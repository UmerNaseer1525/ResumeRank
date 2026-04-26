import json
from app.db import get_db
from app.routes.resume_routes import get_required_skills, calculate_candidate_insights


def to_len_list(value):
    return len(value) if isinstance(value, list) else 0


def main():
    db = get_db()

    sample_resumes = list(
        db.resumes.find(
            {},
            {
                "name": 1,
                "extractedText": 1,
                "skills": 1,
                "experience": 1,
                "projects": 1,
                "jobId": 1,
            },
        ).limit(20)
    )

    for resume in sample_resumes:
        row = {
            "id": str(resume.get("_id")),
            "name": resume.get("name") or "Unknown Candidate",
            "text_len": len(resume.get("extractedText") or ""),
            "skills_len": to_len_list(resume.get("skills")),
            "exp_len": to_len_list(resume.get("experience")),
            "projects_len": to_len_list(resume.get("projects")),
            "jobId": str(resume.get("jobId")) if resume.get("jobId") else None,
        }
        print(json.dumps(row, separators=(",", ":"), ensure_ascii=False))

    required_skills = get_required_skills("")
    print("REQUIRED_SKILLS=" + json.dumps(required_skills, separators=(",", ":"), ensure_ascii=False))

    all_resumes = list(db.resumes.find({}, {"extractedText": 0}))
    ranked = sorted(
        [calculate_candidate_insights(resume, required_skills, "") for resume in all_resumes],
        key=lambda item: item.get("score", 0),
        reverse=True,
    )[:10]

    for index, candidate in enumerate(ranked, start=1):
        row = {
            "rank": index,
            "name": candidate.get("name") or "Unknown Candidate",
            "score": candidate.get("score", 0),
            "matchedSkills": len(candidate.get("matchedSkills") or []),
        }
        print("RANKING=" + json.dumps(row, separators=(",", ":"), ensure_ascii=False))


if __name__ == "__main__":
    main()
