from __future__ import annotations

from pydantic import BaseModel


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
