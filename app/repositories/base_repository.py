"""Repository abstraction reserved for Stage 2 database models."""
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Placeholder for persistence operations independent from Qt views."""
