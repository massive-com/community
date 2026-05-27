from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WITHDRAW_CASH = "WITHDRAW_CASH"
    DEPOSIT_CASH = "DEPOSIT_CASH"


@dataclass(frozen=True)
class Action:
    type: ActionType
    ticker: str | None = None
    qty: int | None = None
    price: float | None = None
    amount: float | None = None


@dataclass(frozen=True)
class AccountState:
    """
    Educational simulator inputs.

    maintenance_haircut is a simplified proxy for maintenance margin requirement.
    For equities-only demo, we model required maintenance as:
      required = haircut * sum(max(position_value, 0))
    """

    starting_cash: float
    positions: Mapping[str, int]
    maintenance_haircut: float = 0.30


@dataclass(frozen=True)
class SimulationResult:
    min_iml: float
    max_intraday_margin_deficit: float
    iml_after_each_action: list[float]


def _maintenance_required(
    positions: Mapping[str, int], prices: Mapping[str, float], haircut: float
) -> float:
    total = 0.0
    for ticker, qty in positions.items():
        px = float(prices.get(ticker, 0.0))
        mv = qty * px
        if mv > 0:
            total += mv
    return haircut * total


def compute_iml(
    cash: float, positions: Mapping[str, int], prices: Mapping[str, float], haircut: float
) -> float:
    """
    Educational IML proxy:
      IML = cash - maintenance_required

    Interpretable as "cash buffer" above the simplified maintenance requirement.
    Negative => additional cash needed in this simplified model.
    """
    req = _maintenance_required(positions, prices, haircut)
    return cash - req


def simulate_day(state: AccountState, actions: list[Action]) -> SimulationResult:
    # In tests we treat each action’s provided price as the mark for that step.
    prices: dict[str, float] = {}
    positions = dict(state.positions)
    cash = float(state.starting_cash)

    imls: list[float] = []
    min_iml = float("inf")

    for a in actions:
        if a.type in (ActionType.BUY, ActionType.SELL):
            assert a.ticker is not None and a.qty is not None and a.price is not None
            prices[a.ticker] = float(a.price)

        if a.type == ActionType.BUY:
            positions[a.ticker] = int(positions.get(a.ticker, 0)) + int(a.qty)
            cash -= float(a.qty) * float(a.price)
        elif a.type == ActionType.SELL:
            positions[a.ticker] = int(positions.get(a.ticker, 0)) - int(a.qty)
            cash += float(a.qty) * float(a.price)
        elif a.type == ActionType.WITHDRAW_CASH:
            assert a.amount is not None
            cash -= float(a.amount)
        elif a.type == ActionType.DEPOSIT_CASH:
            assert a.amount is not None
            cash += float(a.amount)
        else:
            raise ValueError(f"Unsupported action type: {a.type}")

        iml = compute_iml(cash, positions, prices, state.maintenance_haircut)
        imls.append(iml)
        min_iml = min(min_iml, iml)

    if min_iml == float("inf"):
        min_iml = compute_iml(cash, positions, prices, state.maintenance_haircut)
        imls.append(min_iml)

    max_deficit = 0.0 if min_iml >= 0 else abs(min_iml)
    return SimulationResult(
        min_iml=min_iml,
        max_intraday_margin_deficit=max_deficit,
        iml_after_each_action=imls,
    )

