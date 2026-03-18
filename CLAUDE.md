# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Inquora Smart Inquiry Agent MVP - An engineering drawing inquiry system with a Next.js frontend and FastAPI backend.

- `apps/web`: Next.js 15 + Ant Design 6 frontend for file upload, results display, Excel/Word export
- `apps/api`: FastAPI backend for file parsing, OCR, parameter extraction, price matching

## Development Commands

### Backend (apps/api)

```powershell
cd apps/api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ocr.txt  # Optional: enables OCR support
uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/health`

### Frontend (apps/web)

```powershell
cd apps/web
npm install
npm run dev
```

Default URL: `http://localhost:3000`

### Environment Setup

Backend (`apps/api/.env`):
```env
LLM_PROVIDER=auto  # auto | openai | deepseek | none
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
CORS_ORIGINS=["http://localhost:3000"]
```

Frontend (`apps/web/.env.local`):
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## Architecture

### Backend Structure (FastAPI)

```
apps/api/
  app/
    main.py              # FastAPI app entry, CORS, router registration
    config.py            # Pydantic Settings, env var management
    models.py            # Pydantic models: InquiryItem, InquiryResult, etc.
    api/
      routes_inquiry.py  # POST /inquiry/parse, POST /inquiry/export
    services/
      pipeline.py        # InquiryPipeline: orchestrates parse → extract → price
      parsers.py         # File parsing: DXF, PDF, images, TXT/CSV/JSON + OCR
      extractor.py       # ParameterExtractor: LLM-based or heuristic extraction
      pricing.py         # PricingEngine: CSV catalog matching, price calculation
      exporters.py       # export_xlsx(), export_docx()
  data/
    price_catalog.csv    # Sample price database
```

**Request Flow:**
1. `routes_inquiry.py` receives files
2. `pipeline.py` orchestrates the process
3. `parsers.py` extracts text (DXF via ezdxf, PDF via pdfplumber, OCR via EasyOCR/pytesseract)
4. `extractor.py` extracts structured parameters (OpenAI → DeepSeek → heuristic fallback)
5. `pricing.py` matches items against CSV catalog, calculates totals, flags anomalies
6. `exporters.py` generates Excel/Word output

**Key Models:**
- `ParsedDocument`: filename, file_type, parser used, text_excerpt, warnings
- `InquiryItem`: name, category, spec, material, quantity, unit_price, total_price, anomalies
- `InquiryResult`: request_id, documents[], items[], summary, extraction_mode

### Frontend Structure (Next.js 15)

```
apps/web/
  app/
    layout.tsx           # Root layout with Ant Design ConfigProvider
    page.tsx             # Home page renders InquiryWorkbench
    globals.css          # Tailwind + CSS variables
  components/
    inquiry-workbench.tsx # Main UI: upload, results table, export buttons
  lib/
    api.ts               # parseInquiry(), exportInquiry() fetch wrappers
    types.ts             # TypeScript interfaces matching backend models
```

**API Client Pattern:**
- `lib/api.ts` exports async functions that call backend endpoints
- Uses `FormData` for file uploads
- Returns typed promises matching backend Pydantic models

## Key Dependencies

**Backend:**
- FastAPI + uvicorn (web framework)
- pydantic-settings (configuration)
- pandas, openpyxl, python-docx (data/export)
- pdfplumber (PDF parsing)
- ezdxf (DXF parsing)
- openai (LLM client)
- easyocr, pytesseract, Pillow (OCR)

**Frontend:**
- Next.js 15 + React 19
- Ant Design 6 + @ant-design/nextjs-registry
- TypeScript 5
- Tailwind CSS 3

## API Endpoints

- `POST /api/v1/inquiry/parse` - Upload files, returns structured inquiry result
- `POST /api/v1/inquiry/export?format=xlsx|docx` - Export results to Excel/Word

## File Support

**Upload formats:** DWG, DXF, PDF, images (PNG/JPG/BMP/TIFF/WEBP), TXT, CSV, JSON

**Parsing notes:**
- DXF: Parsed directly via ezdxf library
- DWG: Should use dedicated backend in production (not desktop converters)
- PDF: Text extracted via pdfplumber; image-only PDFs use OCR
- Images: OCR with configurable upscale and tiling for large drawings

## LLM Configuration

Provider priority when `LLM_PROVIDER=auto`:
1. DeepSeek (if DEEPSEEK_API_KEY set)
2. OpenAI (if OPENAI_API_KEY set)
3. Heuristic (local rule-based fallback)

Extraction modes are tracked in response (`extraction_mode` field).
