import pytest

from pdt_console.simulator import (
    AccountState,
    Action,
    ActionType,
    simulate_day,
)


def test_intraday_deficit_is_largest_negative_iml_magnitude():
    state = AccountState(
        starting_cash=1000.0,
        positions={"AAPL": 0},
        maintenance_haircut=0.30,
    )

    # Buy 10 shares at $200 => spend $2000, cash goes negative.
    actions = [Action(type=ActionType.BUY, ticker="AAPL", qty=10, price=200.0)]
    result = simulate_day(state, actions)

    assert result.max_intraday_margin_deficit > 0
    assert pytest.approx(result.max_intraday_margin_deficit, rel=1e-6) == abs(
        result.min_iml
    )


def test_deficit_is_zero_when_iml_never_goes_negative():
    state = AccountState(
        starting_cash=10000.0,
        positions={"AAPL": 0},
        maintenance_haircut=0.30,
    )
    actions = [Action(type=ActionType.BUY, ticker="AAPL", qty=10, price=200.0)]
    result = simulate_day(state, actions)

    assert result.min_iml >= 0
    assert result.max_intraday_margin_deficit == 0.0


def test_withdrawal_is_iml_reducing_transaction():
    state = AccountState(
        starting_cash=5000.0,
        positions={"AAPL": 0},
        maintenance_haircut=0.30,
    )
    actions = [Action(type=ActionType.WITHDRAW_CASH, amount=6000.0)]
    result = simulate_day(state, actions)

    assert result.max_intraday_margin_deficit > 0

