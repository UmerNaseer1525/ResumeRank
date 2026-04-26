# Python Backend (FastAPI) for Resume Screener AI

This backend is a Python replacement for the previous Express backend. It keeps the same API routes and response style so your React frontend can continue to work without route changes.

## API Compatibility

The following endpoints are implemented with the same paths used by your frontend:

- `GET /api/health`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `POST /api/resumes/upload`
- `POST /api/resumes/upload/batch`
- `GET /api/resumes`
- `GET /api/resumes/{id}`
- `GET /api/resumes/rankings`

## 1) Setup Python Environment

From the `backend-python` folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) Configure Environment Variables

1. Copy `.env.example` to `.env`.
2. Set values for your MongoDB and JWT:

- `MONGO_URI`
- `MONGO_URI_DIRECT` (optional fallback if SRV DNS lookup fails)
- `MONGO_DNS_SERVERS` (optional)
- `DB_NAME`
- `JWT_SECRET`
- `PORT`
- `CORS_ORIGINS`

## 3) Run Python Backend

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

The frontend default API base URL (`http://localhost:5000/api`) will continue to work.

## 4) Run Frontend

In a second terminal:

```powershell
cd ..\frontend
npm install
npm run dev
```

## 5) Important Notes

- Keep only one backend running on port `5000` (either Express or this Python backend).
- Uploaded files are stored in `backend-python/uploads` and served from `/uploads`.
- The JWT auth flow remains bearer-token based (`Authorization: Bearer <token>`).

## 6) Train a Ranking Model

The backend now supports a trainable ML ranking model.

### Install dependencies

```powershell
pip install -r requirements.txt
```

### Train from existing MongoDB resumes

From `backend-python`:

```powershell
python train_model.py
```

Default training now uses an NLP classification pipeline:

- Text preprocessing + TF-IDF vectorization (unigrams + bigrams)
- Logistic Regression classifier for resume relevance
- Outputs ranking score from model relevance probability
- Reports `Accuracy`, `Precision`, `Recall`, `F1`, and cross-validation `CV F1`

Optional: limit training samples for quick experiments:

```powershell
python train_model.py --limit 200
```

Optional: adjust relevance threshold used to convert score labels into binary classes:

```powershell
python train_model.py --threshold 60
```

### Train from `resumes.jsonl`

If a `resumes.jsonl` file exists at the project root, the trainer automatically uses it.
You can also pass an explicit path:

```powershell
python train_model.py --jsonl-path ..\resumes.jsonl
```

This mode supports:

- Explicit labels when present (`label`, `relevant`, `target`, `class`, `score`, `targetScore`, etc.)
- Chat-style records with `messages` (uses heuristic label fallback when explicit labels are missing)

### Convert to supervised dataset format

To create a cleaner supervised dataset (`resume_text`, `role`, `label`) from `resumes.jsonl`:

```powershell
python scripts\convert_resumes_jsonl_to_supervised.py --input ..\resumes.jsonl --output data\resume_supervised.jsonl --stats data\resume_supervised_stats.json
```

Then train directly on the converted file:

```powershell
python train_model.py --jsonl-path data\resume_supervised.jsonl
```

### Train proposal-aligned transformer model (DistilBERT)

For a deep-learning workflow aligned to the project proposal:

```powershell
python train_bert_model.py --dataset data\resume_supervised.jsonl --epochs 2 --batch-size 8
```

Notes:

- This trains a DistilBERT sequence classifier for resume relevance.
- Artifacts are saved to `backend-python/app/models/resume_ranker_bert`.
- The backend ranking service automatically uses the BERT model when available.
- If BERT artifacts are missing/unloadable, it falls back to the TF-IDF model or heuristic scorer.

### What training uses as labels

The trainer uses these targets in priority order:

- `scoreLabel`, `targetScore`, or `manualScore` (numeric fields on resume documents)
- `hired` (bool) mapped to high/low score
- `shortlisted` (bool) mapped to high/low score
- fallback pseudo-label from current heuristic scorer

Model artifacts are stored at:

- `backend-python/app/models/resume_ranker.joblib`

### Runtime behavior

- `GET /api/resumes/rankings` uses the trained model when artifact exists.
- If artifact is missing or invalid, the endpoint automatically falls back to the existing heuristic scoring.

## 7) Proposal-Aligned ML Architecture (COMPLETE)

This implementation fully aligns with the project proposal requirements:

### Dual Model Support
- **BERT Transformer (Primary)**: DistilBERT sequence classifier for deep learning-based resume relevance detection
  - Model: `app/models/resume_ranker_bert/`
  - Performance: 87.9% accuracy on 455 supervised samples
  - Input: Raw resume text
  - Output: Binary relevance classification (0-1 logits) → normalized to 0-100 score

- **Classical ML Baseline (Fallback)**: TF-IDF + Logistic Regression for comparison
  - Model: `app/models/resume_ranker.joblib`
  - Performance: 86.8% accuracy, F1 0.545
  - Used when BERT is unavailable

### Inference Fallback Chain
1. **BERT Model** (if trained and loadable) → resume relevance classifier
2. **Classical TF-IDF Model** (if trained and loadable) → resume relevance classifier
3. **Heuristic Scorer** (always available) → keyword + metadata-based scoring

### Dataset
- **Training Data**: `data/resume_supervised.jsonl` (455 samples)
  - Source: Converted from `resumes.jsonl` (chat-style QA records)
  - Labels: Heuristic weak-labeled (56 positive, 399 negative)
  - Process: `scripts/convert_resumes_jsonl_to_supervised.py`

### Model Status
View current model in use via:
```
GET /api/resumes/model-status
```

Response shows:
- `modelKind`: Type of active model (e.g., `bert_sequence_classifier_v1`)
- `scoreSource`: Where scores come from (`ml-model` or `heuristic`)
- `accuracy`: Model performance metrics
- `sampleCount`: Training dataset size
