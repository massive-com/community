from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: float
    as_of_ms: int | None = None


__all__ = ["Quote"]

