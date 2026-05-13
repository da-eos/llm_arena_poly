import math

import pytest

from app.services.scoring import brier_score, log_loss, pnl_demo


def test_brier_perfect_yes():
    assert brier_score(1.0, True) == 0.0


def test_brier_perfect_no():
    assert brier_score(0.0, False) == 0.0


def test_brier_worst():
    assert brier_score(1.0, False) == pytest.approx(1.0)
    assert brier_score(0.0, True) == pytest.approx(1.0)


def test_brier_midpoint():
    assert brier_score(0.5, True) == pytest.approx(0.25)
    assert brier_score(0.5, False) == pytest.approx(0.25)


def test_log_loss_perfect():
    # log(1-eps) is very near 0
    assert log_loss(1.0, True) == pytest.approx(0.0, abs=1e-5)
    assert log_loss(0.0, False) == pytest.approx(0.0, abs=1e-5)


def test_log_loss_clipped():
    # Without clipping log(0) would be -inf; clipping keeps it finite.
    val = log_loss(0.0, True)
    assert math.isfinite(val)
    assert val > 10  # large but finite


def test_log_loss_midpoint():
    assert log_loss(0.5, True) == pytest.approx(math.log(2))
    assert log_loss(0.5, False) == pytest.approx(math.log(2))


def test_pnl_winning_yes_side():
    # Model says YES is more likely than market, and outcome was YES.
    # Bet $100 on YES at market price 0.1 → payout = 100 * (1/0.1 - 1) = 900.
    assert pnl_demo(0.5, 0.1, True) == pytest.approx(900.0)


def test_pnl_losing_yes_side():
    # Same side choice but outcome NO → lose stake.
    assert pnl_demo(0.5, 0.1, False) == pytest.approx(-100.0)


def test_pnl_winning_no_side():
    # Model thinks YES less likely than market → bets NO at price 1-0.9=0.1.
    # Outcome NO → payout = 100 * (1/0.1 - 1) = 900.
    assert pnl_demo(0.5, 0.9, False) == pytest.approx(900.0)


def test_pnl_losing_no_side():
    assert pnl_demo(0.5, 0.9, True) == pytest.approx(-100.0)


def test_pnl_degenerate_price_no_bet():
    assert pnl_demo(0.5, 0.0, True) == 0.0
    assert pnl_demo(0.5, 1.0, True) == 0.0
    assert pnl_demo(0.5, None, True) == 0.0
