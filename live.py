"""Live trading loop for Jackpot M5 strategy."""

from __future__ import annotations

import time

import MetaTrader5 as mt5

from executor_mt5 import connect, has_position, open_market_then_modify, shutdown
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
                    f"[LIVE] {plan.symbol} {plan.side} lot={plan.lot} "
                    f"entry={plan.entry} sl={plan.sl} tp={plan.tp} sl_pips={plan.sl_pips:.4f}"
                )

                open_res, mod_res = open_market_then_modify(
                    symbol=plan.symbol,
                    side=plan.side,
                    lot=plan.lot,
                    sl=plan.sl,
                    tp=plan.tp,
                )

                if open_res is None or open_res.retcode not in (
                    mt5.TRADE_RETCODE_DONE,
                    mt5.TRADE_RETCODE_DONE_PARTIAL,
                    mt5.TRADE_RETCODE_PLACED,
                ):
                    if open_res is None:
                        print(f"[OPEN FAIL] {symbol} no result")
                    else:
                        print(f"[OPEN FAIL] {symbol} retcode={open_res.retcode} comment={open_res.comment}")
                    continue

                if mod_res is not None and mod_res.retcode not in (
                    mt5.TRADE_RETCODE_DONE,
                    mt5.TRADE_RETCODE_DONE_PARTIAL,
                    mt5.TRADE_RETCODE_PLACED,
                ):
                    print(f"[MODIFY FAIL] {symbol} retcode={mod_res.retcode} comment={mod_res.comment}")
    finally:
        shutdown()


if __name__ == "__main__":
    main()
