"""Aggregates all route modules into a single router mounted in `main.py`."""
from fastapi import APIRouter

from app.api.routes.parse import router as parse_router
from app.api.routes.pdf import router as pdf_router

api_router = APIRouter()
api_router.include_router(parse_router)
api_router.include_router(pdf_router)
