# NAS100 30-min NY ORB — Pullback Statistics

Statistical study of pullbacks after the first 15-minute candle closes outside
the 09:30–10:00 ET opening range on NAS100 (US Tech 100 CFD).

**Findings: see [REPORT.md](REPORT.md).** Raw per-event data: `events.csv`
(3,683 events, 2005–2020).

## Reproduce

```bash
pip install pandas numpy scipy tabulate
# 1-min source data: OANDA NAS100_USD from github.com/FutureSharks/financial-data
git clone --depth 1 https://github.com/FutureSharks/financial-data /workspace/futuresharks/financial-data
python3 extract_events.py   # builds events.csv from 1-min bars
python3 analyze.py          # writes REPORT.md
```

Pipeline: `prepare_data.py` (load + UTC→NY tz) → `extract_events.py`
(ORB / acceptance / pullback measurement per session) → `analyze.py`
(percentiles, Wilson CIs, bootstrap, Kruskal–Wallis / Mann–Whitney).
