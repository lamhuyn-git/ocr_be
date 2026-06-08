# OCR Backend API

FastAPI + PaddleOCR + PostgreSQL backend for extracting text from images and PDFs.

## Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install poppler (required for PDF support)
# macOS:
brew install poppler
# Ubuntu/Debian:
# sudo apt-get install poppler-utils

# 4. Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 5. Run database migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/ocr/upload` | Upload file, process async (returns job ID) |
| `POST` | `/api/v1/ocr/process-sync` | Upload + process synchronously (returns full result) |
| `GET` | `/api/v1/ocr/jobs` | List all jobs (paginated, filterable by status) |
| `GET` | `/api/v1/ocr/jobs/{id}` | Get job result by ID |
| `DELETE` | `/api/v1/ocr/jobs/{id}` | Delete job and its file |
| `GET` | `/health` | Health check |

Interactive docs: http://localhost:8000/docs

## Supported Languages

Pass `language` as form field. Common codes: `en`, `vi` (Vietnamese), `ch` (Chinese), `fr`, `de`, `ja`, `ko`.

## Supported File Types

Images: `jpg`, `jpeg`, `png`, `bmp`, `tiff`, `webp`  
Documents: `pdf`
