from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request

from app.db import get_db
from app.serializers import serialize_document

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("")
async def create_job(request: Request):
    body = await request.json()
    title = str(body.get("title", "")).strip()

    if not title:
        raise HTTPException(status_code=400, detail="Job title is required")

    now = datetime.now(timezone.utc)
    job_doc = {
        "title": title,
        "department": str(body.get("department", "")),
        "requiredSkills": str(body.get("requiredSkills", "")),
        "experienceLevel": str(body.get("experienceLevel", "")),
        "jobDescription": str(body.get("jobDescription", "")),
        "createdAt": now,
        "updatedAt": now,
    }

    db = get_db()
    result = db.jobs.insert_one(job_doc)
    saved = db.jobs.find_one({"_id": result.inserted_id})
    return serialize_document(saved)


@router.get("")
def get_all_jobs():
    db = get_db()
    jobs = list(db.jobs.find().sort("createdAt", -1))

    jobs_with_counts = []
    for job in jobs:
        candidate_count = db.resumes.count_documents({"jobId": job["_id"]})
        item = serialize_document(job)
        item["candidateCount"] = candidate_count
        jobs_with_counts.append(item)

    return jobs_with_counts


@router.get("/{job_id}")
def get_job_by_id(job_id: str):
    db = get_db()
    job = db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    candidate_count = db.resumes.count_documents({"jobId": job["_id"]})
    item = serialize_document(job)
    item["candidateCount"] = candidate_count
    return item


@router.delete("/{job_id}")
def delete_job(job_id: str):
    db = get_db()

    try:
        job_object_id = ObjectId(job_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid job id") from exc

    job = db.jobs.find_one({"_id": job_object_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    now = datetime.now(timezone.utc)
    cleared_resumes = db.resumes.update_many(
        {"jobId": job_object_id},
        {"$set": {"jobId": None, "updatedAt": now}},
    )
    db.jobs.delete_one({"_id": job_object_id})

    return {
        "deleted": True,
        "job": serialize_document(job),
        "unassignedResumes": cleared_resumes.modified_count,
    }
