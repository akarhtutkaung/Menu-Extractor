# MenuExtract

Upload any restaurant menu (PDF, JPG, or PNG) and get a clean, structured, translated JSON menu instantly.

## Features

- Accepts PDF, JPG, and PNG menu files
- Handles both text-based PDFs and scanned/photo menus
- Detects language and translates item names to English
- Extracts categories, prices, descriptions, tags (spicy, gluten-free, etc.), and drink sizes
- Adaptive image rendering: scores embedded image quality to choose the right DPI/JPEG tier to save memory

---

## Requirements

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys) with GPT-4o access

---

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd MenuExtract

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

`.env` variables:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model to use for extraction |
| `OPENAI_TIMEOUT_SECONDS` | `60` | Timeout for OpenAI requests |
| `MAX_FILE_SIZE_MB` | `10` | Maximum upload size |

---

## Running

Backend
```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Frontend
```bash
source venv/bin/activate
python3 -m http.server 3000 --directory frontend
```

Then open `http://localhost:3000` in your browser.

---

## API

### `POST /api/extract`

Upload a menu file and receive a structured menu JSON.

**Request:** `multipart/form-data` with a `file` field (PDF, JPG, or PNG — max 10 MB).

**Response:**

```json
{
  "restaurant_name": "string | null",
  "detected_language": "string | null",
  "language_code": "string | null",
  "categories": [
    {
      "name": "string",
      "items": [
        {
          "name_original": "string | null",
          "name_english": "string | null",
          "description": "string | null",
          "price": "number | null",
          "currency": "string | null",
          "tags": ["string"],
          "sizes": ["string"]
        }
      ]
    }
  ]
}
```

**Error responses:**

| Status | `error` code | Cause |
|---|---|---|
| 400 | `invalid_file_type` | File is not a PDF, JPG, or PNG |
| 400 | `file_too_large` | Exceeds `MAX_FILE_SIZE_MB` |
| 500 | `extraction_failed` | File parse or OpenAI error |
| 504 | `timeout` | OpenAI request timed out |

### `GET /health`

```json
{ "status": "ok" }
```

---

## Architecture

```
MenuExtract/
├── backend/
│   ├── main.py               # FastAPI app, mounts frontend, registers /api router
│   ├── config.py             # Typed settings loaded from .env
│   ├── routers/
│   │   └── extract.py        # POST /api/extract — validates upload, runs pipeline
│   ├── services/
│   │   ├── pdf_processor.py   # PDF extraction + adaptive image rendering
│   │   ├── image_processor.py # JPG/PNG normalisation to JPEG for vision API
│   │   └── openai_client.py   # GPT-4o calls (text + vision), response merging
│   └── models/
│       └── menu.py           # Pydantic models: MenuItem, Category, MenuResponse
└── frontend/
    ├── index.html            # Single-page UI
    ├── css/styles.css        # CSS custom properties, four UI state styles
    └── js/
        ├── app.js            # State machine wiring, copy/download actions
        ├── uploader.js       # File input + drag-and-drop, client-side validation
        ├── renderer.js       # DOM building from MenuResponse JSON
        └── api.js            # fetch wrapper for /api/extract
```