"""
Bulgarian Housing — COT Indicator + Valuation + Seasonality.

Outputs:
  bg_housing_cot.png         COT view (static)
  bg_housing_cot.html        COT view (interactive)
  bg_housing_valuation.html  Valuation + Seasonality view (interactive)
  bg_housing_cot.csv         model values

COT view (5 panes):
  Avg price (EUR / m², monthly candles)
  COT Index combined  +  Commercials / Non-commercials / Retailers

Valuation view (4 panes):
  Avg price (EUR / m², monthly candles)
  UTC-style Valuation, 1-month analysis window, 12-month rescale
  UTC-style Valuation, 4-month analysis window, 12-month rescale
  Seasonality — average yearly path (last 4 years) vs current year

References for valuation: EUR/USD, EURIBOR 12M (proxy for mortgage cost).
BGN is pegged to EUR at 1.95583 since 1999, so EUR price = BGN / 1.95583.

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

# Currency board peg (fixed since 1999)
BGN_PER_EUR = 1.95583

# UTC-style Valuation thresholds
VAL_UPPER = 75
VAL_LOWER = -75

# Valuation windows (in months)
VAL_ANALYSIS_1M = 1
VAL_ANALYSIS_4M = 4
VAL_RESCALE_MONTHS = 12

# Seasonality lookback
SEASONALITY_YEARS = 4

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
    eurusd = _fetch_ecb("EXR/M.USD.EUR.SP00.A")
    euribor12m = _fetch_ecb("FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA")

    quarterly = pd.DataFrame({
        "avg_price": hpi.resample("QS").last(),
        "permits": permits,
        "nfc_loans": nfc_re.resample("QS").last(),
        "mortgages": mortgages.resample("QS").last(),
    }).dropna()
    monthly_price = hpi.resample("MS").interpolate(method="time")
    macros = pd.DataFrame({
        "eurusd":     eurusd.resample("MS").last(),
        "euribor12m": euribor12m.resample("MS").last(),
    }).dropna()
    return quarterly, monthly_price, macros


# ---------- Synthetic demo data ----------

def _anchored_series(months, anchors, noise_std=0.0, seed=0):
    """
    Build a monthly series by linearly interpolating between known anchor
    points (month_index → value), then layering optional cumulative noise.
    """
    idx = np.array(sorted(anchors.keys()))
    vals = np.array([anchors[k] for k in idx])
    tm = np.arange(len(months))
    out = np.interp(tm, idx, vals)
    if noise_std > 0:
        rng = np.random.default_rng(seed)
        out = out + rng.normal(0, noise_std, len(months)).cumsum() * 0.05
    return out


def synthetic_demo_data():
    """
    Calibrated to published BG stats, anchors covering 2007-2026:

      Avg price (BGN/m², Sofia):  2007 peak ~2,200  → 2010 bottom ~1,300
                                  → 2015 ~1,500    → 2025 ~3,800
      Permits (dwellings/quarter): 2007 ~9,000     → 2010 ~1,500
                                   → 2015 ~2,500   → 2025 ~5,500
      Mortgage stock (EUR bn):    2008 peak ~3.5   → 2013 ~3.0
                                  → 2015 ~3.5     → 2026 Feb ~17.3
      NFC RE loan stock (EUR bn): 2009 peak ~2.1   → 2014 ~1.6
                                  → 2015 ~1.5     → 2025 ~2.3
    """
    months = pd.date_range(start="2007-01-01", end="2026-04-01", freq="MS")
    # month indexes used as anchors (Jan 2007 = 0)
    def mi(year, month):
        return (year - 2007) * 12 + (month - 1)

    monthly_price_vals = _anchored_series(months, {
        mi(2007, 1):  1500,
        mi(2007, 12): 2200,   # peak
        mi(2009, 12): 1700,
        mi(2010, 12): 1300,   # bottom
        mi(2012, 12): 1350,
        mi(2014, 12): 1450,
        mi(2017, 12): 1700,
        mi(2019, 12): 1850,
        mi(2021, 12): 2300,
        mi(2023, 12): 3100,
        mi(2025, 12): 3800,
        mi(2026, 4):  4000,
    }, noise_std=20, seed=7)
    monthly_price = pd.Series(monthly_price_vals, index=months, name="avg_price")

    # ----- monthly underlying series (will be resampled to quarterly) -----
    permits_m = _anchored_series(months, {
        mi(2007, 6):  3000,
        mi(2008, 6):  2700,
        mi(2010, 6):  500,    # bust trough
        mi(2013, 6):  700,
        mi(2015, 6):  850,
        mi(2018, 6):  1300,
        mi(2020, 6):  1100,   # COVID dip
        mi(2022, 6):  1700,
        mi(2024, 6):  1800,
        mi(2026, 4):  1900,
    }, noise_std=80, seed=11)
    # add Q4-peaked seasonality so quarterly sums show seasonal pattern
    season = 250 * np.sin(2 * np.pi * (np.arange(len(months)) + 4) / 12)
    permits_m = np.clip(permits_m + season, 200, None)

    mortgages_m = _anchored_series(months, {
        mi(2007, 1):  2.0,
        mi(2008, 12): 3.5,    # peak before stagnation
        mi(2010, 12): 3.6,
        mi(2013, 12): 3.0,    # post-crisis low
        mi(2015, 12): 3.5,
        mi(2018, 12): 5.0,
        mi(2020, 12): 7.0,
        mi(2022, 12): 10.0,
        mi(2024, 12): 14.0,
        mi(2026, 2):  17.3,
        mi(2026, 4):  17.7,
    }, noise_std=0.04, seed=13)

    nfc_m = _anchored_series(months, {
        mi(2007, 1):  0.8,
        mi(2009, 6):  2.1,    # peak
        mi(2012, 6):  1.7,
        mi(2014, 12): 1.55,
        mi(2018, 12): 1.7,
        mi(2021, 12): 1.95,
        mi(2024, 12): 2.25,
        mi(2026, 4):  2.35,
    }, noise_std=0.02, seed=17)

    # ----- aggregate monthly → quarterly -----
    permits_s   = pd.Series(permits_m,   index=months)
    mortgages_s = pd.Series(mortgages_m, index=months)
    nfc_s       = pd.Series(nfc_m,       index=months)

    quarterly = pd.DataFrame({
        "avg_price": monthly_price.resample("QS").last(),
        "permits":   permits_s.resample("QS").sum(),     # flow → sum
        "mortgages": mortgages_s.resample("QS").last(),  # stock → last
        "nfc_loans": nfc_s.resample("QS").last(),        # stock → last
    }).dropna()

    # ----- macro references (monthly) -----
    eurusd_vals = _anchored_series(months, {
        mi(2007, 1):  1.30,
        mi(2007, 7):  1.36,
        mi(2008, 4):  1.59,   # EUR peak
        mi(2008, 12): 1.30,
        mi(2010, 6):  1.22,
        mi(2011, 5):  1.45,
        mi(2014, 12): 1.21,
        mi(2017, 1):  1.06,
        mi(2018, 4):  1.24,
        mi(2020, 3):  1.10,
        mi(2021, 5):  1.20,
        mi(2022, 9):  0.96,   # parity
        mi(2024, 7):  1.09,
        mi(2026, 4):  1.10,
    }, noise_std=0.008, seed=21)

    euribor12m_vals = _anchored_series(months, {
        mi(2007, 1):  4.10,
        mi(2008, 9):  5.50,   # peak before crisis cuts
        mi(2009, 12): 1.25,
        mi(2011, 7):  2.18,   # brief Trichet hike
        mi(2013, 12): 0.55,
        mi(2016, 1):  -0.05,  # negative territory
        mi(2019, 12): -0.25,
        mi(2021, 12): -0.50,
        mi(2022, 7):  0.99,
        mi(2023, 9):  4.20,   # peak hike
        mi(2024, 12): 2.43,
        mi(2026, 4):  2.20,
    }, noise_std=0.04, seed=23)

    macros = pd.DataFrame({
        "eurusd":     eurusd_vals,
        "euribor12m": euribor12m_vals,
    }, index=months)

    return quarterly, monthly_price, macros


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


# ---------- UTC-style Valuation ----------

def utc_valuation(price, refs, analysis_period, rescale_period):
    """
    UTC-style multi-reference valuation score, ±100.

    For each reference series, compute the % change in
    (price / reference) over `analysis_period`. Average those spreads
    across references, then rescale to ±100 over `rescale_period`.

    Positive  → price has run UP faster than the reference basket
                (housing expensive vs EUR strength / cost of money)
    Negative  → the reverse (housing cheap)
    """
    components = []
    for ref in refs:
        merged = pd.concat([price.rename("p"), ref.rename("r")], axis=1).dropna()
        ratio = merged["p"] / merged["r"]
        components.append(ratio.pct_change(analysis_period) * 100)
    combined = pd.concat(components, axis=1).mean(axis=1)

    rmin = combined.rolling(rescale_period).min()
    rmax = combined.rolling(rescale_period).max()
    mid = (rmin + rmax) / 2.0
    half = (rmax - rmin) / 2.0
    return ((combined - mid) / half * 100).clip(-100, 100)


# ---------- Seasonality ----------

def seasonality(price_monthly, lookback_years=SEASONALITY_YEARS):
    """
    Average yearly path of price as % from each year's January.

    Returns:
      seasonal_avg  pd.Series indexed 1..12 (month-of-year)
      current_path  pd.Series indexed 1..12 — current year so far
    """
    end = price_monthly.index.max()
    cur_year = end.year
    # take last `lookback_years` COMPLETE prior calendar years for the average
    first_year = cur_year - lookback_years
    paths = []
    for yr in range(first_year, cur_year):
        grp = price_monthly[price_monthly.index.year == yr]
        # need January present so the relative path starts at 0%
        if len(grp) < 6 or grp.index.month[0] != 1:
            continue
        rel = ((grp.values / grp.values[0]) - 1.0) * 100
        paths.append(pd.Series(rel, index=grp.index.month))

    if paths:
        seasonal_avg = pd.concat(paths, axis=1).mean(axis=1)
    else:
        seasonal_avg = pd.Series(dtype=float)

    cur = price_monthly[price_monthly.index.year == cur_year]
    if len(cur):
        cur_rel = ((cur.values / cur.values[0]) - 1.0) * 100
        cur_path = pd.Series(cur_rel, index=cur.index.month)
    else:
        cur_path = pd.Series(dtype=float)

    return seasonal_avg, cur_path


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
    ax.set_title("Average housing price (EUR / m², BGN÷1.95583) — monthly candles",
                 loc="left", fontsize=10, fontweight="bold")
    ax.set_ylabel("EUR / m²")
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
            "Average housing price (EUR / m², BGN÷1.95583) — monthly candles",
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

    fig.update_yaxes(title_text="EUR / m²", row=1, col=1)
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


def plot_valuation_html(monthly_price_eur, macros, out_path, source_label):
    """
    Valuation + Seasonality view (interactive HTML, 4 panes):
      1) Avg price candles (EUR / m²)
      2) Valuation 1M  (1-month analysis, 12-month rescale)
      3) Valuation 4M  (4-month analysis, 12-month rescale)
      4) Seasonality   (avg yearly path, last N years, vs current year)
    """
    aligned = pd.concat(
        [monthly_price_eur.rename("price"),
         macros["eurusd"], macros["euribor12m"]],
        axis=1,
    ).dropna()
    price = aligned["price"]
    refs = [
        aligned["eurusd"],
        # shift EURIBOR off zero so ratios are well-defined when negative
        (aligned["euribor12m"] + 6.0),
    ]

    val_1m = utc_valuation(price, refs, VAL_ANALYSIS_1M, VAL_RESCALE_MONTHS)
    val_4m = utc_valuation(price, refs, VAL_ANALYSIS_4M, VAL_RESCALE_MONTHS)
    seasonal_avg, cur_path = seasonality(price, SEASONALITY_YEARS)

    ohlc = synthesize_monthly_ohlc(price)

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=False,
        row_heights=[0.36, 0.21, 0.21, 0.22],
        vertical_spacing=0.075,
        subplot_titles=(
            "Average housing price (EUR / m², BGN÷1.95583) — monthly candles",
            f"Valuation 1M — vs EUR/USD + EURIBOR 12M (1-mo window, 12-mo rescale)",
            f"Valuation 4M — vs EUR/USD + EURIBOR 12M (4-mo window, 12-mo rescale)",
            f"Seasonality — avg yearly path, last {SEASONALITY_YEARS} years vs current year",
        ),
    )

    # 1) price candles
    fig.add_trace(go.Candlestick(
        x=ohlc.index, open=ohlc["open"], high=ohlc["high"],
        low=ohlc["low"], close=ohlc["close"],
        name="Avg price (EUR/m²)",
        increasing_line_color=GREEN, increasing_fillcolor=GREEN,
        decreasing_line_color=RED,   decreasing_fillcolor=RED,
        showlegend=False,
    ), row=1, col=1)
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)

    # 2) Valuation 1M  — purple (TradingView style)
    s = val_1m.dropna()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines", name="Valuation 1M",
        line=dict(color="#a040ff", width=1.6),
        hovertemplate="Val 1M: %{y:.1f}<extra></extra>",
        showlegend=False,
    ), row=2, col=1)
    fig.add_hline(y=VAL_UPPER, line=dict(color=RED,   width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=VAL_LOWER, line=dict(color=GREEN, width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=0,         line=dict(color="#888", width=0.7), row=2, col=1)
    fig.update_yaxes(range=[-110, 110], row=2, col=1)

    # 3) Valuation 4M
    s = val_4m.dropna()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines", name="Valuation 4M",
        line=dict(color=BLUE, width=1.6),
        hovertemplate="Val 4M: %{y:.1f}<extra></extra>",
        showlegend=False,
    ), row=3, col=1)
    fig.add_hline(y=VAL_UPPER, line=dict(color=RED,   width=1, dash="dash"), row=3, col=1)
    fig.add_hline(y=VAL_LOWER, line=dict(color=GREEN, width=1, dash="dash"), row=3, col=1)
    fig.add_hline(y=0,         line=dict(color="#888", width=0.7), row=3, col=1)
    fig.update_yaxes(range=[-110, 110], row=3, col=1)

    # 4) Seasonality
    if len(seasonal_avg):
        fig.add_trace(go.Scatter(
            x=seasonal_avg.index, y=seasonal_avg.values, mode="lines+markers",
            name=f"Avg of last {SEASONALITY_YEARS} yrs",
            line=dict(color="#a040ff", width=2),
            hovertemplate="Month %{x}: %{y:+.1f}%<extra></extra>",
        ), row=4, col=1)
    if len(cur_path):
        fig.add_trace(go.Scatter(
            x=cur_path.index, y=cur_path.values, mode="lines+markers",
            name="Current year",
            line=dict(color=BLUE, width=2, dash="dot"),
            hovertemplate="Month %{x}: %{y:+.1f}%<extra></extra>",
        ), row=4, col=1)
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        row=4, col=1,
    )

    fig.update_yaxes(title_text="EUR / m²", row=1, col=1)
    fig.update_yaxes(title_text="Valuation", row=2, col=1)
    fig.update_yaxes(title_text="Valuation", row=3, col=1)
    fig.update_yaxes(title_text="% from Jan", row=4, col=1)
    fig.update_xaxes(title_text="Date",     row=3, col=1)
    fig.update_xaxes(title_text="Month",    row=4, col=1)

    fig.update_layout(
        title=dict(
            text=f"<b>Bulgarian Housing — Valuation & Seasonality</b>  ·  data: {source_label}",
            x=0.02, xanchor="left",
        ),
        template="plotly_white",
        height=1180,
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        margin=dict(l=60, r=40, t=90, b=50),
    )
    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True)


# ---------- Entry point ----------

def main():
    live = os.environ.get("LIVE") == "1"
    if live:
        quarterly, monthly_price, macros = fetch_live_data()
        source_label = "LIVE (Eurostat + ECB SDW)"
    else:
        quarterly, monthly_price, macros = synthetic_demo_data()
        source_label = "SYNTHETIC (calibrated to published БНБ / НСИ stats)"

    # Convert prices BGN → EUR using fixed currency-board peg
    quarterly["avg_price"] = quarterly["avg_price"] / BGN_PER_EUR
    monthly_price_eur = monthly_price / BGN_PER_EUR

    model = build_cot_model(quarterly)
    model.to_csv("bg_housing_cot.csv", float_format="%.2f")
    plot_model(model, monthly_price_eur, "bg_housing_cot.png", source_label)
    plot_html(model, monthly_price_eur, "bg_housing_cot.html", source_label)
    plot_valuation_html(monthly_price_eur, macros,
                        "bg_housing_valuation.html", source_label)

    print(f"Source: {source_label}")
    print("Wrote: bg_housing_cot.csv, bg_housing_cot.png,")
    print("       bg_housing_cot.html, bg_housing_valuation.html")
    print()
    print("Last 4 quarters (COT, price in EUR/m²):")
    print(model[["avg_price", "commercials", "noncommercials", "retailers"]]
          .dropna().tail(4).round(1).to_string())


if __name__ == "__main__":
    main()
