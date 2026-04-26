from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import time
import re

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.db import get_db
from app.serializers import serialize_document
from app.services.resume_parser import (
    extract_text_from_pdf,
    parse_resume_text,
    safe_upload_filename,
)
from app.services.ml_ranker import get_model_status, predict_score

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

DEFAULT_REQUIRED_SKILLS = ["python", "sql", "machine learning", "data analysis", "pandas"]
KNOWN_SKILLS = [
    "python",
    "sql",
    "machine learning",
    "data analysis",
    "pandas",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "react",
    "node",
    "javascript",
    "java",
    "c++",
]
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_skill(value: Any) -> str:
    return str(value or "").strip().lower()


def title_case(text: str) -> str:
    return " ".join(part[:1].upper() + part[1:] for part in text.split() if part)


def _split_skill_text(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = [item.strip() for item in re.split(r"[,;/\n|]+", str(value or ""))]

    return list(dict.fromkeys([normalize_skill(item) for item in raw_items if normalize_skill(item)]))


def build_job_description(job: dict[str, Any]) -> str:
    lines = [
        job.get("title") and f"Role: {job.get('title')}",
        job.get("department") and f"Department: {job.get('department')}",
        job.get("requiredSkills") and f"Required Skills: {job.get('requiredSkills')}",
        job.get("experienceLevel") and f"Experience Level: {job.get('experienceLevel')}",
        job.get("jobDescription") and f"Job Description: {job.get('jobDescription')}",
    ]
    return "\n".join(str(item) for item in lines if item)


def get_required_skills(job_description: str = "", explicit_skills: list[str] | None = None) -> list[str]:
    normalized_text = str(job_description or "").lower()
    detected = [skill for skill in KNOWN_SKILLS if skill in normalized_text]
    combined = list(dict.fromkeys([*(explicit_skills or []), *detected]))
    if not combined:
        combined = DEFAULT_REQUIRED_SKILLS
    return list(dict.fromkeys(combined))


def _load_job_for_rankings(job_id: str | None) -> dict[str, Any] | None:
    if not job_id:
        return None

    try:
        job_object_id = ObjectId(job_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid job id") from exc

    db = get_db()
    job = db.jobs.find_one({"_id": job_object_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


def calculate_candidate_insights(resume: dict, required_skills: list[str], job_description: str = "") -> dict:
    resume_skills = list(dict.fromkeys([normalize_skill(item) for item in resume.get("skills", []) if normalize_skill(item)]))
    matched_skills = [skill for skill in required_skills if skill in resume_skills]
    missing_skills = [skill for skill in required_skills if skill not in resume_skills]

    score, score_source = predict_score(resume, required_skills, job_description)

    reasons: list[str] = []
    if matched_skills:
        reasons.append(f"Matched {len(matched_skills)} required skills: {', '.join(title_case(item) for item in matched_skills)}")
    if resume.get("experience"):
        reasons.append(f"Experience section includes {len(resume.get('experience', []))} relevant highlights")
    if resume.get("projects"):
        reasons.append(f"Project portfolio contains {len(resume.get('projects', []))} listed projects")
    if missing_skills:
        reasons.append(f"Skill gaps found in: {', '.join(title_case(item) for item in missing_skills)}")

    recommendation = (
        f"Strengthen {' and '.join(title_case(item) for item in missing_skills[:2])} to improve ranking."
        if missing_skills
        else "Profile strongly aligns with the current role requirements."
    )

    return {
        "id": str(resume.get("_id")),
        "name": resume.get("name") or "Unknown Candidate",
        "score": score,
        "matchedSkills": [title_case(item) for item in matched_skills],
        "missingSkills": [title_case(item) for item in missing_skills],
        "recommendation": recommendation,
        "reasons": reasons,
        "scoreSource": score_source,
        "skills": resume.get("skills", []),
        "experience": resume.get("experience", []),
        "education": resume.get("education", []),
        "projects": resume.get("projects", []),
        "summary": resume.get("summary", ""),
        "email": resume.get("email", ""),
        "phone": resume.get("phone", ""),
    }


def _save_upload(file: UploadFile) -> Path:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    filename = f"{int(time.time() * 1000)}-{safe_upload_filename(file.filename)}"
    destination = UPLOADS_DIR / filename

    with destination.open("wb") as output:
        output.write(file.file.read())

    return destination


def _relative_upload_path(file_path: Path) -> str:
    return str(Path("uploads") / file_path.name).replace("\\", "/")


@router.post("/upload")
def upload_resume(resume: UploadFile = File(...), jobId: str | None = Form(default=None)):
    if not resume:
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    job = _load_job_for_rankings(jobId)
    file_path = _save_upload(resume)
    extracted_text = extract_text_from_pdf(str(file_path))
    parsed_data = parse_resume_text(extracted_text)

    now = datetime.now(timezone.utc)
    resume_doc = {
        **parsed_data,
        "originalFilePath": _relative_upload_path(file_path),
        "extractedText": extracted_text,
        "jobId": ObjectId(jobId) if jobId else None,
        "jobTitle": job.get("title") if job else None,
        "createdAt": now,
        "updatedAt": now,
    }

    db = get_db()
    result = db.resumes.insert_one(resume_doc)
    saved = db.resumes.find_one({"_id": result.inserted_id})
    return serialize_document(saved)


@router.post("/upload/batch")
def upload_multiple_resumes(
    resumes: list[UploadFile] = File(...),
    jobId: str | None = Form(default=None),
):
    if not resumes:
        raise HTTPException(status_code=400, detail="Please upload at least one PDF file")

    job = _load_job_for_rankings(jobId)
    db = get_db()
    created_resumes = []

    for file in resumes[:30]:
        file_path = _save_upload(file)
        extracted_text = extract_text_from_pdf(str(file_path))
        parsed_data = parse_resume_text(extracted_text)

        now = datetime.now(timezone.utc)
        resume_doc = {
            **parsed_data,
            "originalFilePath": _relative_upload_path(file_path),
            "extractedText": extracted_text,
            "createdAt": now,
            "updatedAt": now,
            "jobId": ObjectId(jobId) if jobId else None,
            "jobTitle": job.get("title") if job else None,
        }

        result = db.resumes.insert_one(resume_doc)
        saved = db.resumes.find_one({"_id": result.inserted_id})
        created_resumes.append(serialize_document(saved))

    return {
        "uploadedCount": len(created_resumes),
        "candidates": created_resumes,
    }


@router.get("")
def get_all_resumes():
    db = get_db()
    resumes = list(db.resumes.find({}, {"extractedText": 0}))
    return [serialize_document(item) for item in resumes]


@router.get("/rankings")
def get_resume_rankings(
    resumeId: str | None = Query(default=None),
    jobDescription: str = Query(default=""),
    jobId: str | None = Query(default=None),
):
    db = get_db()

    job = _load_job_for_rankings(jobId)
    job_description_from_job = build_job_description(job) if job else ""
    combined_job_description = "\n".join(part for part in [job_description_from_job, jobDescription] if part)
    explicit_skills = _split_skill_text(job.get("requiredSkills") if job else "")
    required_skills = get_required_skills(combined_job_description, explicit_skills)

    query: dict[str, Any] = {}
    if jobId:
        query["jobId"] = ObjectId(jobId)

    resumes = list(db.resumes.find(query, {"extractedText": 0}))

    if not resumes:
        return {
            "jobDescription": jobDescription,
            "requiredSkills": [title_case(skill) for skill in required_skills],
            "evaluatedAt": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "totalCandidates": 0,
                "averageScore": 0,
            },
            "selectedCandidate": None,
            "candidates": [],
        }

    ranked_candidates = sorted(
        [
            calculate_candidate_insights(
                resume,
                required_skills,
                combined_job_description or jobDescription,
            )
            for resume in resumes
        ],
        key=lambda item: item["score"],
        reverse=True,
    )

    ranked_candidates = [
        {
            **candidate,
            "rank": index + 1,
        }
        for index, candidate in enumerate(ranked_candidates)
    ]

    selected_candidate = None
    if resumeId:
        selected_candidate = next((item for item in ranked_candidates if item["id"] == str(resumeId)), None)
        if not selected_candidate:
            raise HTTPException(status_code=404, detail="Requested resume was not found in ranking results.")

    average_score = round(sum(item["score"] for item in ranked_candidates) / len(ranked_candidates))

    return {
        "jobDescription": combined_job_description or jobDescription,
        "requiredSkills": [title_case(skill) for skill in required_skills],
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "totalCandidates": len(ranked_candidates),
            "averageScore": average_score,
        },
        "job": serialize_document(job) if job else None,
        "selectedCandidate": selected_candidate,
        "candidates": ranked_candidates,
    }


@router.get("/model-status")
def get_resume_model_status():
    return get_model_status()


@router.get("/{resume_id}")
def get_resume_by_id(resume_id: str):
    db = get_db()
    resume = db.resumes.find_one({"_id": ObjectId(resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return serialize_document(resume)
