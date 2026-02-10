"""Dry-run: teste la chaîne MT5 -> specs/spread -> risk gate -> calc lot.
Aucun ordre n'est envoyé.
"""

from __future__ import annotations

from executor_mt5 import get_spread_pips, mt5_connect, mt5_shutdown, symbol_specs
from risk import AccountSnapshot, PropRules, calc_lot_by_risk, risk_gate


def main() -> None:
    symbol = "EURUSD"
    print("=== MT5 BOT | DRY-RUN ===")
    print("Aucun ordre ne sera envoyé.\n")

    ok, msg = mt5_connect(login=None, password=None, server=None, path=None)
    print(f"Connexion MT5: {ok} | {msg}")
    if not ok:
        return

    try:
        specs = symbol_specs(symbol)
        spread_pips = get_spread_pips(symbol)

        print(f"\nSymbole: {symbol}")
        print(f"Spread actuel (pips): {spread_pips}")
        print(f"Specs: {specs}\n")

        rules = PropRules(
            risk_per_trade=0.01,
            max_trades_per_day=5,
            max_consec_losses=3,
            daily_kill_pct=-0.02,
            max_dd_kill_pct=-0.05,
            daily_soft_target_pct=0.01,
            spread_max_pips=2.0,
        )

        snapshot = AccountSnapshot(
            equity=10000.0,
            balance=10050.0,
            day_start_equity=9900.0,
            peak_equity=10100.0,
            trades_today=1,
            consec_losses_today=0,
            floating_pnl=-50.0,
        )

        allow, reason, details = risk_gate(rules, snapshot, spread_pips)
        print("=== RISK GATE ===")
        print(f"allow  : {allow}")
        print(f"reason : {reason}")
        print(f"details: {details}\n")

        entry = 1.0850
        sl = 1.0820

        lot = calc_lot_by_risk(
            equity=snapshot.equity,
            risk_pct=rules.risk_per_trade,
            entry=entry,
            sl=sl,
            specs=specs,
        )

        print("=== LOT SIZING (DRY-RUN) ===")
        print(f"Entry fictif: {entry}")
        print(f"SL fictif   : {sl}")
        print(f"Lot calculé : {lot}")
        print("\nFin dry-run. Aucun ordre n'a été placé.")

    finally:
        mt5_shutdown()
        print("MT5 shutdown effectué.")


if __name__ == "__main__":
    main()
