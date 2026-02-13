"""Strategy logic for SniperBreakout M5 v4.0 STRIKE - BASE ORIGINALE (Jackpot)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    df = pd.DataFrame(rates)
    return df


def _last_closed_sma(symbol: str, timeframe: int, period: int) -> float:
    bars = max(period + 5, 120)
    df = _rates_df(symbol, timeframe, bars)
    sma = df["close"].rolling(period).mean()
    value = float(sma.iloc[-2])
    if pd.isna(value):
        raise RuntimeError(f"SMA unavailable {symbol} tf={timeframe} period={period}")
    return value


def build_trade_plan(symbol: str, params: StrategyParams, balance: float) -> TradePlan | None:
    m5 = _rates_df(symbol, mt5.TIMEFRAME_M5, 120)

    open_1 = float(m5["open"].iloc[-2])
    close_1 = float(m5["close"].iloc[-2])

    if close_1 > open_1:
        side = "BUY"
    elif close_1 < open_1:
        side = "SELL"
    else:
        return None

    ma_fast_m5 = _last_closed_sma(symbol, mt5.TIMEFRAME_M5, params.ma_fast)
    ma_slow_m5 = _last_closed_sma(symbol, mt5.TIMEFRAME_M5, params.ma_slow)
    ma_fast_m15 = _last_closed_sma(symbol, mt5.TIMEFRAME_M15, params.ma_fast)
    ma_slow_m15 = _last_closed_sma(symbol, mt5.TIMEFRAME_M15, params.ma_slow)

    if side == "BUY" and (ma_fast_m5 <= ma_slow_m5 or ma_fast_m15 <= ma_slow_m15):
        return None
    if side == "SELL" and (ma_fast_m5 >= ma_slow_m5 or ma_fast_m15 >= ma_slow_m15):
        return None

    constraints = get_constraints(symbol)
    point_pips = pip_size(constraints.point, constraints.digits)

    tick = symbol_tick(symbol)
    entry = float(tick.ask if side == "BUY" else tick.bid)

    raw_sl = float(m5["low"].iloc[-2] - 2 * constraints.point) if side == "BUY" else float(m5["high"].iloc[-2] + 2 * constraints.point)

    sl_pips_uncapped = abs(entry - raw_sl) / point_pips
    sl_pips = min(sl_pips_uncapped, params.sl_max_pips)

    if side == "BUY":
        sl = entry - sl_pips * point_pips
        tp = entry + params.tp1_pips * point_pips
    else:
        sl = entry + sl_pips * point_pips
        tp = entry - params.tp1_pips * point_pips

    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info failed for {symbol}")

    lot = compute_lot_by_risk(
        balance=balance,
        risk_percent=params.risk_percent,
        sl_pips=sl_pips,
        tick_value=float(info.trade_tick_value),
        tick_size=float(info.trade_tick_size),
        point=constraints.point,
        digits=constraints.digits,
        volume_min=constraints.volume_min,
        volume_max=constraints.volume_max,
        volume_step=constraints.volume_step,
    )

    return TradePlan(
        symbol=symbol,
        side=side,
        lot=lot,
        entry=round(entry, constraints.digits),
        sl=round(sl, constraints.digits),
        tp=round(tp, constraints.digits),
        sl_pips=sl_pips,
    )
