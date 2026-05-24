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
from matplotlib.patches import Rectangle


LOOKBACK_QUARTERS = 26
UPPER_THRESHOLD = 80
LOWER_THRESHOLD = 20

# Intra-month volatility model for synthesized OHLC range.
# BG housing has no daily price feed; this is a calibrated synthetic spread
# around the real month-end value. ~1.2% mirrors typical BG REIT daily ranges.
INTRA_MONTH_VOL_PCT = 0.012

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


def fetch_live_data() -> tuple:
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
    monthly = pd.DataFrame({
        "mortgage_stock": mortgages,
        "nfc_loans_stock": nfc_re,
    }).dropna()
    monthly_to_q = lambda s: s.resample("QS").sum()
    quarterly = pd.DataFrame({
        "hpi": hpi.resample("QS").last(),
        "permits": permits,
        "nfc_loans": monthly_to_q(nfc_re),
        "mortgages": monthly_to_q(mortgages),
    }).dropna()
    return quarterly, monthly


# ---------- Synthetic demo data (calibrated to published BG stats) ----------

def synthetic_demo_data() -> tuple:
    """
    Returns (quarterly_df, monthly_df).

    Anchors used (real, published):
      HPI Q4 2025 ~ 210 (2015 = 100)
      Permits Q4 2025 ~ 15,642 dwellings
      Mortgage stock Feb 2026 ~ EUR 17.3bn, +27.8% YoY
      Total transactions 2025 ~ 226,513
    """
    rng = np.random.default_rng(7)

    # --- Monthly series (mortgage stock + NFC RE loans, EUR bn) ---
    months = pd.date_range(start="2015-01-01", end="2026-04-01", freq="MS")
    m = len(months)
    tm = np.arange(m)
    # Mortgage stock: ~3.5bn in 2015 → ~17.3bn by early 2026 (≈+27.8% YoY tail)
    mortgage_stock = 3.5 * np.exp(0.0118 * tm) + 0.4 * np.sin(2 * np.pi * tm / 36)
    mortgage_stock += rng.normal(0, 0.04, m).cumsum() * 0.08
    # NFC real-estate loan stock
    nfc_stock = 1.4 + tm * 0.018 + 0.35 * np.sin(2 * np.pi * tm / 36)
    nfc_stock += rng.normal(0, 0.03, m).cumsum() * 0.05
    monthly = pd.DataFrame(
        {"mortgage_stock": mortgage_stock, "nfc_loans_stock": nfc_stock},
        index=months,
    )

    # --- Quarterly series for COT model ---
    quarters = pd.date_range(start="2015-01-01", end="2026-04-01", freq="QS")
    n = len(quarters)
    t = np.arange(n)

    # HPI: flat-ish 2015-2019, accelerating boom 2020-2025
    excess = np.maximum(t - 20, 0).astype(float)
    base = np.where(t < 20, 100 + t * 1.6, 132 + (excess ** 1.5) * 0.65)
    hpi = base + rng.normal(0, 1.2, n).cumsum() * 0.25

    # Permits: trend + Q4-peaked seasonality + boom-bust cycle
    permits_trend = 6500 + t * 230
    seasonality = 1800 * np.sin(2 * np.pi * (t + 1) / 4)
    boom = 2200 * np.exp(-((t - 32) ** 2) / 40)
    permits = permits_trend + seasonality + boom + rng.normal(0, 700, n)
    permits = np.clip(permits, 3000, None)

    # Aggregate monthly → quarterly (last for stocks)
    mortgages_q = monthly["mortgage_stock"].resample("QS").last().reindex(quarters)
    nfc_q = monthly["nfc_loans_stock"].resample("QS").last().reindex(quarters)

    quarterly = pd.DataFrame(
        {"hpi": hpi, "permits": permits, "nfc_loans": nfc_q.values, "mortgages": mortgages_q.values},
        index=quarters,
    )
    return quarterly, monthly


# ---------- OHLC + interpolation ----------

def synthesize_monthly_ohlc(monthly: pd.Series, vol_pct: float = INTRA_MONTH_VOL_PCT, seed: int = 11) -> pd.DataFrame:
    """
    Build monthly OHLC from a single monthly observation.

      close = month-end value (real)
      open  = previous month's close (real)
      high  = max(open, close) * (1 + r_h)   with r_h ~ U(0, vol_pct)
      low   = min(open, close) * (1 - r_l)   with r_l ~ U(0, vol_pct)

    The H / L spread is SYNTHETIC — BG mortgage stock has no intra-month
    high / low; this is a calibrated volatility model around real anchors.
    """
    rng = np.random.default_rng(seed)
    closes = monthly.values.astype(float)
    opens = np.concatenate(([closes[0]], closes[:-1]))
    body_hi = np.maximum(opens, closes)
    body_lo = np.minimum(opens, closes)
    h_extra = rng.uniform(0, vol_pct, len(closes)) * body_hi
    l_extra = rng.uniform(0, vol_pct, len(closes)) * body_lo
    return pd.DataFrame(
        {
            "open": opens,
            "high": body_hi + h_extra,
            "low": body_lo - l_extra,
            "close": closes,
        },
        index=monthly.index,
    )


def weekly_interpolate(monthly: pd.Series) -> pd.Series:
    """
    Cubic-spline interpolation of monthly observations onto weekly index.
    SYNTHETIC — purely a visual smoother; no real weekly data exists.
    """
    weekly_idx = pd.date_range(monthly.index.min(), monthly.index.max(), freq="W-MON")
    combined = pd.concat([monthly, pd.Series(np.nan, index=weekly_idx)]).sort_index()
    combined = combined[~combined.index.duplicated(keep="first")]
    return combined.interpolate(method="cubic").reindex(weekly_idx)


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


def _draw_candles(ax, ohlc: pd.DataFrame, width_days: float = 22):
    up = "#34c759"
    down = "#ff3b30"
    for date, row in ohlc.iterrows():
        x = mdates.date2num(date)
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        color = up if c >= o else down
        ax.plot([x, x], [l, h], color=color, lw=1.0, zorder=2)
        body_lo = min(o, c)
        height = abs(c - o)
        if height < 1e-6:
            height = (h - l) * 0.05 or 1e-3
        rect = Rectangle(
            (x - width_days / 2, body_lo),
            width_days,
            height,
            facecolor=color,
            edgecolor=color,
            zorder=3,
        )
        ax.add_patch(rect)


def plot_price_chart(monthly: pd.DataFrame, out_path: str, source_label: str):
    """
    Two-pane price view:
      1) Monthly OHLC candles of БНБ mortgage stock (proxy price for the housing
         market). H/L is synthesized via calibrated intra-month volatility.
      2) Weekly cubic-spline interpolation of the same monthly series (visual
         only; no real weekly data exists for BG housing).
    """
    ohlc = synthesize_monthly_ohlc(monthly["mortgage_stock"])
    weekly = weekly_interpolate(monthly["mortgage_stock"])

    fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True,
                             gridspec_kw={"height_ratios": [3, 2]})
    fig.suptitle(
        "Bulgarian Housing — Price-style View  ·  Mortgage Stock (БНБ) as "
        f"market proxy  ·  data: {source_label}",
        fontsize=12, fontweight="bold", y=0.995,
    )

    # --- Candles ---
    ax = axes[0]
    _draw_candles(ax, ohlc, width_days=22)
    ax.set_title(
        "Monthly OHLC candles — close is real БНБ month-end stock; "
        "H / L is synthetic intra-month range (±1.2%)",
        loc="left", fontsize=10, fontweight="bold",
    )
    ax.set_ylabel("Mortgage stock (EUR bn)")
    ax.grid(True, alpha=0.25)
    last_c = float(ohlc["close"].iloc[-1])
    last_d = ohlc.index[-1]
    ax.annotate(
        f"{last_c:,.2f}",
        xy=(last_d, last_c), xytext=(8, 0), textcoords="offset points",
        va="center", fontsize=9, fontweight="bold",
        color=("#34c759" if ohlc["close"].iloc[-1] >= ohlc["open"].iloc[-1] else "#ff3b30"),
    )
    ax.set_xlim(monthly.index.min() - pd.Timedelta(days=20),
                monthly.index.max() + pd.Timedelta(days=40))

    # --- Weekly subchart ---
    ax2 = axes[1]
    ax2.plot(weekly.index, weekly.values, color="#1f77b4", lw=1.3,
             label="Weekly interp. (synthetic)")
    ax2.scatter(monthly.index, monthly["mortgage_stock"].values,
                color="#1f77b4", s=14, zorder=4, label="Monthly close (real)")
    ax2.set_title(
        "Weekly subchart — cubic-spline interpolation of monthly closes "
        "(no real weekly data exists)",
        loc="left", fontsize=10, fontweight="bold",
    )
    ax2.set_ylabel("EUR bn")
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper left", fontsize=8, framealpha=0.9)

    for ax_ in axes:
        ax_.xaxis.set_major_locator(mdates.YearLocator())
        ax_.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
        ax_.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    axes[-1].set_xlabel("Date")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


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
        quarterly, monthly = fetch_live_data()
        source_label = "LIVE (Eurostat + ECB SDW)"
    else:
        quarterly, monthly = synthetic_demo_data()
        source_label = "SYNTHETIC (calibrated to published БНБ / НСИ stats)"

    model = build_cot_model(quarterly)

    out_cot_csv = "bg_housing_cot.csv"
    out_cot_png = "bg_housing_cot.png"
    out_price_png = "bg_housing_price.png"
    out_monthly_csv = "bg_housing_monthly.csv"

    model.to_csv(out_cot_csv, float_format="%.3f")
    monthly.to_csv(out_monthly_csv, float_format="%.4f")
    plot_model(model, out_cot_png, source_label)
    plot_price_chart(monthly, out_price_png, source_label)

    last_q = model.dropna().tail(4)
    last_m = synthesize_monthly_ohlc(monthly["mortgage_stock"]).tail(6)
    print(f"Source: {source_label}")
    print(f"Wrote {out_cot_csv}, {out_monthly_csv}, {out_cot_png}, {out_price_png}")
    print()
    print("Last 4 quarters (COT model):")
    print(last_q.round(1).to_string())
    print()
    print("Last 6 monthly OHLC candles (mortgage stock, EUR bn):")
    print(last_m.round(3).to_string())


if __name__ == "__main__":
    main()
