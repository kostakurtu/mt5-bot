# strategy_jackpot_m5.py
"""Strategy logic for SniperBreakout M5 v4.0 STRIKE - BASE ORIGINALE (Jackpot).

Correction/optimisation:
- Fetch M5 and M15 rates once each and compute SMA from those series.
- Keep exact MQL5 semantics (use last CLOSED bar: shift=1 => iloc[-2]).
"""

from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5
import pandas as pd

from executor_mt5 import get_constraints, symbol_tick
from risk import compute_lot_by_risk, pip_size


@dataclass(frozen=True)
class StrategyParams:
    risk_percent: float = 1.0
    tp1_pips: float = 5.0
    ma_fast: int = 9
    ma_slow: int = 100
    sl_max_pips: float = 12.0


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    side: str
    lot: float
    entry: float
    sl: float
    tp: float
    sl_pips: float


def _rates_df(symbol: str, timeframe: int, bars: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates for {symbol} tf={timeframe}")
    return pd.DataFrame(rates)


def build_trade_plan(symbol: str, params: StrategyParams, balance: float) -> TradePlan | None:
    # Ensure enough bars for MA_Slow on both TFs
    bars = max(params.ma_slow + 20, 150)

    m5 = _rates_df(symbol, mt5.TIMEFRAME_M5, bars)
    m15 = _rates_df(symbol, mt5.TIMEFRAME_M15, bars)

    # Direction from last CLOSED M5 bar (MQL5 iClose/iOpen shift=1)
    open_1 = float(m5["open"].iloc[-2])
    close_1 = float(m5["close"].iloc[-2])

    if close_1 > open_1:
        side = "BUY"
    elif close_1 < open_1:
        side = "SELL"
    else:
        return None

    # SMA on PRICE_CLOSE, last CLOSED bar
    m5_fast = float(m5["close"].rolling(params.ma_fast).mean().iloc[-2])
    m5_slow = float(m5["close"].rolling(params.ma_slow).mean().iloc[-2])
    m15_fast = float(m15["close"].rolling(params.ma_fast).mean().iloc[-2])
    m15_slow = float(m15["close"].rolling(params.ma_slow).mean().iloc[-2])

    if pd.isna(m5_fast) or pd.isna(m5_slow) or pd.isna(m15_fast) or pd.isna(m15_slow):
        return None

    # Trend confluence filter (exact MQL5 logic)
    if side == "BUY" and (m5_fast <= m5_slow or m15_fast <= m15_slow):
        return None
    if side == "SELL" and (m5_fast >= m5_slow or m15_fast >= m15_slow):
        return None

    constraints = get_constraints(symbol)
    point_pips = pip_size(constraints.point, constraints.digits)

    tick = symbol_tick(symbol)
    entry = float(tick.ask if side == "BUY" else tick.bid)

    # Raw SL from previous CLOSED M5 candle low/high with 2 points buffer
    prev_low = float(m5["low"].iloc[-2])
    prev_high = float(m5["high"].iloc[-2])
    raw_sl = (prev_low - 2 * constraints.point) if side == "BUY" else (prev_high + 2 * constraints.point)

    # Cap SL distance in pips (and recompute SL from entry for consistent risk math)
    sl_pips_uncapped = abs(entry - raw_sl) / point_pips
    sl_pips = min(float(sl_pips_uncapped), float(params.sl_max_pips))

    if side == "BUY":
        sl = entry - sl_pips * point_pips
        tp = entry + float(params.tp1_pips) * point_pips
    else:
        sl = entry + sl_pips * point_pips
        tp = entry - float(params.tp1_pips) * point_pips

    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info failed for {symbol}")

    lot = compute_lot_by_risk(
        balance=float(balance),
        risk_percent=float(params.risk_percent),
        sl_pips=float(sl_pips),
        tick_value=float(info.trade_tick_value),
        tick_size=float(info.trade_tick_size),
        point=float(constraints.point),
        digits=int(constraints.digits),
        volume_min=float(constraints.volume_min),
        volume_max=float(constraints.volume_max),
        volume_step=float(constraints.volume_step),
    )

    return TradePlan(
        symbol=symbol,
        side=side,
        lot=float(lot),
        entry=round(entry, constraints.digits),
        sl=round(sl, constraints.digits),
        tp=round(tp, constraints.digits),
        sl_pips=float(sl_pips),
    )
