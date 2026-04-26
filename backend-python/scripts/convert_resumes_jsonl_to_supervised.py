from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


RESUME_SIGNALS = [
    "resume",
    "candidate",
    "skills",
    "experience",
    "education",
    "project",
    "internship",
    "hiring",
    "recruit",
    "cv",
    "work",
    "portfolio",
    "linkedin",
    "github",
]

ROLE_KEYWORDS: dict[str, list[str]] = {
    "data_scientist": ["data scientist", "machine learning", "pandas", "numpy", "scikit", "statistics"],
    "ml_engineer": ["ml engineer", "deep learning", "tensorflow", "pytorch", "llm", "rag"],
    "ui_ux_designer": ["ui", "ux", "figma", "wireframe", "prototype", "usability"],
    "frontend_engineer": ["react", "next.js", "javascript", "html", "css", "frontend"],
    "backend_engineer": ["fastapi", "flask", "django", "node", "express", "api", "backend"],
    "fullstack_engineer": ["full stack", "fullstack", "frontend and backend", "mern"],
    "devops_cloud": ["aws", "azure", "gcp", "kubernetes", "docker", "devops", "cloud"],
    "technical_recruiter": ["technical recruiter", "sourcing", "hiring", "candidate matching", "recruitment"],
    "support_engineer": ["technical support", "incident", "sla", "ticketing", "customer support"],
}


EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)\d{3}[\s-]?\d{4,}")


def _normalize(text: Any) -> str:
    value = str(text or "").lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _extract_message(messages: Any, role: str) -> str:
    if not isinstance(messages, list):
        return ""
    for item in reversed(messages):
        if isinstance(item, dict) and str(item.get("role", "")).lower() == role:
            return str(item.get("content", "") or "").strip()
    return ""


def _extract_document_text(record: dict[str, Any], user_text: str, assistant_text: str) -> str:
    for key in ["resume_text", "resumeText", "text", "content", "document", "candidate_profile"]:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if assistant_text:
        return assistant_text

    return user_text


def _infer_relevance_label(user_text: str, assistant_text: str, document_text: str) -> tuple[int, float, str]:
    combined = _normalize(" ".join([user_text, assistant_text, document_text]))

    signal_hits = sum(1 for token in RESUME_SIGNALS if token in combined)
    has_email = bool(EMAIL_PATTERN.search(combined))
    has_phone = bool(PHONE_PATTERN.search(combined))

    score = signal_hits + (2 if has_email else 0) + (2 if has_phone else 0)

    if score >= 3:
        confidence = min(0.99, 0.55 + (score * 0.08))
        return 1, confidence, "heuristic_resume_signal"

    confidence = min(0.95, 0.55 + ((3 - score) * 0.08))
    return 0, confidence, "heuristic_non_resume"


def _infer_role(text: str) -> tuple[str, float]:
    normalized = _normalize(text)
    if not normalized:
        return "other", 0.0

    best_role = "other"
    best_hits = 0

    for role, keywords in ROLE_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in normalized)
        if hits > best_hits:
            best_hits = hits
            best_role = role

    if best_role == "other":
        return best_role, 0.0

    confidence = min(0.98, 0.45 + best_hits * 0.15)
    return best_role, confidence


def convert(input_path: Path, output_path: Path, stats_path: Path) -> None:
    if not input_path.exists():
        raise RuntimeError(f"Input JSONL not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    invalid = 0
    written = 0
    positive = 0
    negative = 0
    role_counts: dict[str, int] = {}

    with input_path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for index, line in enumerate(src, start=1):
            raw = line.strip()
            if not raw:
                continue

            total += 1

            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                invalid += 1
                continue

            if not isinstance(record, dict):
                invalid += 1
                continue

            messages = record.get("messages", [])
            user_text = _extract_message(messages, "user")
            assistant_text = _extract_message(messages, "assistant")
            document_text = _extract_document_text(record, user_text, assistant_text)

            if not document_text:
                continue

            label, label_confidence, label_source = _infer_relevance_label(user_text, assistant_text, document_text)
            role, role_confidence = _infer_role(document_text)

            item = {
                "line_number": index,
                "resume_text": document_text,
                "query": user_text,
                "response": assistant_text,
                "role": role,
                "role_confidence": round(role_confidence, 4),
                "label": label,
                "label_confidence": round(label_confidence, 4),
                "label_source": label_source,
            }

            dst.write(json.dumps(item, ensure_ascii=False) + "\n")
            written += 1

            if label == 1:
                positive += 1
            else:
                negative += 1

            role_counts[role] = role_counts.get(role, 0) + 1

    stats = {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "total_lines": total,
        "invalid_lines": invalid,
        "written_rows": written,
        "positive_labels": positive,
        "negative_labels": negative,
        "positive_ratio": round((positive / written), 4) if written else 0.0,
        "role_distribution": dict(sorted(role_counts.items(), key=lambda kv: kv[1], reverse=True)),
    }

    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print("Conversion complete")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Stats: {stats_path}")
    print(f"Rows written: {written}")
    print(f"Positive labels: {positive}")
    print(f"Negative labels: {negative}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert resumes.jsonl into supervised training JSONL")
    parser.add_argument(
        "--input",
        type=str,
        default="../resumes.jsonl",
        help="Path to source JSONL dataset",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/resume_supervised.jsonl",
        help="Path to write converted supervised JSONL",
    )
    parser.add_argument(
        "--stats",
        type=str,
        default="data/resume_supervised_stats.json",
        help="Path to write conversion stats JSON",
    )

    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    stats_path = Path(args.stats).resolve()

    convert(input_path=input_path, output_path=output_path, stats_path=stats_path)


if __name__ == "__main__":
    main()
