from __future__ import annotations

import logging
import math
from typing import Any

import MetaTrader5 as mt5

LOGGER = logging.getLogger(__name__)

SUCCESS_RETCODES = {
    mt5.TRADE_RETCODE_DONE,
    mt5.TRADE_RETCODE_PLACED,
    mt5.TRADE_RETCODE_DONE_PARTIAL,
}


def _log(msg: str) -> None:
    print(msg)
    LOGGER.info(msg)


def _last_error() -> dict[str, Any]:
    code, message = mt5.last_error()
    return {"code": code, "message": message}


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    if isinstance(obj, dict):
        return obj
    return {"value": obj}


def _order_response(result: Any, request: dict[str, Any] | None = None) -> dict[str, Any]:
    res = _to_dict(result)
    retcode = res.get("retcode")
    ok = retcode in SUCCESS_RETCODES
    response: dict[str, Any] = {
        "ok": ok,
        "retcode": retcode,
        "order": res.get("order"),
        "deal": res.get("deal"),
        "price": res.get("price"),
        "volume": res.get("volume"),
        "request": request if request is not None else _to_dict(res.get("request")),
        "comment": res.get("comment"),
        "last_error": _last_error(),
    }
    if not ok:
        response["reason"] = "ORDER_SEND_FAILED"
        response["details"] = res
    return response


def _ensure_symbol(symbol: str) -> tuple[Any, Any]:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol_info failed for {symbol}: {_last_error()}")

    if not info.visible:
        selected = mt5.symbol_select(symbol, True)
        if not selected:
            raise RuntimeError(f"symbol_select failed for {symbol}: {_last_error()}")
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(
                f"symbol_info unavailable after selection for {symbol}: {_last_error()}"
            )

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"symbol_info_tick failed for {symbol}: {_last_error()}")
    if tick.bid <= 0 or tick.ask <= 0:
        raise RuntimeError(f"invalid tick for {symbol}: bid={tick.bid}, ask={tick.ask}")
    return info, tick


def _norm_price(price: float, digits: int) -> float:
    return round(float(price), int(digits))


def _normalize_volume(
    volume: float, volume_min: float, volume_max: float, volume_step: float
) -> float:
    if volume_step <= 0:
        return volume
    steps = math.floor((volume - volume_min) / volume_step)
    normalized = volume_min + steps * volume_step
    normalized = max(volume_min, min(normalized, volume_max))
    precision = max(0, len(str(volume_step).split(".")[-1].rstrip("0")))
    return round(normalized, precision)


def mt5_connect(
    login: int | None,
    password: str | None,
    server: str | None,
    path: str | None,
) -> tuple[bool, str]:
    _log("Initializing MT5...")
    ok_init = mt5.initialize(path=path) if path else mt5.initialize()
    if not ok_init:
        err = _last_error()
        return False, f"mt5.initialize failed: {err}"

    if login is not None and password is not None and server is not None:
        _log(f"Logging into MT5 account {login} on {server}...")
        ok_login = mt5.login(login=login, password=password, server=server)
        if not ok_login:
            err = _last_error()
            return False, f"mt5.login failed: {err}"

    return True, "MT5 connected"


def mt5_shutdown() -> None:
    _log("Shutting down MT5...")
    mt5.shutdown()


def symbol_specs(symbol: str) -> dict:
    info, tick = _ensure_symbol(symbol)
    point = float(info.point)
    if point <= 0:
        raise RuntimeError(f"invalid point value for {symbol}: point={point}")

    spread_points = (tick.ask - tick.bid) / point
    ifuddan if spread_points < 0:
        raise RuntimeError(f"invalid spread for {symbol}: bid={tick.bid}, ask={tick.ask}")

    return {
        "digits": int(info.digits),
        "point": point,
        "trade_tick_value": float(info.trade_tick_value),
        "trade_tick_size": float(info.trade_tick_size),
        "volume_min": float(info.volume_min),
        "volume_max": float(info.volume_max),
        "volume_step": float(info.volume_step),
        "stops_level_points": int(info.trade_stops_level),
        "spread_points": float(spread_points),
        "trade_contract_size": float(getattr(info, "trade_contract_size", 0.0)),
        "freeze_level_points": int(getattr(info, "trade_freeze_level", 0)),
    }


def get_spread_pips(symbol: str) -> float:
    specs = symbol_specs(symbol)
    digits = int(specs["digits"])
    pip_factor = 10 if digits in (3, 5) else 1
    return float(specs["spread_points"]) / pip_factor


if __name__ == "__main__":
    ok, message = mt5_connect(login=None, password=None, server=None, path=None)
    print("CONNECT:", ok, message)
    if ok:
        try:
            specs = symbol_specs("EURUSD")
            print("EURUSD SPECS:", specs)
            spread = get_spread_pips("EURUSD")
            print("EURUSD SPREAD (pips):", spread)
        finally:
            mt5_shutdown()
