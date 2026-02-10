from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PropRules:
    risk_per_trade: float
    max_trades_per_day: int
    max_consec_losses: int
    daily_kill_pct: float
    max_dd_kill_pct: float
    daily_soft_target_pct: float
    spread_max_pips: float


@dataclass(frozen=True)
class AccountSnapshot:
    equity: float
    balance: float
    day_start_equity: float
    peak_equity: float
    trades_today: int
    consec_losses_today: int
    floating_pnl: float


def calc_lot_by_risk(
    equity: float,
    risk_pct: float,
    entry: float,
    sl: float,
    specs: dict,
):
    point = float(specs["point"])
    trade_tick_value = float(specs["trade_tick_value"])
    trade_tick_size = float(specs["trade_tick_size"])
    volume_min = float(specs["volume_min"])
    volume_max = float(specs["volume_max"])
    volume_step = float(specs["volume_step"])

    sl_distance_price = abs(entry - sl)
    if sl_distance_price <= 0:
        raise ValueError("SL distance must be > 0")

    risk_money = equity * risk_pct
    sl_points = sl_distance_price / point
    value_per_point_per_lot = (trade_tick_value / trade_tick_size) * point
    raw_lot = risk_money / (sl_points * value_per_point_per_lot)

    stepped_lot = math.floor(raw_lot / volume_step) * volume_step
    normalized_lot = max(volume_min, min(stepped_lot, volume_max))

    return round(normalized_lot, 2)


def risk_gate(
    rules: PropRules,
    account: AccountSnapshot,
    spread_pips: float,
):
    day_pnl_pct = (account.equity - account.day_start_equity) / account.day_start_equity
    dd_pct = (account.equity - account.peak_equity) / account.peak_equity

    if spread_pips > rules.spread_max_pips:
        return False, "SPREAD_TOO_HIGH", {}
    if account.trades_today >= rules.max_trades_per_day:
        return False, "MAX_TRADES_REACHED", {}
    if account.consec_losses_today >= rules.max_consec_losses:
        return False, "MAX_CONSEC_LOSSES_REACHED", {}
    if day_pnl_pct <= rules.daily_kill_pct:
        return False, "DAILY_KILL_SWITCH", {}
    if dd_pct <= rules.max_dd_kill_pct:
        return False, "MAX_DD_KILL_SWITCH", {}
    if day_pnl_pct >= rules.daily_soft_target_pct:
        return False, "DAILY_TARGET_REACHED", {}

    return True, "ALLOW", {}
