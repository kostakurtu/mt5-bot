# backtest.py
"""Offline bar replay for Jackpot M5 strategy logic using MT5 rates (no trading).

Correction:
- Use a simulated Bid/Ask entry instead of bar close (mid proxy) to better mimic live execution:
  * mid ≈ close
  * spread_price = info.spread * point
  * BUY entry ≈ close + spread_price/2 (ask)
  * SELL entry ≈ close - spread_price/2 (bid)

Notes:
- This is still a *logic replay* (not a broker-accurate PnL backtest).
- We also optionally skip plans that would violate stops_level distance (like live modify guard).
"""

from __future__ import annotations

import math
from typing import Any

import MetaTrader5 as mt5
import pandas as pd

from risk import normalize_volume, pip_size

SYMBOLS_TO_TRADE = "EURUSD,USDJPY,GBPUSD,USDCHF,USDCAD,AUDUSD"
RISK_PERCENT = 1.0
TP1_PIPS = 5.0
MA_FAST = 9
MA_SLOW = 100
SL_MAX_PIPS = 12.0

# If True, skip printing trades where SL/TP distances would violate broker stop level
ENFORCE_STOP_LEVEL = True


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _lot_for_bar(
    balance: float,
    sl_pips: float,
    tick_value: float,
    tick_size: float,
    point: float,
    digits: int,
    info: Any,
) -> float:
    pips = pip_size(point, digits)
    pip_value_per_lot = (tick_value / tick_size) * pips
    raw = (balance * (RISK_PERCENT / 100.0)) / (sl_pips * pip_value_per_lot)
    return normalize_volume(raw, float(info.volume_min), float(info.volume_max), float(info.volume_step))


def _spread_price(info: Any, point: float) -> float:
    # info.spread is typically in points (integer). If 0 (some CFDs), fallback to 2 points.
    sp = getattr(info, "spread", 0)
    try:
        sp_points = float(sp)
    except Exception:
        sp_points = 0.0
    if sp_points <= 0:
        sp_points = 2.0
    return sp_points * point


def _entry_from_close(side: str, close_mid: float, spread_price: float) -> float:
    half = spread_price / 2.0
    if side == "BUY":
        return close_mid + half  # ask
    return close_mid - half      # bid


def run_backtest(symbol: str, bars: int = 2000) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"[BACKTEST] skip {symbol}: symbol_info unavailable")
        return

    m5_raw = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, bars)
    m15_raw = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, max(600, bars // 3))
    if m5_raw is None or m15_raw is None:
        print(f"[BACKTEST] skip {symbol}: no rates")
        return

    m5 = pd.DataFrame(m5_raw)
    m15 = pd.DataFrame(m15_raw)
    if m5.empty or m15.empty:
        return

    m5["time"] = pd.to_datetime(m5["time"], unit="s")
    m15["time"] = pd.to_datetime(m15["time"], unit="s")
    m5.set_index("time", inplace=True)
    m15.set_index("time", inplace=True)

    m5["ma_fast"] = _sma(m5["close"], MA_FAST)
    m5["ma_slow"] = _sma(m5["close"], MA_SLOW)
    m15["ma_fast"] = _sma(m15["close"], MA_FAST)
    m15["ma_slow"] = _sma(m15["close"], MA_SLOW)

    point = float(info.point)
    digits = int(info.digits)
    point_pips = pip_size(point, digits)

    # backtest balance default (logic replay)
    balance = 10000.0

    spread_price = _spread_price(info, point)
    stop_level_price_dist = float(getattr(info, "trade_stops_level", 0)) * point

    for i in range(MA_SLOW + 2, len(m5)):
        # Last CLOSED M5 bar (equivalent to shift=1 in MQL5 relative to a new tick)
        bar = m5.iloc[i - 1]
        t = m5.index[i - 1]

        m15_slice = m15[m15.index <= t]
        if m15_slice.empty:
            continue
        m15_row = m15_slice.iloc[-1]

        # direction from last closed M5 candle (close vs open)
        if bar["close"] > bar["open"]:
            side = "BUY"
        elif bar["close"] < bar["open"]:
            side = "SELL"
        else:
            continue

        ma_fast_m5 = float(bar["ma_fast"])
        ma_slow_m5 = float(bar["ma_slow"])
        ma_fast_m15 = float(m15_row["ma_fast"])
        ma_slow_m15 = float(m15_row["ma_slow"])

        if any(math.isnan(v) for v in (ma_fast_m5, ma_slow_m5, ma_fast_m15, ma_slow_m15)):
            continue

        # confluence filter (exact)
        if side == "BUY" and (ma_fast_m5 <= ma_slow_m5 or ma_fast_m15 <= ma_slow_m15):
            continue
        if side == "SELL" and (ma_fast_m5 >= ma_slow_m5 or ma_fast_m15 >= ma_slow_m15):
            continue

        # Simulated entry using bid/ask from close(mid) + spread
        close_mid = float(bar["close"])
        entry = _entry_from_close(side, close_mid, spread_price)

        # raw SL from prev candle low/high + 2 points buffer
        raw_sl = float(bar["low"] - 2 * point) if side == "BUY" else float(bar["high"] + 2 * point)

        # cap SL distance in pips and recompute SL from entry for consistent risk sizing
        sl_pips = min(abs(entry - raw_sl) / point_pips, SL_MAX_PIPS)
        sl = entry - sl_pips * point_pips if side == "BUY" else entry + sl_pips * point_pips
        tp = entry + TP1_PIPS * point_pips if side == "BUY" else entry - TP1_PIPS * point_pips

        if ENFORCE_STOP_LEVEL and stop_level_price_dist > 0:
            if abs(entry - sl) < stop_level_price_dist or abs(tp - entry) < stop_level_price_dist:
                continue

        lot = _lot_for_bar(
            balance=balance,
            sl_pips=sl_pips,
            tick_value=float(info.trade_tick_value),
            tick_size=float(info.trade_tick_size),
            point=po
