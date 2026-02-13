# MT5 Jackpot M5 Bot (Python)

Python recreation of **SniperBreakout M5 v4.0 STRIKE – BASE ORIGINALE (Jackpot)** logic.

## Requirements
- Python 3.10+
- MetaTrader 5 terminal installed and running
- MT5 account logged in
- Algo trading enabled in MT5 terminal
- Symbols visible in Market Watch (`EURUSD,USDJPY,GBPUSD,USDCHF,USDCAD,AUDUSD` by default)

## Install
```bash
pip install -r requirements.txt
```

## Files
- `strategy_jackpot_m5.py`: strategy signal + SL/TP + lot planning
- `executor_mt5.py`: MT5 connection, execution, FOK->IOC fallback, delayed SL/TP modify
- `risk.py`: pip size, lot sizing, volume normalization
- `scan.py`: signal scanning only (no order_send)
- `backtest.py`: offline bar replay from MT5 history (no trading)
- `live.py`: live trading loop

## Run
### Scan only
```bash
python scan.py
```

### Backtest replay (logic verification)
```bash
python backtest.py
```

### Live trading
```bash
python live.py
```

## Notes
- Strategy throttles loop to max once per second.
- One open position per symbol max.
- Orders are sent without SL/TP first, then SL/TP is set after ~200ms.
- SL/TP modify is skipped if stop-level distance is violated.
