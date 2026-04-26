from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

SKILL_PATTERNS = {
    "Python": re.compile(r"\bpython\b", re.IGNORECASE),
    "SQL": re.compile(r"\bsql\b", re.IGNORECASE),
    "Machine Learning": re.compile(r"\b(machine learning|ml)\b", re.IGNORECASE),
    "Data Analysis": re.compile(r"\bdata analysis\b", re.IGNORECASE),
    "Pandas": re.compile(r"\bpandas\b", re.IGNORECASE),
    "Scikit-learn": re.compile(r"\bscikit[- ]learn\b", re.IGNORECASE),
    "TensorFlow": re.compile(r"\btensorflow\b", re.IGNORECASE),
    "PyTorch": re.compile(r"\bpytorch\b", re.IGNORECASE),
    "NumPy": re.compile(r"\bnumpy\b", re.IGNORECASE),
    "Excel": re.compile(r"\bexcel\b", re.IGNORECASE),
    "PowerBI": re.compile(r"\bpower\s?bi\b", re.IGNORECASE),
    "Tableau": re.compile(r"\btableau\b", re.IGNORECASE),
    "JavaScript": re.compile(r"\bjavascript\b", re.IGNORECASE),
    "React": re.compile(r"\breact\b", re.IGNORECASE),
    "Node": re.compile(r"\bnode(\.js)?\b", re.IGNORECASE),
    "Java": re.compile(r"\bjava\b", re.IGNORECASE),
    "C++": re.compile(r"(?<!\w)c\+\+(?!\w)|\bcpp\b", re.IGNORECASE),
    "Docker": re.compile(r"\bdocker\b", re.IGNORECASE),
    "Kubernetes": re.compile(r"\bkubernetes\b", re.IGNORECASE),
    "AWS": re.compile(r"\baws\b", re.IGNORECASE),
    "Azure": re.compile(r"\bazure\b", re.IGNORECASE),
    "GCP": re.compile(r"\bgcp\b|google cloud", re.IGNORECASE),
}

SECTION_ALIASES = {
    "summary": ["summary", "profile", "professional summary", "about"],
    "skills": ["skills", "technical skills", "core competencies", "technologies"],
    "education": ["education", "academic background", "qualification", "qualifications"],
    "experience": ["experience", "work experience", "professional experience", "employment history"],
    "projects": ["projects", "project experience", "academic projects"],
}


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", str(line or "").replace("\u2022", " ").replace("\u25cf", " ").replace("\u25aa", " ")).strip()


def find_section_key(line: str) -> str | None:
    normalized = normalize_line(line).lower().rstrip(":")
    for key, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return key
    return None


def is_likely_header(line: str) -> bool:
    normalized = normalize_line(line).lower().rstrip(":")
    return any(normalized in aliases for aliases in SECTION_ALIASES.values())


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys([item for item in values if item]))


def format_name(value: str) -> str:
    return " ".join(part[:1].upper() + part[1:].lower() for part in value.split() if part)


def extract_name(lines: list[str]) -> str:
    for line in lines:
        cleaned = normalize_line(line)
        if not cleaned:
            continue
        if len(cleaned) < 3 or len(cleaned) > 60:
            continue
        if re.search(r"@|http|www\.|linkedin|github|portfolio", cleaned, re.IGNORECASE):
            continue
        if re.search(r"\d", cleaned):
            continue
        if len(cleaned.split()) <= 5:
            return format_name(cleaned)
    return "Unknown Candidate"


def extract_phone(raw_text: str) -> str:
    match = re.search(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)\d{3}[\s-]?\d{4,}", raw_text)
    return match.group(0).strip() if match else ""


def parse_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {
        "summary": [],
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
    }

    active_section: str | None = None

    for line in lines:
        section_key = find_section_key(line)
        if section_key:
            active_section = section_key
            continue

        cleaned = normalize_line(line)
        if not cleaned:
            continue

        if active_section and not is_likely_header(cleaned):
            sections[active_section].append(cleaned)

    return sections


def split_skill_tokens(lines: list[str]) -> list[str]:
    tokens: list[str] = []
    for line in lines:
        parts = re.split(r"[,|]", line)
        tokens.extend(normalize_line(part) for part in parts)
    return [token for token in tokens if token]


def extract_detected_skills(raw_text: str, section_skills: list[str]) -> list[str]:
    detected_from_text = [skill for skill, pattern in SKILL_PATTERNS.items() if pattern.search(raw_text)]

    direct_matches: list[str] = []
    for token in split_skill_tokens(section_skills):
        for skill in SKILL_PATTERNS:
            if skill.lower() == token.lower():
                direct_matches.append(skill)
                break

    return dedupe(detected_from_text + direct_matches)


def trim_section_items(items: list[str], limit: int) -> list[str]:
    return dedupe(items)[:limit]


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_resume_text(raw_text: str) -> dict:
    lines = [normalize_line(line) for line in str(raw_text or "").splitlines()]
    lines = [line for line in lines if line]

    sections = parse_sections(lines)
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", raw_text or "", re.IGNORECASE)
    skills = extract_detected_skills(raw_text or "", sections["skills"])
    education = trim_section_items(sections["education"], 4)
    experience = trim_section_items(sections["experience"], 6)
    projects = trim_section_items(sections["projects"], 6)
    summary = " ".join(sections["summary"])[:500]

    return {
        "name": extract_name(lines),
        "email": email_match.group(0) if email_match else "",
        "phone": extract_phone(raw_text or ""),
        "skills": skills,
        "education": education,
        "experience": experience,
        "projects": projects,
        "summary": summary,
    }


def safe_upload_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")
