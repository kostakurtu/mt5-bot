"""Risk and position-sizing helpers for Jackpot M5 strategy."""

from __future__ import annotations

import math


def pip_size(point: float, digits: int) -> float:
    """Return pip size from symbol point/digits.

    MQL5-equivalent behavior: for 5-digit/3-digit FX symbols, 1 pip = 10 points.
    """
    return point * 10.0 if int(digits) in (3, 5) else point


def normalize_volume(raw_lot: float, volume_min: float, volume_max: float, volume_step: float) -> float:
    """Floor raw lot to broker step and clamp to [min, max]."""
    if volume_step <= 0:
        normalized = raw_lot
    else:
        steps = math.floor(raw_lot / volume_step)
        normalized = steps * volume_step

    normalized = max(volume_min, min(normalized, volume_max))

    step_text = f"{volume_step:.10f}".rstrip("0")
    precision = len(step_text.split(".")[1]) if "." in step_text else 0
    return round(normalized, precision)


def compute_lot_by_risk(
    balance: float,
    risk_percent: float,
    sl_pips: float,
    tick_value: float,
    tick_size: float,
    point: float,
    digits: int,
    volume_min: float,
    volume_max: float,
    volume_step: float,
) -> float:
    """Compute lot size with MQL5-equivalent risk logic."""
    if sl_pips <= 0:
        raise ValueError("sl_pips must be > 0")
    if tick_size <= 0:
        raise ValueError("tick_size must be > 0")

    risk_money = balance * (risk_percent / 100.0)
    pips = pip_size(point=point, digits=digits)
    pip_value_per_lot = (tick_value / tick_size) * pips
    if pip_value_per_lot <= 0:
        raise ValueError("pip_value_per_lot must be > 0")

    raw_lot = risk_money / (sl_pips * pip_value_per_lot)
    return normalize_volume(raw_lot, volume_min, volume_max, volume_step)
