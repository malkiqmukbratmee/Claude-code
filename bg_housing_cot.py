"""
Bulgarian Housing COT Indicator.

Williams COT Index applied to three Bulgarian housing positioning series:

  Retailers       — БНБ new household mortgage origination (monthly)
                    ECB SDW: BSI.M.BG.N.A.A22.A.1.U2.2250.Z01.E
  Commercials     — НСИ building permits, dwellings count (quarterly)
                    Eurostat: sts_cobp_q
  Non-commercials — БНБ loans to non-financial corporations,
                    real estate activities (monthly)
                    ECB SDW: BSI.M.BG.N.A.A22.A.1.U2.4S.Z01.E

  Price reference — НСИ House Price Index (quarterly)
                    Eurostat: prc_hpi_q

Indicator: Williams COT Index = (x - min) / (max - min) * 100
           Lookback = 26 quarters, thresholds at 80 / 20.

Run modes:
  Default            — synthetic data calibrated to published BG stats
  LIVE=1 python ...  — fetch real series (needs unrestricted network)
"""

import io
import os
import urllib.request
from dataclasses import dataclass

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


LOOKBACK_QUARTERS = 26
UPPER_THRESHOLD = 80
LOWER_THRESHOLD = 20

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data"


# ---------- Live fetchers (used when LIVE=1) ----------

def _fetch_eurostat(dataset: str, params: dict) -> pd.Series:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{EUROSTAT_BASE}/{dataset}?format=JSON&{qs}"
    with urllib.request.urlopen(url, timeout=30) as r:
        payload = pd.read_json(io.BytesIO(r.read()), typ="series").to_dict()
    times = list(payload["dimension"]["time"]["category"]["index"].keys())
    values = payload["value"]
    return pd.Series(
        {pd.Period(times[int(i)], freq="Q").to_timestamp(): v for i, v in values.items()}
    ).sort_index()


def _fetch_ecb(series_key: str) -> pd.Series:
    url = f"{ECB_BASE}/{series_key}?format=csvdata"
    df = pd.read_csv(url)
    df["TIME_PERIOD"] = pd.to_datetime(df["TIME_PERIOD"])
    return df.set_index("TIME_PERIOD")["OBS_VALUE"].sort_index()


def fetch_live_data() -> pd.DataFrame:
    permits = _fetch_eurostat(
        "sts_cobp_q",
        {"geo": "BG", "indic_bt": "PSQM", "unit": "I15", "s_adj": "NSA"},
    )
    mortgages = _fetch_ecb("BSI/M.BG.N.A.A22.A.1.U2.2250.Z01.E")
    nfc_re = _fetch_ecb("BSI/M.BG.N.A.A22.A.1.U2.4S.Z01.E")
    hpi = _fetch_eurostat(
        "prc_hpi_q",
        {"geo": "BG", "purchase": "TOTAL", "unit": "I15_Q"},
    )
    monthly_to_q = lambda s: s.resample("QS").sum()
    df = pd.DataFrame({
        "hpi": hpi.resample("QS").last(),
        "permits": permits,
        "nfc_loans": monthly_to_q(nfc_re),
        "mortgages": monthly_to_q(mortgages),
    }).dropna()
    return df


# ---------- Synthetic demo data (calibrated to published BG stats) ----------

def synthetic_demo_data() -> pd.DataFrame:
    """
    Anchors used (real, published):
      HPI Q4 2025 ~ 210 (2015 = 100)
      Permits Q4 2025 ~ 15,642 dwellings
      Mortgage stock Feb 2026 ~ EUR 17.3bn, +27.8% YoY
      Total transactions 2025 ~ 226,513
    """
    rng = np.random.default_rng(7)
    quarters = pd.date_range(start="2015-01-01", end="2026-04-01", freq="QS")
    n = len(quarters)
    t = np.arange(n)

    # HPI: flat-ish 2015-2019, accelerating boom 2020-2025
    # anchor: ~210 by Q4 2025 (2015 = 100), then small post-euro pullback
    excess = np.maximum(t - 20, 0).astype(float)
    base = np.where(t < 20, 100 + t * 1.6, 132 + (excess ** 1.5) * 0.65)
    hpi = base + rng.normal(0, 1.2, n).cumsum() * 0.25

    # Permits: trend + Q4-peaked seasonality + boom-bust cycle
    permits_trend = 6500 + t * 230
    seasonality = 1800 * np.sin(2 * np.pi * (t + 1) / 4)
    boom = 2200 * np.exp(-((t - 32) ** 2) / 40)  # peak around 2023
    permits = permits_trend + seasonality + boom + rng.normal(0, 700, n)
    permits = np.clip(permits, 3000, None)

    # NFC real-estate loans (EUR bn, quarterly flow proxy)
    nfc_cycle = 0.35 * np.sin(2 * np.pi * t / 18)
    nfc_loans = 1.4 + t * 0.06 + nfc_cycle + rng.normal(0, 0.08, n).cumsum() * 0.05

    # Household mortgage origination (EUR bn, quarterly)
    mortgage = 0.18 + t * 0.014 + np.exp(t / 38) * 0.06 + rng.normal(0, 0.05, n)
    mortgage = np.clip(mortgage, 0.1, None)

    return pd.DataFrame(
        {"hpi": hpi, "permits": permits, "nfc_loans": nfc_loans, "mortgages": mortgage},
        index=quarters,
    )


# ---------- COT Index ----------

def williams_cot_index(series: pd.Series, lookback: int) -> pd.Series:
    rmin = series.rolling(window=lookback, min_periods=lookback).min()
    rmax = series.rolling(window=lookback, min_periods=lookback).max()
    return (series - rmin) / (rmax - rmin) * 100


def build_cot_model(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["hpi"] = df["hpi"]
    out["retailers"] = williams_cot_index(df["mortgages"], LOOKBACK_QUARTERS)
    out["commercials"] = williams_cot_index(df["permits"], LOOKBACK_QUARTERS)
    out["noncommercials"] = williams_cot_index(df["nfc_loans"], LOOKBACK_QUARTERS)
    return out


# ---------- Plot ----------

@dataclass
class Pane:
    title: str
    series: list  # list of (label, pd.Series, color)
    ymin: float = None
    ymax: float = None
    thresholds: bool = False


def _draw_pane(ax, pane: Pane, last_dates: pd.DatetimeIndex):
    for label, s, color in pane.series:
        s_plot = s.dropna()
        ax.plot(s_plot.index, s_plot.values, color=color, lw=1.6, label=label)
        # value label at the right edge
        if len(s_plot):
            last_x = s_plot.index[-1]
            last_y = float(s_plot.iloc[-1])
            ax.annotate(
                f"{last_y:,.1f}",
                xy=(last_x, last_y),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                fontsize=8,
                color=color,
                fontweight="bold",
            )
    if pane.thresholds:
        ax.axhline(UPPER_THRESHOLD, color="#888", lw=0.8, ls="--")
        ax.axhline(LOWER_THRESHOLD, color="#888", lw=0.8, ls="--")
        ax.axhspan(UPPER_THRESHOLD, 100, color="#ff3b30", alpha=0.06)
        ax.axhspan(0, LOWER_THRESHOLD, color="#34c759", alpha=0.06)
    if pane.ymin is not None:
        ax.set_ylim(pane.ymin, pane.ymax)
    ax.set_title(pane.title, loc="left", fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", which="major", labelsize=9)


def plot_model(df: pd.DataFrame, out_path: str, source_label: str):
    fig, axes = plt.subplots(5, 1, figsize=(15, 13), sharex=True)
    fig.suptitle(
        f"Bulgarian Housing — COT-style Indicator  ·  Williams COT Index, "
        f"{LOOKBACK_QUARTERS}Q lookback  ·  data: {source_label}",
        fontsize=12,
        fontweight="bold",
        y=0.995,
    )

    panes = [
        Pane(
            "House Price Index (НСИ, 2015 = 100)",
            [("HPI", df["hpi"], "#1f77b4")],
        ),
        Pane(
            "COT Index — all three legs",
            [
                ("Retailers (mortgages)", df["retailers"], "#ff3b30"),
                ("Commercials (developers / permits)", df["commercials"], "#34c759"),
                ("Non-commercials (NFC real-estate loans)", df["noncommercials"], "#f5c518"),
            ],
            ymin=-5,
            ymax=105,
            thresholds=True,
        ),
        Pane(
            "Retailers — household mortgage origination",
            [("Retailers", df["retailers"], "#ff3b30")],
            ymin=-5,
            ymax=105,
            thresholds=True,
        ),
        Pane(
            "Commercials — developer building permits",
            [("Commercials", df["commercials"], "#34c759")],
            ymin=-5,
            ymax=105,
            thresholds=True,
        ),
        Pane(
            "Non-commercials — NFC real-estate loans",
            [("Non-commercials", df["noncommercials"], "#f5c518")],
            ymin=-5,
            ymax=105,
            thresholds=True,
        ),
    ]

    for ax, pane in zip(axes, panes):
        _draw_pane(ax, pane, df.index)

    axes[-1].set_xlabel("Quarter")
    plt.tight_layout(rect=[0, 0, 1, 0.985])
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


# ---------- Entry point ----------

def main():
    live = os.environ.get("LIVE") == "1"
    if live:
        raw = fetch_live_data()
        source_label = "LIVE (Eurostat + ECB SDW)"
    else:
        raw = synthetic_demo_data()
        source_label = "SYNTHETIC (calibrated to published БНБ / НСИ stats)"

    model = build_cot_model(raw)

    out_csv = "bg_housing_cot.csv"
    out_png = "bg_housing_cot.png"
    model.to_csv(out_csv, float_format="%.3f")
    plot_model(model, out_png, source_label)

    last = model.dropna().tail(4)
    print(f"Source: {source_label}")
    print(f"Wrote {out_csv} and {out_png}")
    print()
    print("Last 4 quarters:")
    print(last.round(1).to_string())


if __name__ == "__main__":
    main()
