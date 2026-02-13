# executor_mt5.py
"""MT5 execution layer: open market order, then modify SL/TP after delay.

Corrections:
- Use the *position ticket* for TRADE_ACTION_SLTP (do NOT use order/deal id).
- Prefer matching the opened position by magic + comment; fallback to most recent
  position on the symbol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import MetaTrader5 as mt5


SUCCESS_RETCODES = {
    mt5.TRADE_RETCODE_DONE,
    mt5.TRADE_RETCODE_DONE_PARTIAL,
    mt5.TRADE_RETCODE_PLACED,
}


@dataclass(frozen=True)
class SymbolConstraints:
    point: float
    digits: int
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level_points: int


def last_error_text() -> str:
    code, msg = mt5.last_error()
    return f"{code}: {msg}"


def ensure_symbol(symbol: str) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info failed {symbol}: {last_error_text()}")
    if not info.visible and not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"symbol_select failed {symbol}: {last_error_text()}")


def connect(
    login: int | None = None,
    password: str | None = None,
    server: str | None = None,
    path: str | None = None,
) -> None:
    ok = mt5.initialize(path=path) if path else mt5.initialize()
    if not ok:
        raise RuntimeError(f"mt5.initialize failed: {last_error_text()}")
    if login is not None and password is not None and server is not None:
        if not mt5.login(login=login, password=password, server=server):
            raise RuntimeError(f"mt5.login failed: {last_error_text()}")


def shutdown() -> None:
    mt5.shutdown()


def get_constraints(symbol: str) -> SymbolConstraints:
    ensure_symbol(symbol)
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info unavailable for {symbol}")
    return SymbolConstraints(
        point=float(info.point),
        digits=int(info.digits),
        volume_min=float(info.volume_min),
        volume_max=float(info.volume_max),
        volume_step=float(info.volume_step),
        stops_level_points=int(info.trade_stops_level),
    )


def symbol_tick(symbol: str) -> Any:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"symbol_info_tick failed {symbol}: {last_error_text()}")
    return tick


def has_position(symbol: str) -> bool:
    positions = mt5.positions_get(symbol=symbol)
    return positions is not None and len(positions) > 0


def _send_with_fok_ioc_fallback(request: dict[str, Any]) -> Any:
    """Try FOK, fallback to IOC."""
    request_fok = dict(request)
    request_fok["type_filling"] = mt5.ORDER_FILLING_FOK
    result = mt5.order_send(request_fok)
    if result is not None and result.retcode in SUCCESS_RETCODES:
        return result

    request_ioc = dict(request)
    request_ioc["type_filling"] = mt5.ORDER_FILLING_IOC
    return mt5.order_send(request_ioc)


def _pick_position_ticket(symbol: str, magic: int, comment: str) -> Optional[int]:
    """Return a position ticket for TRADE_ACTION_SLTP.

    In MT5 Python, modifying SL/TP requires a *position ticket*.
    order/deal ids are not reliable substitutes.
    """
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return None

    # Prefer magic + comment match
    matched = []
    for p in positions:
        pmagic = getattr(p, "magic", None)
        pcomment = getattr(p, "comment", "")
        if pmagic == magic and (comment in pcomment):
            matched.append(p)

    if matched:
        matched.sort(key=lambda x: getattr(x, "time", 0))
        return int(matched[-1].ticket)

    # Fallback: most recent position on the symbol
    positions = list(positions)
    positions.sort(key=lambda x: getattr(x, "time", 0))
    return int(positions[-1].ticket)


def open_market_then_modify(
    symbol: str,
    side: str,
    lot: float,
    sl: float,
    tp: float,
    magic: int = 440040,
    comment: str = "jackpot_m5",
) -> tuple[Any, Any | None]:
    """Open market order without SL/TP, then set SL/TP after 200ms if stop-level allows."""
    ensure_symbol(symbol)
    constraints = get_constraints(symbol)
    tick = symbol_tick(symbol)

    is_buy = side.upper() == "BUY"
    order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
    entry = float(tick.ask if is_buy else tick.bid)

    open_request: dict[str, Any] = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": round(entry, constraints.digits),
        "deviation": 20,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
    }

    open_result = _send_with_fok_ioc_fallback(open_request)
    if open_result is None or open_result.retcode not in SUCCESS_RETCODES:
        return open_result, None

    # mimic human delay
    time.sleep(0.2)

    stop_level_price_dist = constraints.stops_level_points * constraints.point
    if abs(entry - sl) < stop_level_price_dist or abs(tp - entry) < stop_level_price_dist:
        return open_result, None

    ticket = _pick_position_ticket(symbol=symbol, magic=magic, comment=comment)
    if ticket is None:
        return open_result, None

    modify_request: dict[str, Any] = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": int(ticket),
        "sl": round(float(sl), constraints.digits),
        "tp": round(float(tp), constraints.digits),
        "magic": magic,
        "comment": comment,
    }
    modify_result = mt5.order_send(modify_request)
    return open_result, modify_result
