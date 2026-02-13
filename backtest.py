"""Offline bar replay for Jackpot M5 strategy logic using MT5 rates (no trading)."""

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


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _lot_for_bar(balance: float, sl_pips: float, tick_value: float, tick_size: float, point: float, digits: int, info: Any) -> float:
    pips = pip_size(point, digits)
    pip_value_per_lot = (tick_value / tick_size) * pips
    raw = (balance * (RISK_PERCENT / 100.0)) / (sl_pips * pip_value_per_lot)
    return normalize_volume(raw, float(info.volume_min), float(info.volume_max), float(info.volume_step))


def run_backtest(symbol: str, bars: int = 2000) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"[BACKTEST] skip {symbol}: symbol_info unavailable")
        return

    m5_raw = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, bars)
    m15_raw = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, max(500, bars // 3))
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
    balance = 10000.0

    for i in range(MA_SLOW + 2, len(m5)):
        bar = m5.iloc[i - 1]
        t = m5.index[i - 1]
        m15_row = m15[m15.index <= t].iloc[-1] if not m15[m15.index <= t].empty else None
        if m15_row is None:
            continue

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

        if side == "BUY" and (ma_fast_m5 <= ma_slow_m5 or ma_fast_m15 <= ma_slow_m15):
            continue
        if side == "SELL" and (ma_fast_m5 >= ma_slow_m5 or ma_fast_m15 >= ma_slow_m15):
            continue

        entry = float(bar["close"])
        raw_sl = float(bar["low"] - 2 * point) if side == "BUY" else float(bar["high"] + 2 * point)
        sl_pips = min(abs(entry - raw_sl) / point_pips, SL_MAX_PIPS)
        sl = entry - sl_pips * point_pips if side == "BUY" else entry + sl_pips * point_pips
        tp = entry + TP1_PIPS * point_pips if side == "BUY" else entry - TP1_PIPS * point_pips

        lot = _lot_for_bar(
            balance=balance,
            sl_pips=sl_pips,
            tick_value=float(info.trade_tick_value),
            tick_size=float(info.trade_tick_size),
            point=point,
            digits=digits,
            info=info,
        )

        print(
            f"[BACKTEST] {symbol} {t} {side} lot={lot} "
            f"entry={round(entry, digits)} sl={round(sl, digits)} tp={round(tp, digits)} sl_pips={sl_pips:.4f}"
        )


def self_check() -> None:
    assert pip_size(0.00001, 5) == 0.0001
    assert pip_size(0.001, 3) == 0.01
    step = 0.01
    lot = normalize_volume(0.127, 0.01, 100.0, step)
    rem = round((lot / step) - round(lot / step), 8)
    assert abs(rem) <= 1e-6


def main() -> None:
    self_check()
    if not mt5.initialize():
        raise RuntimeError("mt5.initialize failed")

    try:
        for symbol in [s.strip() for s in SYMBOLS_TO_TRADE.split(",") if s.strip()]:
            run_backtest(symbol)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
