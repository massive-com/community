from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulatedAccount:
    account_id: str


__all__ = ["SimulatedAccount"]

