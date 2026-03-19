from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class MenuItem(BaseModel):
    name_original: Optional[str] = None
    name_english: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    tags: list[str] = []
    sizes: list[str] = []


class Category(BaseModel):
    name: str
    items: list[MenuItem]


class MenuResponse(BaseModel):
    restaurant_name: Optional[str] = None
    detected_language: Optional[str] = None
    language_code: Optional[str] = None
    categories: list[Category] = []
