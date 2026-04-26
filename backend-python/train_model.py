from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

from app.db import close_db, connect_db, get_db
from app.services.ml_ranker import build_heuristic_label, build_text_document

ARTIFACT_PATH = Path(__file__).resolve().parent / "app" / "models" / "resume_ranker.joblib"
DEFAULT_JSONL_PATH = Path(__file__).resolve().parents[1] / "resumes.jsonl"
RESUME_HINT_TOKENS = [
    "resume",
    "candidate",
    "skills",
    "experience",
    "education",
    "projects",
    "hiring",
    "job",
    "recruit",
    "cv",
    "work",
    "portfolio",
    "internship",
]


def _normalize_skill(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_required_skills(job_doc: dict[str, Any]) -> list[str]:
    raw = str(job_doc.get("requiredSkills", "") or "")
    if not raw.strip():
        return []

    tokens = []
    for part in raw.replace("|", ",").split(","):
        token = _normalize_skill(part)
        if token:
            tokens.append(token)
    return list(dict.fromkeys(tokens))


def _target_from_resume(resume_doc: dict[str, Any], required_skills: list[str], job_description: str) -> float:
    numeric_targets = [
        resume_doc.get("scoreLabel"),
        resume_doc.get("targetScore"),
        resume_doc.get("manualScore"),
    ]
    for value in numeric_targets:
        if isinstance(value, (int, float)):
            return float(min(100, max(0, value)))

    if isinstance(resume_doc.get("hired"), bool):
        return 100.0 if resume_doc.get("hired") else 25.0

    if isinstance(resume_doc.get("shortlisted"), bool):
        return 85.0 if resume_doc.get("shortlisted") else 35.0

    return float(build_heuristic_label(resume_doc, required_skills, job_description))


def _score_to_label(score: float, threshold: float = 70.0) -> int:
    return 1 if float(score) >= threshold else 0


def _extract_message_content(messages: Any, role: str) -> str:
    if not isinstance(messages, list):
        return ""
    for item in reversed(messages):
        if isinstance(item, dict) and str(item.get("role", "")).lower() == role:
            return str(item.get("content", "") or "")
    return ""


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _coerce_label(value: Any) -> int | None:
    if isinstance(value, bool):
        return 1 if value else 0

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric in {0.0, 1.0}:
            return int(numeric)
        return 1 if numeric >= 50 else 0

    text = _normalize_text(value)
    if text in {"1", "true", "relevant", "yes", "fit", "match", "positive"}:
        return 1
    if text in {"0", "false", "irrelevant", "no", "reject", "negative"}:
        return 0
    return None


def _infer_label_from_text(user_text: str, assistant_text: str) -> int:
    combined = _normalize_text(user_text + " " + assistant_text)
    score = sum(1 for token in RESUME_HINT_TOKENS if token in combined)
    return 1 if score >= 2 else 0


def _extract_document_text(record: dict[str, Any]) -> str:
    for key in ["resume_text", "resumeText", "text", "content", "document", "candidate_profile"]:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = record.get("messages", [])
    user_text = _extract_message_content(messages, "user")
    assistant_text = _extract_message_content(messages, "assistant")
    merged = " ".join(part for part in [user_text, assistant_text] if part)
    return merged.strip()


def _extract_label(record: dict[str, Any], threshold: float) -> tuple[int, str]:
    for key in ["label", "relevant", "target", "class", "class_label", "is_relevant", "fit"]:
        if key in record:
            coerced = _coerce_label(record.get(key))
            if coerced is not None:
                return coerced, "manual"

    for key in ["score", "targetScore", "manualScore", "scoreLabel"]:
        if key in record:
            value = record.get(key)
            if isinstance(value, (int, float)):
                return _score_to_label(float(value), threshold=threshold), "manual"

    messages = record.get("messages", [])
    user_text = _extract_message_content(messages, "user")
    assistant_text = _extract_message_content(messages, "assistant")
    return _infer_label_from_text(user_text, assistant_text), "heuristic"


def build_dataset_from_jsonl(
    jsonl_path: Path,
    limit: int | None = None,
    threshold: float = 70.0,
) -> tuple[list[str], list[float], list[int], dict[str, int]]:
    if not jsonl_path.exists():
        raise RuntimeError(f"JSONL dataset not found at {jsonl_path}")

    documents: list[str] = []
    score_targets: list[float] = []
    label_targets: list[int] = []
    counters = {
        "total": 0,
        "heuristic_targets": 0,
        "manual_targets": 0,
        "positive_labels": 0,
    }

    with jsonl_path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if limit and len(documents) >= limit:
                break

            raw = line.strip()
            if not raw:
                continue

            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if not isinstance(record, dict):
                continue

            document = _extract_document_text(record)
            if not document:
                continue

            label_target, source = _extract_label(record, threshold=threshold)
            score_target = 85.0 if label_target == 1 else 25.0

            counters["total"] += 1
            if source == "manual":
                counters["manual_targets"] += 1
            else:
                counters["heuristic_targets"] += 1
            if label_target == 1:
                counters["positive_labels"] += 1

            documents.append(document)
            label_targets.append(label_target)
            score_targets.append(score_target)

    return documents, score_targets, label_targets, counters


def build_dataset(limit: int | None = None, threshold: float = 70.0) -> tuple[list[str], list[float], list[int], dict[str, int]]:
    db = get_db()

    jobs_by_id: dict[Any, dict[str, Any]] = {}
    for job in db.jobs.find({}):
        jobs_by_id[job.get("_id")] = job

    query = {}
    cursor = db.resumes.find(query)
    if limit and limit > 0:
        cursor = cursor.limit(limit)

    documents: list[str] = []
    score_targets: list[float] = []
    label_targets: list[int] = []
    counters = {
        "total": 0,
        "heuristic_targets": 0,
        "manual_targets": 0,
        "positive_labels": 0,
    }

    for resume in cursor:
        counters["total"] += 1
        job_doc = jobs_by_id.get(resume.get("jobId"), {})
        required_skills = _extract_required_skills(job_doc)
        job_description = str(job_doc.get("jobDescription", "") or "")

        if not required_skills:
            required_skills = [_normalize_skill(item) for item in resume.get("skills", [])[:5] if _normalize_skill(item)]

        score_target = _target_from_resume(resume, required_skills, job_description)
        label_target = _score_to_label(score_target, threshold=threshold)
        has_manual_target = any(
            isinstance(resume.get(field), (int, float)) for field in ["scoreLabel", "targetScore", "manualScore"]
        ) or isinstance(resume.get("hired"), bool) or isinstance(resume.get("shortlisted"), bool)
        if has_manual_target:
            counters["manual_targets"] += 1
        else:
            counters["heuristic_targets"] += 1

        if label_target == 1:
            counters["positive_labels"] += 1

        documents.append(build_text_document(resume, required_skills, job_description))
        score_targets.append(score_target)
        label_targets.append(label_target)

    return documents, score_targets, label_targets, counters


def train_model(limit: int | None = None, threshold: float = 70.0, jsonl_path: Path | None = None) -> None:
    if jsonl_path is not None:
        documents, score_targets, label_targets, counters = build_dataset_from_jsonl(
            jsonl_path=jsonl_path,
            limit=limit,
            threshold=threshold,
        )
        dataset_source = f"jsonl:{jsonl_path}"
    else:
        documents, score_targets, label_targets, counters = build_dataset(limit=limit, threshold=threshold)
        dataset_source = "mongodb"

    if len(documents) < 8:
        raise RuntimeError("Not enough resumes to train. Add at least 8 resumes first.")

    unique_labels = set(label_targets)
    if len(unique_labels) < 2:
        raise RuntimeError(
            "Need both positive and negative labels to train a classifier. "
            "Add more varied resumes or adjust --threshold."
        )

    tfidf_config = {
        "max_features": 30000,
        "ngram_range": (1, 2),
        "lowercase": True,
        "stop_words": "english",
        "sublinear_tf": True,
        "min_df": 1,
    }

    vectorizer = TfidfVectorizer(**tfidf_config)
    X = vectorizer.fit_transform(documents)

    X_train, X_test, y_train, y_test, score_train, score_test = train_test_split(
        X,
        label_targets,
        score_targets,
        test_size=0.25,
        random_state=42,
        stratify=label_targets,
    )

    model = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
        solver="liblinear",
    )
    model.fit(X_train, y_train)

    if hasattr(model, "predict_proba"):
        probas = model.predict_proba(X_test)[:, 1]
    else:
        decision_values = model.decision_function(X_test)
        probas = [1.0 / (1.0 + (2.718281828 ** (-value))) for value in decision_values]

    y_pred = [1 if value >= 0.5 else 0 for value in probas]
    score_predictions = [float(min(100, max(0, round(value * 100)))) for value in probas]

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    mae = mean_absolute_error(score_test, score_predictions)

    class_counts = {0: label_targets.count(0), 1: label_targets.count(1)}
    max_cv_folds = min(5, class_counts[0], class_counts[1])
    if max_cv_folds >= 2:
        cv_pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(**tfidf_config)),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=42,
                    solver="liblinear",
                ),
            ),
        ])
        cv = StratifiedKFold(n_splits=max_cv_folds, shuffle=True, random_state=42)
        cv_scores = cross_val_score(cv_pipeline, documents, label_targets, cv=cv, scoring="f1")
        cv_f1 = float(cv_scores.mean())
    else:
        cv_f1 = None

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "kind": "text_tfidf_logreg_v2",
        "task": "binary_relevance",
        "threshold": 0.5,
        "datasetSource": dataset_source,
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "vectorizer": vectorizer,
        "metrics": {
            "mae": float(mae),
            "r2": None,
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "cvF1": cv_f1,
            "sampleCount": len(documents),
            "manualTargetCount": counters["manual_targets"],
            "heuristicTargetCount": counters["heuristic_targets"],
            "positiveLabelCount": counters["positive_labels"],
            "negativeLabelCount": len(documents) - counters["positive_labels"],
        },
    }
    joblib.dump(payload, ARTIFACT_PATH)

    print("Model training complete")
    print(f"Artifact: {ARTIFACT_PATH}")
    print(f"Samples: {len(documents)}")
    print(f"Manual labels: {counters['manual_targets']}")
    print(f"Heuristic labels: {counters['heuristic_targets']}")
    print(f"Positive labels: {counters['positive_labels']}")
    print(f"Negative labels: {len(documents) - counters['positive_labels']}")
    print(f"Accuracy: {accuracy:.3f}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"F1: {f1:.3f}")
    if cv_f1 is not None:
        print(f"CV F1: {cv_f1:.3f}")
    else:
        print("CV F1: N/A (insufficient class balance for cross-validation)")
    print(f"MAE: {mae:.3f}")
    print("R2: N/A (classification model)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the resume ranking model from MongoDB data")
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum resumes to use")
    parser.add_argument(
        "--threshold",
        type=float,
        default=70.0,
        help="Score threshold (0-100) for converting targets into relevant/not-relevant labels",
    )
    parser.add_argument(
        "--jsonl-path",
        type=str,
        default="",
        help="Optional path to resumes JSONL dataset. If provided, trains from JSONL instead of MongoDB.",
    )
    args = parser.parse_args()

    jsonl_path = Path(args.jsonl_path).resolve() if str(args.jsonl_path or "").strip() else None
    if jsonl_path is None and DEFAULT_JSONL_PATH.exists():
        jsonl_path = DEFAULT_JSONL_PATH

    if jsonl_path is not None:
        train_model(limit=args.limit or None, threshold=args.threshold, jsonl_path=jsonl_path)
    else:
        connect_db()
        try:
            train_model(limit=args.limit or None, threshold=args.threshold)
        finally:
            close_db()
