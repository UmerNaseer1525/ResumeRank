from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import math
import re

import joblib


MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "resume_ranker.joblib"
BERT_MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "resume_ranker_bert"
BERT_METADATA_PATH = BERT_MODEL_DIR / "metadata.json"


@dataclass
class _ModelState:
    vectorizer: Any
    model: Any
    mtime: float
    payload: dict[str, Any]


@dataclass
class _BertModelState:
    tokenizer: Any
    model: Any
    mtime: float
    metadata: dict[str, Any]


_model_state: _ModelState | None = None
_bert_state: _BertModelState | None = None


def _normalize_skill(value: Any) -> str:
    return str(value or "").strip().lower()


def _safe_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if not value:
        return 0
    return 1


def _education_has_degree(education_value: Any) -> int:
    if isinstance(education_value, list):
        education_text = " ".join(str(item) for item in education_value).lower()
    else:
        education_text = str(education_value or "").lower()

    degree_tokens = ["bs", "bachelor", "master", "phd", "msc", "ms"]
    return 1 if any(token in education_text for token in degree_tokens) else 0


def _feature_map(resume: dict[str, Any], required_skills: list[str], job_description: str = "") -> dict[str, float]:
    resume_skills = list(
        dict.fromkeys([_normalize_skill(item) for item in resume.get("skills", []) if _normalize_skill(item)])
    )
    normalized_required = [_normalize_skill(item) for item in required_skills if _normalize_skill(item)]
    matched_skills = [skill for skill in normalized_required if skill in resume_skills]

    required_count = len(normalized_required)
    matched_count = len(matched_skills)
    missing_count = max(required_count - matched_count, 0)

    features: dict[str, float] = {
        "required_skill_count": float(required_count),
        "matched_skill_count": float(matched_count),
        "missing_skill_count": float(missing_count),
        "matched_ratio": float(matched_count / required_count) if required_count else 0.0,
        "resume_skill_count": float(len(resume_skills)),
        "experience_count": float(_safe_len(resume.get("experience", []))),
        "project_count": float(_safe_len(resume.get("projects", []))),
        "education_degree_flag": float(_education_has_degree(resume.get("education", []))),
        "summary_char_len": float(len(str(resume.get("summary", "") or ""))),
        "job_description_char_len": float(len(str(job_description or ""))),
    }

    for skill in normalized_required:
        key = skill.replace(" ", "_")
        features[f"req_skill::{key}"] = 1.0
        features[f"has_skill::{key}"] = 1.0 if skill in resume_skills else 0.0

    return features


def _normalize_text(text: Any) -> str:
    value = str(text or "").lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def build_text_document(resume: dict[str, Any], required_skills: list[str], job_description: str = "") -> str:
    sections: list[str] = []

    sections.append(str(resume.get("summary", "") or ""))
    sections.extend([str(item) for item in resume.get("experience", [])])
    sections.extend([str(item) for item in resume.get("projects", [])])
    sections.extend([str(item) for item in resume.get("education", [])])
    sections.extend([str(item) for item in resume.get("skills", [])])

    # Include role context so the same resume can be scored against different jobs.
    sections.append("required skills " + " ".join(str(skill) for skill in required_skills))
    sections.append("job description " + str(job_description or ""))

    return _normalize_text(" ".join(part for part in sections if part))


def _analyze_experience_depth(experience: Any) -> tuple[float, float]:
    """Analyze experience for depth (responsibilities, growth) and seniority"""
    if not isinstance(experience, list) or not experience:
        return 0.0, 0.0
    
    depth_score = 0.0
    seniority_score = 0.0
    
    for exp in experience:
        if isinstance(exp, dict):
            title = _normalize_text(exp.get("title", ""))
            description = _normalize_text(exp.get("description", "") or exp.get("details", ""))
        else:
            # Parser output is often plain text lines; score them instead of skipping.
            title = ""
            description = _normalize_text(exp)
        
        # Seniority keywords
        seniority_keywords = ["lead", "senior", "principal", "architect", "director", "manager", "head"]
        exp_seniority = 1.0 if any(kw in title or kw in description for kw in seniority_keywords) else 0.0
        seniority_score = max(seniority_score, exp_seniority)
        
        # Experience depth signals
        depth_keywords = [
            "designed", "architected", "implemented", "developed", "optimized",
            "led", "mentored", "improved", "reduced", "increased", "scaled",
            "automated", "deployed", "managed", "coordinated", "solved",
            "performance", "efficiency", "impact", "responsibility"
        ]
        depth_count = sum(1 for kw in depth_keywords if kw in description)
        depth_score = max(depth_score, min(depth_count / 4.0, 1.0))
    
    return min(depth_score, 1.0), min(seniority_score, 1.0)


def _analyze_project_quality(projects: Any) -> float:
    """Analyze project descriptions for technical depth and impact"""
    if not isinstance(projects, list) or not projects:
        return 0.0
    
    quality_score = 0.0
    
    for project in projects:
        if isinstance(project, dict):
            description = _normalize_text(project.get("description", "") or project.get("details", ""))
        else:
            # Parser output is often plain text lines; score them instead of skipping.
            description = _normalize_text(project)
        
        # Technical depth indicators
        tech_signals = [
            "algorithm", "architecture", "pattern", "framework", "optimization",
            "scale", "performance", "concurrent", "distributed", "microservice",
            "api", "database", "backend", "frontend", "fullstack"
        ]
        tech_count = sum(1 for sig in tech_signals if sig in description)
        
        # Impact indicators
        impact_signals = ["users", "deployed", "production", "performance", "improved"]
        impact_count = sum(1 for sig in impact_signals if sig in description)
        
        project_quality = (tech_count + impact_count) / 10.0
        quality_score = max(quality_score, project_quality)
    
    return min(quality_score, 1.0)


def _analyze_skills_relevance(resume_skills: list[str], required_skills: list[str]) -> tuple[float, float]:
    """Analyze skill relevance beyond binary match - consider skill categories"""
    if not required_skills or not resume_skills:
        return 0.0, 0.0
    
    normalized_resume = [_normalize_skill(s) for s in resume_skills]
    normalized_required = [_normalize_skill(s) for s in required_skills]
    
    # Exact matches
    exact_matches = sum(1 for req in normalized_required if req in normalized_resume)
    exact_ratio = exact_matches / len(normalized_required) if normalized_required else 0.0
    
    # Semantic similarity (basic keyword matching)
    related_keywords = {
        "python": ["python", "py", "django", "flask", "fastapi"],
        "java": ["java", "spring", "maven", "junit"],
        "sql": ["sql", "mysql", "postgres", "database", "nosql"],
        "machine learning": ["ml", "ai", "neural", "tensor", "keras", "pytorch", "scikit"],
        "data analysis": ["data", "pandas", "numpy", "analytics", "visualization"],
        "frontend": ["react", "vue", "angular", "html", "css", "javascript"],
        "backend": ["backend", "api", "server", "node", "express"],
    }
    
    semantic_matches = 0
    for req in normalized_required:
        for category, keywords in related_keywords.items():
            if any(kw in req for kw in keywords):
                if any(kw in skill for skill in normalized_resume for kw in keywords):
                    semantic_matches += 1
                    break
    
    semantic_ratio = semantic_matches / len(normalized_required) if normalized_required else 0.0
    
    # Overall relevance combining exact + semantic
    relevance = (exact_ratio + semantic_ratio) / 2.0
    
    return exact_ratio, relevance


def _heuristic_score(resume: dict[str, Any], required_skills: list[str], job_description: str = "") -> int:
    """Enhanced heuristic scoring with multiple intelligence factors"""
    features = _feature_map(resume, required_skills, job_description)
    
    # ===== SKILL SCORING (30-40%) =====
    exact_skill_match, semantic_relevance = _analyze_skills_relevance(
        resume.get("skills", []), required_skills
    )
    skill_score = (exact_skill_match * 0.6 + semantic_relevance * 0.4) * 100
    
    # ===== EXPERIENCE SCORING (20-30%) =====
    exp_depth, seniority = _analyze_experience_depth(resume.get("experience", []))
    exp_count = min(features["experience_count"] / 5.0, 1.0)  # Normalize to 1.0
    experience_score = (exp_depth * 0.5 + seniority * 0.3 + exp_count * 0.2) * 100
    
    # ===== PROJECT SCORING (10-15%) =====
    project_quality = _analyze_project_quality(resume.get("projects", []))
    project_count_score = min(features["project_count"] / 5.0, 1.0)
    project_score = (project_count_score * 0.4 + project_quality * 0.6) * 100
    
    # ===== EDUCATION BONUS (5-10%) =====
    education_score = features["education_degree_flag"] * 100
    
    # ===== SUMMARY/PROFILE QUALITY (5-10%) =====
    summary_length = features["summary_char_len"]
    summary_quality = min(summary_length / 500.0, 1.0) * 100
    
    # ===== SKILL DEPTH BONUS (5%) =====
    total_resume_skills = features["resume_skill_count"]
    skill_diversity_score = min(total_resume_skills / 15.0, 1.0) * 100
    
    # Combine all scores with weighted system
    final_score = (
        skill_score * 0.35 +        # Skills: 35%
        experience_score * 0.25 +   # Experience: 25%
        project_score * 0.15 +      # Projects: 15%
        education_score * 0.10 +    # Education: 10%
        summary_quality * 0.08 +    # Summary: 8%
        skill_diversity_score * 0.07  # Skill diversity: 7%
    )
    
    return int(min(100, max(0, round(final_score))))


def _load_model_state() -> _ModelState | None:
    global _model_state

    if not MODEL_PATH.exists():
        return None

    mtime = MODEL_PATH.stat().st_mtime
    if _model_state and math.isclose(_model_state.mtime, mtime):
        return _model_state

    payload = joblib.load(MODEL_PATH)
    if not isinstance(payload, dict):
        return None

    vectorizer = payload.get("vectorizer")
    model = payload.get("model")
    if vectorizer is None or model is None:
        return None

    _model_state = _ModelState(vectorizer=vectorizer, model=model, mtime=mtime, payload=payload)
    return _model_state


def _load_bert_state() -> _BertModelState | None:
    global _bert_state

    if not BERT_MODEL_DIR.exists() or not BERT_METADATA_PATH.exists():
        return None

    try:
        mtime = BERT_METADATA_PATH.stat().st_mtime
    except Exception:
        return None

    if _bert_state and math.isclose(_bert_state.mtime, mtime):
        return _bert_state

    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
    except Exception:
        return None

    try:
        metadata = json.loads(BERT_METADATA_PATH.read_text(encoding="utf-8"))
        tokenizer = AutoTokenizer.from_pretrained(str(BERT_MODEL_DIR))
        model = AutoModelForSequenceClassification.from_pretrained(str(BERT_MODEL_DIR))
        model.eval()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        metadata["device"] = str(device)
    except Exception:
        return None

    _bert_state = _BertModelState(
        tokenizer=tokenizer,
        model=model,
        mtime=mtime,
        metadata=metadata,
    )
    return _bert_state


def predict_score(resume: dict[str, Any], required_skills: list[str], job_description: str = "") -> tuple[int, str]:
    heuristic_score = _heuristic_score(resume, required_skills, job_description)

    bert_state = _load_bert_state()
    if bert_state is not None:
        try:
            import torch

            text_document = build_text_document(resume, required_skills, job_description)
            threshold = float(bert_state.metadata.get("threshold", 0.5))

            encoded = bert_state.tokenizer(
                text_document,
                truncation=True,
                padding="max_length",
                max_length=int(bert_state.metadata.get("max_length", 256)),
                return_tensors="pt",
            )
            device = bert_state.metadata.get("device", "cpu")
            encoded = {key: value.to(device) for key, value in encoded.items()}

            with torch.no_grad():
                output = bert_state.model(**encoded)
                probabilities = torch.softmax(output.logits, dim=-1)[0]
                positive_probability = float(probabilities[1].item())

            score = int(min(100, max(0, round(positive_probability * 100))))
            if positive_probability < threshold:
                score = min(score, 69)

            return max(score, heuristic_score), "ml-model"
        except Exception:
            pass

    state = _load_model_state()

    if state is None:
        return heuristic_score, "heuristic"

    try:
        model_kind = str(state.payload.get("kind", ""))

        if model_kind == "text_tfidf_logreg_v2":
            threshold = float(state.payload.get("threshold", 0.5))
            text_document = build_text_document(resume, required_skills, job_description)
            X = state.vectorizer.transform([text_document])

            if hasattr(state.model, "predict_proba"):
                score_probability = float(state.model.predict_proba(X)[0][1])
            else:
                decision = float(state.model.decision_function(X)[0])
                score_probability = 1.0 / (1.0 + math.exp(-decision))

            score = int(min(100, max(0, round(score_probability * 100))))
            if score_probability < threshold:
                score = min(score, 69)
        else:
            # Backward compatibility for older dict-feature regression artifacts.
            features = _feature_map(resume, required_skills, job_description)
            X = state.vectorizer.transform([features])
            prediction = float(state.model.predict(X)[0])
            score = int(min(100, max(0, round(prediction))))

        return max(score, heuristic_score), "ml-model"
    except Exception:
        return heuristic_score, "heuristic"


def build_training_features(resume: dict[str, Any], required_skills: list[str], job_description: str = "") -> dict[str, float]:
    return _feature_map(resume, required_skills, job_description)


def build_heuristic_label(resume: dict[str, Any], required_skills: list[str], job_description: str = "") -> int:
    return _heuristic_score(resume, required_skills, job_description)


def get_model_status() -> dict[str, Any]:
    if BERT_MODEL_DIR.exists() and BERT_METADATA_PATH.exists():
        try:
            metadata = json.loads(BERT_METADATA_PATH.read_text(encoding="utf-8"))
            metrics = metadata.get("metrics", {}) if isinstance(metadata, dict) else {}
            return {
                "exists": True,
                "path": str(BERT_MODEL_DIR),
                "trainedAt": metadata.get("trainedAt") if isinstance(metadata, dict) else None,
                "mae": metrics.get("mae"),
                "r2": metrics.get("r2"),
                "accuracy": metrics.get("accuracy"),
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1": metrics.get("f1"),
                "cvF1": metrics.get("cvF1"),
                "sampleCount": metrics.get("sampleCount", 0),
                "scoreSource": "ml-model",
                "modelKind": metadata.get("kind"),
                "datasetSource": metadata.get("datasetSource"),
            }
        except Exception as exc:
            return {
                "exists": False,
                "path": str(BERT_MODEL_DIR),
                "trainedAt": None,
                "mae": None,
                "r2": None,
                "sampleCount": 0,
                "scoreSource": "heuristic",
                "error": str(exc),
            }

    if not MODEL_PATH.exists():
        return {
            "exists": False,
            "path": str(MODEL_PATH),
            "trainedAt": None,
            "mae": None,
            "r2": None,
            "sampleCount": 0,
            "scoreSource": "heuristic",
        }

    try:
        payload = joblib.load(MODEL_PATH)
        metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
        return {
            "exists": True,
            "path": str(MODEL_PATH),
            "trainedAt": payload.get("trainedAt") if isinstance(payload, dict) else None,
            "mae": metrics.get("mae"),
            "r2": metrics.get("r2"),
            "accuracy": metrics.get("accuracy"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "f1": metrics.get("f1"),
            "cvF1": metrics.get("cvF1"),
            "sampleCount": metrics.get("sampleCount", 0),
            "scoreSource": "ml-model",
            "modelKind": payload.get("kind") if isinstance(payload, dict) else None,
            "datasetSource": payload.get("datasetSource") if isinstance(payload, dict) else None,
        }
    except Exception as exc:
        return {
            "exists": False,
            "path": str(MODEL_PATH),
            "trainedAt": None,
            "mae": None,
            "r2": None,
            "sampleCount": 0,
            "scoreSource": "heuristic",
            "error": str(exc),
        }
