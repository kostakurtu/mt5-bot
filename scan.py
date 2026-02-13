"""Signal scanner only: computes Jackpot M5 trade candidates, no order sending."""

from __future__ import annotations

import time

import MetaTrader5 as mt5

from executor_mt5 import connect, has_position, shutdown
from strategy_jackpot_m5 import StrategyParams, build_trade_plan

SYMBOLS_TO_TRADE = "EURUSD,USDJPY,GBPUSD,USDCHF,USDCAD,AUDUSD"


def main() -> None:
    connect()
    symbols = [s.strip() for s in SYMBOLS_TO_TRADE.split(",") if s.strip()]
    params = StrategyParams()

    last_run = 0.0
    try:
        while True:
            now = time.time()
            if now - last_run < 1.0:
                time.sleep(0.05)
                continue
            last_run = now

            account = mt5.account_info()
            if account is None:
                print("account_info failed")
                continue

            for symbol in symbols:
                if has_position(symbol):
                    continue
                plan = build_trade_plan(symbol, params, balance=float(account.balance))
                if plan is None:
                    continue
                print(
                    f"[SCAN] {plan.symbol} {plan.side} lot={plan.lot} "
                    f"entry={plan.entry} sl={plan.sl} tp={plan.tp} sl_pips={plan.sl_pips:.4f}"
                )
    finally:
        shutdown()


if __name__ == "__main__":
    main()
