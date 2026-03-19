from __future__ import annotations

import logging

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi.middleware.cors import CORSMiddleware

from backend.routers.extract import router as extract_router

app = FastAPI(title="MenuExtract", version="1.0.0")

# Allow all origins during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(extract_router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
