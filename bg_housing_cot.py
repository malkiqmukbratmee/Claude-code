"""
Bulgarian Housing COT Indicator (simple version).

Two panes:
  1) Avg housing price (BGN / m²)
  2) Williams COT Index — Commercials / Non-commercials / Retailers

COT legs:
  Retailers       — БНБ household mortgage stock
  Commercials     — НСИ developer building permits
  Non-commercials — БНБ NFC real-estate loan stock

Williams COT Index = (x - min) / (max - min) * 100
Lookback = 26 quarters. Thresholds at 80 / 20.

LIVE=1 python bg_housing_cot.py  → fetch real series (Eurostat + ECB SDW)
Default                          → synthetic data calibrated to published stats
"""

import io
import os
import urllib.request

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go
from plotly.subplots import make_subplots


LOOKBACK_QUARTERS = 26
UPPER_THRESHOLD = 80
LOWER_THRESHOLD = 20

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data"


# ---------- Live fetchers ----------

def _fetch_eurostat(dataset, params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{EUROSTAT_BASE}/{dataset}?format=JSON&{qs}"
    with urllib.request.urlopen(url, timeout=30) as r:
        payload = pd.read_json(io.BytesIO(r.read()), typ="series").to_dict()
    times = list(payload["dimension"]["time"]["category"]["index"].keys())
    values = payload["value"]
    return pd.Series(
        {pd.Period(times[int(i)], freq="Q").to_timestamp(): v for i, v in values.items()}
    ).sort_index()


def _fetch_ecb(series_key):
    url = f"{ECB_BASE}/{series_key}?format=csvdata"
    df = pd.read_csv(url)
    df["TIME_PERIOD"] = pd.to_datetime(df["TIME_PERIOD"])
    return df.set_index("TIME_PERIOD")["OBS_VALUE"].sort_index()


def fetch_live_data():
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
    return pd.DataFrame({
        "avg_price": hpi.resample("QS").last(),
        "permits": permits,
        "nfc_loans": nfc_re.resample("QS").last(),
        "mortgages": mortgages.resample("QS").last(),
    }).dropna()


# ---------- Synthetic demo data ----------

def synthetic_demo_data():
    """
    Quarterly synthetic data calibrated to published BG stats.
      Sofia avg price 2025 ≈ 3,500 BGN/m²
      Permits Q4 2025 ≈ 15,642 dwellings
      Mortgage stock Feb 2026 ≈ EUR 17.3bn, +27.8% YoY
    """
    rng = np.random.default_rng(7)
    quarters = pd.date_range(start="2015-01-01", end="2026-04-01", freq="QS")
    n = len(quarters)
    t = np.arange(n)

    # Avg price BGN/m²: ~1,500 in 2015 → ~3,800 by Q1 2026 (Sofia anchor)
    excess = np.maximum(t - 20, 0).astype(float)
    avg_price = np.where(t < 20, 1500 + t * 18, 1860 + (excess ** 1.45) * 22)
    avg_price += rng.normal(0, 12, n).cumsum() * 0.4

    # Permits: trend + Q4 seasonality + boom around 2023
    permits = 6500 + t * 230 + 1800 * np.sin(2 * np.pi * (t + 1) / 4)
    permits += 2200 * np.exp(-((t - 32) ** 2) / 40) + rng.normal(0, 700, n)
    permits = np.clip(permits, 3000, None)

    # Mortgage stock EUR bn: ~3.5 → ~17.3
    mortgages = 3.5 * np.exp(0.035 * t) + 0.4 * np.sin(2 * np.pi * t / 12)
    mortgages += rng.normal(0, 0.08, n).cumsum() * 0.1

    # NFC real-estate loan stock
    nfc_loans = 1.4 + t * 0.06 + 0.35 * np.sin(2 * np.pi * t / 12)
    nfc_loans += rng.normal(0, 0.05, n).cumsum() * 0.08

    return pd.DataFrame(
        {"avg_price": avg_price, "permits": permits,
         "mortgages": mortgages, "nfc_loans": nfc_loans},
        index=quarters,
    )


# ---------- COT Index ----------

def williams_cot_index(series, lookback):
    rmin = series.rolling(window=lookback, min_periods=lookback).min()
    rmax = series.rolling(window=lookback, min_periods=lookback).max()
    return (series - rmin) / (rmax - rmin) * 100


def build_cot_model(df):
    return pd.DataFrame({
        "avg_price":     df["avg_price"],
        "retailers":     williams_cot_index(df["mortgages"], LOOKBACK_QUARTERS),
        "commercials":   williams_cot_index(df["permits"],   LOOKBACK_QUARTERS),
        "noncommercials":williams_cot_index(df["nfc_loans"], LOOKBACK_QUARTERS),
    }, index=df.index)


# ---------- Plot ----------

def plot_model(df, out_path, source_label):
    fig, (ax_price, ax_cot) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True,
        gridspec_kw={"height_ratios": [2, 3]},
    )
    fig.suptitle(
        f"Bulgarian Housing — COT Indicator  ·  data: {source_label}",
        fontsize=12, fontweight="bold", y=0.995,
    )

    # --- Avg price ---
    ax_price.plot(df.index, df["avg_price"], color="#1f77b4", lw=1.8)
    ax_price.set_title("Average housing price (BGN / m²)",
                       loc="left", fontsize=10, fontweight="bold")
    ax_price.set_ylabel("BGN / m²")
    ax_price.grid(True, alpha=0.25)
    last_p = float(df["avg_price"].iloc[-1])
    ax_price.annotate(f"{last_p:,.0f}",
                      xy=(df.index[-1], last_p), xytext=(8, 0),
                      textcoords="offset points", va="center",
                      fontsize=9, fontweight="bold", color="#1f77b4")

    # --- COT Index ---
    legs = [
        ("Commercials (developers / permits)",       df["commercials"],    "#34c759"),
        ("Non-commercials (NFC real-estate loans)",  df["noncommercials"], "#f5c518"),
        ("Retailers (household mortgages)",          df["retailers"],      "#ff3b30"),
    ]
    for label, s, color in legs:
        s = s.dropna()
        ax_cot.plot(s.index, s.values, color=color, lw=1.6, label=label)
        ax_cot.annotate(f"{float(s.iloc[-1]):.0f}",
                        xy=(s.index[-1], float(s.iloc[-1])),
                        xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=8, fontweight="bold", color=color)

    ax_cot.axhline(UPPER_THRESHOLD, color="#888", lw=0.8, ls="--")
    ax_cot.axhline(LOWER_THRESHOLD, color="#888", lw=0.8, ls="--")
    ax_cot.axhspan(UPPER_THRESHOLD, 100, color="#ff3b30", alpha=0.06)
    ax_cot.axhspan(0, LOWER_THRESHOLD, color="#34c759", alpha=0.06)
    ax_cot.set_ylim(-5, 105)
    ax_cot.set_title(f"COT Index — Williams %R, {LOOKBACK_QUARTERS}Q lookback, thresholds 80 / 20",
                     loc="left", fontsize=10, fontweight="bold")
    ax_cot.set_ylabel("COT Index (0–100)")
    ax_cot.grid(True, alpha=0.25)
    ax_cot.legend(loc="upper left", fontsize=9, framealpha=0.9)

    for ax in (ax_price, ax_cot):
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax_cot.set_xlabel("Quarter")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_html(df, out_path, source_label):
    """Interactive HTML version (open in browser, zoom / hover)."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.4, 0.6],
        vertical_spacing=0.08,
        subplot_titles=(
            "Average housing price (BGN / m²)",
            f"COT Index — Williams %R, {LOOKBACK_QUARTERS}Q lookback",
        ),
    )

    fig.add_trace(go.Scatter(
        x=df.index, y=df["avg_price"], mode="lines", name="Avg price",
        line=dict(color="#1f77b4", width=2),
        hovertemplate="%{x|%Y-Q%q}<br>%{y:,.0f} BGN/m²<extra></extra>",
    ), row=1, col=1)

    legs = [
        ("Commercials (permits)",     df["commercials"],    "#34c759"),
        ("Non-commercials (NFC RE)",  df["noncommercials"], "#f5c518"),
        ("Retailers (mortgages)",     df["retailers"],      "#ff3b30"),
    ]
    for label, s, color in legs:
        s = s.dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines", name=label,
            line=dict(color=color, width=2),
            hovertemplate="%{x|%Y-Q%q}<br>" + label + ": %{y:.0f}<extra></extra>",
        ), row=2, col=1)

    fig.add_hline(y=UPPER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=LOWER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=2, col=1)
    fig.add_hrect(y0=UPPER_THRESHOLD, y1=100, fillcolor="#ff3b30", opacity=0.06,
                  line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=LOWER_THRESHOLD, fillcolor="#34c759", opacity=0.06,
                  line_width=0, row=2, col=1)

    fig.update_yaxes(title_text="BGN / m²", row=1, col=1)
    fig.update_yaxes(title_text="COT (0–100)", range=[-5, 105], row=2, col=1)
    fig.update_xaxes(title_text="Quarter", row=2, col=1)

    fig.update_layout(
        title=dict(
            text=f"<b>Bulgarian Housing — COT Indicator</b>  ·  data: {source_label}",
            x=0.02, xanchor="left",
        ),
        template="plotly_white",
        height=720,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=60, r=40, t=90, b=50),
    )

    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True)


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
    model.to_csv("bg_housing_cot.csv", float_format="%.2f")
    plot_model(model, "bg_housing_cot.png", source_label)
    plot_html(model, "bg_housing_cot.html", source_label)

    print(f"Source: {source_label}")
    print("Wrote bg_housing_cot.csv, bg_housing_cot.png, bg_housing_cot.html")
    print()
    print("Last 4 quarters:")
    print(model.dropna().tail(4).round(1).to_string())


if __name__ == "__main__":
    main()
