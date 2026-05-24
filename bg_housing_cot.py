"""
Bulgarian Housing COT Indicator.

Layout (5 panes):
  1) Average housing price (BGN / m²) — monthly OHLC candles
  2) COT Index — Commercials / Non-commercials / Retailers (combined)
  3) Commercials only        (NSI developer building permits, YoY%)
  4) Non-commercials only    (БНБ NFC real-estate loan stock, YoY%)
  5) Retailers only          (БНБ household mortgage stock, YoY%)

Williams COT Index = (x - min) / (max - min) * 100
Applied to the YoY % CHANGE of each underlying series, so a long trend
in the raw stock doesn't pin the index at 100.

Lookback = 26 quarters. Thresholds at 80 / 20.

Outputs:
  bg_housing_cot.png   (static)
  bg_housing_cot.html  (interactive, open in browser)
  bg_housing_cot.csv   (model values)

LIVE=1 → fetch real series (Eurostat + ECB SDW)
"""

import io
import os
import urllib.request

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import plotly.graph_objects as go
from plotly.subplots import make_subplots


LOOKBACK_QUARTERS = 26
UPPER_THRESHOLD = 80
LOWER_THRESHOLD = 20
INTRA_MONTH_VOL_PCT = 0.010   # ±1.0% intra-month synthetic range for candles

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
ECB_BASE = "https://data-api.ecb.europa.eu/service/data"

GREEN = "#34c759"
RED = "#ff3b30"
YELLOW = "#f5c518"
BLUE = "#1f77b4"


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
    # quarterly indicators
    quarterly = pd.DataFrame({
        "avg_price": hpi.resample("QS").last(),
        "permits": permits,
        "nfc_loans": nfc_re.resample("QS").last(),
        "mortgages": mortgages.resample("QS").last(),
    }).dropna()
    # monthly avg_price for candles — НСИ is quarterly, interpolate to monthly
    monthly_price = hpi.resample("MS").interpolate(method="time")
    return quarterly, monthly_price


# ---------- Synthetic demo data ----------

def synthetic_demo_data():
    """
    Calibrated to published BG stats:
      Sofia avg price 2025 ≈ 3,500 BGN/m²
      Permits Q4 2025 ≈ 15,642 dwellings
      Mortgage stock Feb 2026 ≈ EUR 17.3bn, +27.8% YoY
    """
    rng = np.random.default_rng(7)

    # ----- monthly avg_price (BGN/m²) -----
    months = pd.date_range(start="2015-01-01", end="2026-04-01", freq="MS")
    m = len(months)
    tm = np.arange(m)
    excess = np.maximum(tm - 60, 0).astype(float)  # boom starts ~2020
    avg_price = np.where(tm < 60, 1500 + tm * 6.0, 1860 + (excess ** 1.45) * 4.2)
    avg_price += rng.normal(0, 18, m).cumsum() * 0.10
    monthly_price = pd.Series(avg_price, index=months, name="avg_price")

    # ----- quarterly indicators -----
    quarters = pd.date_range(start="2015-01-01", end="2026-04-01", freq="QS")
    n = len(quarters)
    t = np.arange(n)

    # Permits: trend + Q4 seasonality + boom around 2023
    permits = 6500 + t * 230 + 1800 * np.sin(2 * np.pi * (t + 1) / 4)
    permits += 2200 * np.exp(-((t - 32) ** 2) / 40) + rng.normal(0, 700, n)
    permits = np.clip(permits, 3000, None)

    # Mortgage stock EUR bn: ~3.5 → ~17.3 with a cycle so YoY% has dynamics
    mortgages = 3.5 * np.exp(0.035 * t)
    mortgages += 0.6 * np.sin(2 * np.pi * t / 14)   # cycle ~3.5yr
    mortgages += rng.normal(0, 0.08, n).cumsum() * 0.1

    # NFC real-estate loan stock
    nfc_loans = 1.4 + t * 0.06 + 0.35 * np.sin(2 * np.pi * t / 12)
    nfc_loans += rng.normal(0, 0.05, n).cumsum() * 0.08

    avg_price_q = monthly_price.resample("QS").last().reindex(quarters)
    quarterly = pd.DataFrame(
        {"avg_price": avg_price_q.values, "permits": permits,
         "mortgages": mortgages, "nfc_loans": nfc_loans},
        index=quarters,
    )
    return quarterly, monthly_price


# ---------- COT Index ----------

def williams_cot_index(series, lookback):
    rmin = series.rolling(window=lookback, min_periods=lookback).min()
    rmax = series.rolling(window=lookback, min_periods=lookback).max()
    return (series - rmin) / (rmax - rmin) * 100


def build_cot_model(df):
    """
    Apply COT to the YoY % change of each underlying series.

    Why YoY%: raw mortgage / loan STOCKS grow ~monotonically with a long-run
    trend, so the rolling-min/rolling-max bracket would pin the COT index
    at 100. YoY% captures the cyclical positioning instead.
    """
    mort_yoy = df["mortgages"].pct_change(4) * 100
    perm_yoy = df["permits"].pct_change(4) * 100
    nfc_yoy  = df["nfc_loans"].pct_change(4) * 100

    return pd.DataFrame({
        "avg_price":      df["avg_price"],
        "mortgages_yoy":  mort_yoy,
        "permits_yoy":    perm_yoy,
        "nfc_yoy":        nfc_yoy,
        "retailers":      williams_cot_index(mort_yoy, LOOKBACK_QUARTERS),
        "commercials":    williams_cot_index(perm_yoy, LOOKBACK_QUARTERS),
        "noncommercials": williams_cot_index(nfc_yoy,  LOOKBACK_QUARTERS),
    }, index=df.index)


# ---------- OHLC for monthly price ----------

def synthesize_monthly_ohlc(monthly_series, vol_pct=INTRA_MONTH_VOL_PCT, seed=11):
    """
    open  = prev month's close
    close = month-end value
    high  = max(open, close) + small synthetic spread
    low   = min(open, close) - small synthetic spread
    """
    rng = np.random.default_rng(seed)
    closes = monthly_series.values.astype(float)
    opens = np.concatenate(([closes[0]], closes[:-1]))
    body_hi = np.maximum(opens, closes)
    body_lo = np.minimum(opens, closes)
    return pd.DataFrame(
        {
            "open":  opens,
            "high":  body_hi + rng.uniform(0, vol_pct, len(closes)) * body_hi,
            "low":   body_lo - rng.uniform(0, vol_pct, len(closes)) * body_lo,
            "close": closes,
        },
        index=monthly_series.index,
    )


# ---------- Matplotlib plot ----------

def _draw_candles(ax, ohlc, width_days=22):
    for date, row in ohlc.iterrows():
        x = mdates.date2num(date)
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        color = GREEN if c >= o else RED
        ax.plot([x, x], [l, h], color=color, lw=1.0, zorder=2)
        body_lo = min(o, c)
        height = abs(c - o) or (h - l) * 0.05 or 1e-3
        ax.add_patch(Rectangle(
            (x - width_days / 2, body_lo),
            width_days, height,
            facecolor=color, edgecolor=color, zorder=3,
        ))


def _draw_cot_pane(ax, series, label, color):
    s = series.dropna()
    ax.plot(s.index, s.values, color=color, lw=1.6, label=label)
    if len(s):
        ax.annotate(
            f"{float(s.iloc[-1]):.0f}",
            xy=(s.index[-1], float(s.iloc[-1])),
            xytext=(6, 0), textcoords="offset points",
            va="center", fontsize=8, fontweight="bold", color=color,
        )
    ax.axhline(UPPER_THRESHOLD, color="#888", lw=0.8, ls="--")
    ax.axhline(LOWER_THRESHOLD, color="#888", lw=0.8, ls="--")
    ax.axhspan(UPPER_THRESHOLD, 100, color=RED, alpha=0.06)
    ax.axhspan(0, LOWER_THRESHOLD, color=GREEN, alpha=0.06)
    ax.set_ylim(-5, 105)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)


def plot_model(model, monthly_price, out_path, source_label):
    ohlc = synthesize_monthly_ohlc(monthly_price)

    fig, axes = plt.subplots(
        5, 1, figsize=(15, 16), sharex=True,
        gridspec_kw={"height_ratios": [3, 2.5, 1.6, 1.6, 1.6]},
    )
    fig.suptitle(
        f"Bulgarian Housing — COT Indicator  ·  data: {source_label}",
        fontsize=12, fontweight="bold", y=0.997,
    )

    # 1) Avg price candles
    ax = axes[0]
    _draw_candles(ax, ohlc, width_days=22)
    ax.set_title("Average housing price (BGN / m²) — monthly candles",
                 loc="left", fontsize=10, fontweight="bold")
    ax.set_ylabel("BGN / m²")
    ax.grid(True, alpha=0.25)
    last_c = float(ohlc["close"].iloc[-1])
    ax.annotate(
        f"{last_c:,.0f}",
        xy=(ohlc.index[-1], last_c), xytext=(8, 0),
        textcoords="offset points", va="center",
        fontsize=9, fontweight="bold",
        color=(GREEN if ohlc["close"].iloc[-1] >= ohlc["open"].iloc[-1] else RED),
    )
    ax.set_xlim(monthly_price.index.min() - pd.Timedelta(days=20),
                monthly_price.index.max() + pd.Timedelta(days=45))

    # 2) COT combined
    ax = axes[1]
    for label, s, color in [
        ("Commercials (permits, YoY%)",     model["commercials"],    GREEN),
        ("Non-commercials (NFC RE, YoY%)",  model["noncommercials"], YELLOW),
        ("Retailers (mortgages, YoY%)",     model["retailers"],      RED),
    ]:
        _draw_cot_pane(ax, s, label, color)
    ax.set_title(f"COT Index — Williams %R, {LOOKBACK_QUARTERS}Q lookback",
                 loc="left", fontsize=10, fontweight="bold")
    ax.set_ylabel("COT (0–100)")

    # 3) Commercials
    _draw_cot_pane(axes[2], model["commercials"], "Commercials", GREEN)
    axes[2].set_title("Commercials — developer building permits (YoY% → COT)",
                      loc="left", fontsize=10, fontweight="bold")
    axes[2].set_ylabel("COT (0–100)")

    # 4) Non-commercials
    _draw_cot_pane(axes[3], model["noncommercials"], "Non-commercials", YELLOW)
    axes[3].set_title("Non-commercials — NFC real-estate loan stock (YoY% → COT)",
                      loc="left", fontsize=10, fontweight="bold")
    axes[3].set_ylabel("COT (0–100)")

    # 5) Retailers
    _draw_cot_pane(axes[4], model["retailers"], "Retailers", RED)
    axes[4].set_title("Retailers — household mortgage stock (YoY% → COT)",
                      loc="left", fontsize=10, fontweight="bold")
    axes[4].set_ylabel("COT (0–100)")
    axes[4].set_xlabel("Date")

    for ax in axes:
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout(rect=[0, 0, 1, 0.985])
    plt.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


# ---------- Plotly HTML ----------

def _add_cot_traces(fig, series, label, color, row, show_legend=True):
    s = series.dropna()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines", name=label,
        line=dict(color=color, width=2),
        showlegend=show_legend,
        hovertemplate=label + ": %{y:.0f}<extra></extra>",
    ), row=row, col=1)
    fig.add_hline(y=UPPER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=row, col=1)
    fig.add_hline(y=LOWER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=row, col=1)
    fig.add_hrect(y0=UPPER_THRESHOLD, y1=100, fillcolor=RED, opacity=0.06,
                  line_width=0, row=row, col=1)
    fig.add_hrect(y0=0, y1=LOWER_THRESHOLD, fillcolor=GREEN, opacity=0.06,
                  line_width=0, row=row, col=1)
    fig.update_yaxes(range=[-5, 105], row=row, col=1)


def plot_html(model, monthly_price, out_path, source_label):
    ohlc = synthesize_monthly_ohlc(monthly_price)

    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True,
        row_heights=[0.30, 0.24, 0.155, 0.155, 0.155],
        vertical_spacing=0.035,
        subplot_titles=(
            "Average housing price (BGN / m²) — monthly candles",
            f"COT Index — Williams %R, {LOOKBACK_QUARTERS}Q lookback",
            "Commercials — developer building permits (YoY% → COT)",
            "Non-commercials — NFC real-estate loan stock (YoY% → COT)",
            "Retailers — household mortgage stock (YoY% → COT)",
        ),
    )

    fig.add_trace(go.Candlestick(
        x=ohlc.index,
        open=ohlc["open"], high=ohlc["high"],
        low=ohlc["low"], close=ohlc["close"],
        name="Avg price",
        increasing_line_color=GREEN, increasing_fillcolor=GREEN,
        decreasing_line_color=RED,   decreasing_fillcolor=RED,
        showlegend=False,
    ), row=1, col=1)

    # COT combined (row 2)
    for label, s, color in [
        ("Commercials",      model["commercials"],    GREEN),
        ("Non-commercials",  model["noncommercials"], YELLOW),
        ("Retailers",        model["retailers"],      RED),
    ]:
        s = s.dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines", name=label,
            line=dict(color=color, width=2),
            hovertemplate=label + ": %{y:.0f}<extra></extra>",
        ), row=2, col=1)
    fig.add_hline(y=UPPER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=LOWER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=2, col=1)
    fig.add_hrect(y0=UPPER_THRESHOLD, y1=100, fillcolor=RED, opacity=0.06,
                  line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=LOWER_THRESHOLD, fillcolor=GREEN, opacity=0.06,
                  line_width=0, row=2, col=1)
    fig.update_yaxes(range=[-5, 105], row=2, col=1)

    _add_cot_traces(fig, model["commercials"],    "Commercials",     GREEN,  row=3, show_legend=False)
    _add_cot_traces(fig, model["noncommercials"], "Non-commercials", YELLOW, row=4, show_legend=False)
    _add_cot_traces(fig, model["retailers"],      "Retailers",       RED,    row=5, show_legend=False)

    fig.update_yaxes(title_text="BGN / m²", row=1, col=1)
    for r in (2, 3, 4, 5):
        fig.update_yaxes(title_text="COT (0–100)", row=r, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_xaxes(title_text="Date", row=5, col=1)

    fig.update_layout(
        title=dict(
            text=f"<b>Bulgarian Housing — COT Indicator</b>  ·  data: {source_label}",
            x=0.02, xanchor="left",
        ),
        template="plotly_white",
        height=1300,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(l=60, r=40, t=90, b=50),
    )

    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True)


# ---------- Entry point ----------

def main():
    live = os.environ.get("LIVE") == "1"
    if live:
        quarterly, monthly_price = fetch_live_data()
        source_label = "LIVE (Eurostat + ECB SDW)"
    else:
        quarterly, monthly_price = synthetic_demo_data()
        source_label = "SYNTHETIC (calibrated to published БНБ / НСИ stats)"

    model = build_cot_model(quarterly)
    model.to_csv("bg_housing_cot.csv", float_format="%.2f")
    plot_model(model, monthly_price, "bg_housing_cot.png", source_label)
    plot_html(model, monthly_price, "bg_housing_cot.html", source_label)

    print(f"Source: {source_label}")
    print("Wrote bg_housing_cot.csv, bg_housing_cot.png, bg_housing_cot.html")
    print()
    print("Last 4 quarters (COT):")
    print(model[["avg_price", "commercials", "noncommercials", "retailers"]]
          .dropna().tail(4).round(1).to_string())


if __name__ == "__main__":
    main()
