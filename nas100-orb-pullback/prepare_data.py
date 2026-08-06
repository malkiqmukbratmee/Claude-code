"""Load OANDA NAS100_USD 1-minute CSVs (UTC) and cache as a single pickle in NY time.

Source: FutureSharks/financial-data (OANDA NAS100 CFD, 1-min OHLCV with volume,
timestamps in UTC — verified via Sunday-reopen boundaries: 23:00 UTC winter /
22:00 UTC summer = 18:00 ET both seasons).
"""
import glob
import os
import sys

import pandas as pd

SRC = "/workspace/futuresharks/financial-data/pyfinancialdata/data/currencies/oanda/NAS100_USD"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "nas100_m1_ny.pkl")


def load(cache_path: str = None) -> pd.DataFrame:
    cache_path = cache_path or os.environ.get("NAS100_CACHE", "/tmp/nas100_m1_ny.pkl")
    if os.path.exists(cache_path):
        return pd.read_pickle(cache_path)
    files = sorted(glob.glob(f"{SRC}/*/oanda-NAS100_USD-*.csv"))
    if not files:
        sys.exit(f"no source CSVs found under {SRC}")
    frames = [pd.read_csv(f, parse_dates=["time"]) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    df["time"] = df["time"].dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    df = df.set_index("time")
    df.to_pickle(cache_path)
    return df


if __name__ == "__main__":
    df = load()
    print(f"rows: {len(df):,}")
    print(f"range: {df.index.min()} -> {df.index.max()}")
    print(df.head(3))
