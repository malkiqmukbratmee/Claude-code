"""
Confluence test — apply COT, Valuation, Seasonality (independently) to
TRADABLE real-estate proxies, find moments where ≥2 indicators agree on
the same direction, and measure forward returns.

No composite score — each indicator votes separately.

Tradables (synthetic, calibrated to real instrument history):
  EU Property ETF (IPRP-like, since 2007)
  BG REIT 6A6     (Advance Terrafund-like, since 2007)

Extremes (per-indicator, per-month):
  COT          any leg ≤ 20 → BUY vote ;  any leg ≥ 80 → SELL vote
  Valuation 4M ≤ -75       → BUY vote ;          ≥ +75 → SELL vote
  Seasonality  cur-year path ≥ 7% BELOW avg → BUY ; ≥ 7% ABOVE avg → SELL

Confluence = ≥ 2 BUY votes  or  ≥ 2 SELL votes  in the same month.

Output:
  bg_housing_confluence.html   — tradable charts + markers + backtest tables
"""

import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from bg_housing_cot import (
    _anchored_series,
    synthetic_demo_data,
    fetch_live_data,
    build_cot_model,
    utc_valuation,
    seasonality,
    synthesize_monthly_ohlc,
    BGN_PER_EUR,
    VAL_ANALYSIS_1M,
    VAL_ANALYSIS_4M,
    VAL_RESCALE_MONTHS,
    SEASONALITY_YEARS,
    LOOKBACK_QUARTERS,
    UPPER_THRESHOLD,
    LOWER_THRESHOLD,
    VAL_UPPER,
    VAL_LOWER,
    GREEN, RED, BLUE, YELLOW,
)


SEASONAL_DEV_THRESHOLD = 7.0     # % deviation of current-year vs avg path
BACKTEST_HORIZONS_MONTHS = [1, 3, 6, 12]


# ---------- Synthetic tradable proxies ----------

def synth_tradables(months):
    """
    Monthly price series for tradable real-estate proxies.
    Anchors reflect actual cycle history (boom 2007, crash 2008-09, slow
    recovery, COVID bump, 2022 rate-shock, partial rebound).
    """
    def mi(y, m): return (y - 2007) * 12 + (m - 1)

    iprp = _anchored_series(months, {
        mi(2007, 1):  38.0,
        mi(2007, 7):  48.0,
        mi(2008, 1):  44.0,
        mi(2008, 12): 22.0,   # crisis trough
        mi(2009, 12): 28.0,
        mi(2011, 12): 26.0,
        mi(2014, 12): 33.0,
        mi(2016, 12): 40.0,
        mi(2018, 12): 42.0,
        mi(2019, 12): 47.0,
        mi(2020, 3):  32.0,   # COVID
        mi(2020, 12): 42.0,
        mi(2021, 9):  48.0,   # all-time-ish high
        mi(2022, 12): 26.0,   # rate-shock crash
        mi(2023, 6):  28.0,
        mi(2024, 12): 36.0,
        mi(2026, 4):  38.5,
    }, noise_std=0.60, seed=41)

    bg_reit = _anchored_series(months, {
        mi(2007, 1):  1.00,
        mi(2007, 12): 2.70,   # BG boom
        mi(2008, 12): 1.20,
        mi(2010, 6):  0.55,   # trough
        mi(2012, 12): 0.85,
        mi(2015, 12): 1.20,
        mi(2018, 12): 1.55,
        mi(2020, 6):  1.30,
        mi(2021, 12): 1.90,
        mi(2023, 6):  2.10,
        mi(2024, 12): 2.55,
        mi(2026, 4):  2.80,
    }, noise_std=0.02, seed=43)

    return pd.DataFrame({"iprp": iprp, "bg_reit": bg_reit}, index=months)


# ---------- Extreme flag detection ----------

def _bool_to_int(s):
    return s.fillna(False).astype(int)


def detect_per_indicator_extremes(price_monthly, cot_model_q, macros):
    """
    Build a MONTHLY dataframe with per-indicator BUY / SELL votes.

    Returns columns:
      cot_buy, cot_sell  (any leg < LOWER or > UPPER)
      val_buy, val_sell  (4M valuation < VAL_LOWER or > VAL_UPPER)
      seas_buy, seas_sell  (current-yr path vs avg, ±SEASONAL_DEV_THRESHOLD)
    """
    idx = price_monthly.index

    # --- COT (quarterly → forward-fill monthly) ---
    cot_q = cot_model_q[["commercials", "noncommercials", "retailers"]]
    cot_m = cot_q.reindex(idx, method="ffill")
    cot_buy  = (cot_m <= LOWER_THRESHOLD).any(axis=1)
    cot_sell = (cot_m >= UPPER_THRESHOLD).any(axis=1)

    # --- Valuation 4M ---
    aligned = pd.concat([price_monthly.rename("p"),
                         macros["eurusd"], macros["euribor12m"]], axis=1).dropna()
    refs = [aligned["eurusd"], aligned["euribor12m"] + 6.0]
    val_4m = utc_valuation(aligned["p"], refs,
                           VAL_ANALYSIS_4M, VAL_RESCALE_MONTHS).reindex(idx)
    val_buy  = val_4m <= VAL_LOWER
    val_sell = val_4m >= VAL_UPPER

    # --- Seasonality (compute for each month using 4-yr trailing average) ---
    # For each month-end, compute the avg yearly path of the prior 4 complete
    # years, and the current year's path; flag if deviation > threshold.
    seas_buy = pd.Series(False, index=idx)
    seas_sell = pd.Series(False, index=idx)
    for d in idx:
        # use data up to d (no look-ahead)
        slice_ = price_monthly.loc[:d]
        if len(slice_) < 24:
            continue
        try:
            avg_path, cur_path = seasonality(slice_, lookback_years=4)
        except Exception:
            continue
        m = d.month
        if m in cur_path.index and m in avg_path.index:
            dev = float(cur_path[m]) - float(avg_path[m])
            if dev <= -SEASONAL_DEV_THRESHOLD:
                seas_buy[d] = True
            elif dev >= SEASONAL_DEV_THRESHOLD:
                seas_sell[d] = True

    return pd.DataFrame({
        "cot_buy":  _bool_to_int(cot_buy),
        "cot_sell": _bool_to_int(cot_sell),
        "val_buy":  _bool_to_int(val_buy),
        "val_sell": _bool_to_int(val_sell),
        "val_4m":   val_4m,
        "seas_buy": _bool_to_int(seas_buy),
        "seas_sell": _bool_to_int(seas_sell),
    }, index=idx)


# ---------- Confluence detection ----------

def find_confluences(extremes):
    """A month is a confluence if ≥ 2 votes line up in the same direction."""
    buy_votes  = extremes[["cot_buy",  "val_buy",  "seas_buy"]].sum(axis=1)
    sell_votes = extremes[["cot_sell", "val_sell", "seas_sell"]].sum(axis=1)
    confluence = pd.DataFrame({
        "buy_votes": buy_votes,
        "sell_votes": sell_votes,
        "is_buy":  buy_votes >= 2,
        "is_sell": sell_votes >= 2,
    }, index=extremes.index)
    return confluence


def collapse_consecutive(flags):
    """Reduce streaks of consecutive True flags to the FIRST month only."""
    out = flags & ~flags.shift(1, fill_value=False)
    return out


# ---------- Backtest ----------

def backtest_signals(price_monthly, confluence, horizons=BACKTEST_HORIZONS_MONTHS):
    """
    For each first-of-streak signal, compute forward returns at every horizon.

    Returns:
      events_df  one row per signal event (date, direction, votes, rets)
      summary    per-direction summary stats
    """
    buy_events  = collapse_consecutive(confluence["is_buy"])
    sell_events = collapse_consecutive(confluence["is_sell"])

    records = []
    for d in price_monthly.index[buy_events]:
        rec = {"date": d, "direction": "BUY",
               "buy_votes": int(confluence.loc[d, "buy_votes"])}
        for h in horizons:
            tgt = d + pd.DateOffset(months=h)
            if tgt in price_monthly.index:
                rec[f"r_{h}m"] = (price_monthly[tgt] / price_monthly[d] - 1) * 100
            else:
                later = price_monthly.index[price_monthly.index >= tgt]
                rec[f"r_{h}m"] = (
                    (price_monthly[later[0]] / price_monthly[d] - 1) * 100
                    if len(later) else np.nan
                )
        records.append(rec)
    for d in price_monthly.index[sell_events]:
        rec = {"date": d, "direction": "SELL",
               "sell_votes": int(confluence.loc[d, "sell_votes"])}
        for h in horizons:
            tgt = d + pd.DateOffset(months=h)
            if tgt in price_monthly.index:
                rec[f"r_{h}m"] = (price_monthly[tgt] / price_monthly[d] - 1) * 100
            else:
                later = price_monthly.index[price_monthly.index >= tgt]
                rec[f"r_{h}m"] = (
                    (price_monthly[later[0]] / price_monthly[d] - 1) * 100
                    if len(later) else np.nan
                )
        records.append(rec)

    events_df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)

    summary = []
    for direction in ["BUY", "SELL"]:
        sub = events_df[events_df["direction"] == direction]
        row = {"direction": direction, "n_events": len(sub)}
        for h in horizons:
            col = f"r_{h}m"
            vals = sub[col].dropna()
            row[f"mean_{h}m"] = vals.mean() if len(vals) else np.nan
            row[f"median_{h}m"] = vals.median() if len(vals) else np.nan
            if direction == "BUY":
                row[f"hit_{h}m"] = (vals > 0).mean() * 100 if len(vals) else np.nan
            else:  # SELL
                row[f"hit_{h}m"] = (vals < 0).mean() * 100 if len(vals) else np.nan
        # baseline (all months) return
        row["baseline_12m"] = (
            price_monthly.pct_change(12).dropna().mean() * 100
        )
        summary.append(row)
    return events_df, pd.DataFrame(summary)


# ---------- Per-instrument analysis ----------

def analyze_instrument(name, price_monthly, cot_model_q, macros):
    extremes = detect_per_indicator_extremes(price_monthly, cot_model_q, macros)
    confluence = find_confluences(extremes)
    events, summary = backtest_signals(price_monthly, confluence)

    # also compute the per-instrument indicators for plotting
    aligned = pd.concat([price_monthly.rename("p"),
                         macros["eurusd"], macros["euribor12m"]], axis=1).dropna()
    refs = [aligned["eurusd"], aligned["euribor12m"] + 6.0]
    val_1m = utc_valuation(aligned["p"], refs,
                           VAL_ANALYSIS_1M, VAL_RESCALE_MONTHS)
    val_4m = utc_valuation(aligned["p"], refs,
                           VAL_ANALYSIS_4M, VAL_RESCALE_MONTHS)
    seas_avg, seas_cur = seasonality(price_monthly, SEASONALITY_YEARS)

    return {
        "name": name,
        "price": price_monthly,
        "extremes": extremes,
        "confluence": confluence,
        "events": events,
        "summary": summary,
        "val_1m": val_1m,
        "val_4m": val_4m,
        "cot": cot_model_q,
        "seasonal_avg": seas_avg,
        "seasonal_cur": seas_cur,
    }


# ---------- HTML report ----------

def _events_html_table(events):
    if len(events) == 0:
        return "<p><em>No confluence events.</em></p>"
    cols = ["date", "direction", "r_1m", "r_3m", "r_6m", "r_12m"]
    rows = []
    for _, r in events.iterrows():
        rows.append("<tr>"
                    f"<td>{r['date'].strftime('%Y-%m')}</td>"
                    f"<td class='{r['direction'].lower()}'>{r['direction']}</td>"
                    + "".join(
                        f"<td class='{ 'pos' if pd.notna(r[c]) and r[c] > 0 else 'neg' }'>"
                        f"{r[c]:+.1f}%" + "</td>" if pd.notna(r[c]) else "<td>—</td>"
                        for c in cols[2:]
                    )
                    + "</tr>")
    head = "<thead><tr><th>Date</th><th>Dir</th><th>+1M</th><th>+3M</th><th>+6M</th><th>+12M</th></tr></thead>"
    return f"<table class='events'>{head}<tbody>{''.join(rows)}</tbody></table>"


def _summary_html_table(summary):
    rows = []
    for _, r in summary.iterrows():
        rows.append("<tr>"
                    f"<td class='{r['direction'].lower()}'>{r['direction']}</td>"
                    f"<td>{int(r['n_events'])}</td>"
                    + "".join(
                        f"<td>{r[f'mean_{h}m']:+.1f}%</td>"
                        f"<td>{r[f'hit_{h}m']:.0f}%</td>"
                        if pd.notna(r[f'mean_{h}m']) else "<td>—</td><td>—</td>"
                        for h in BACKTEST_HORIZONS_MONTHS
                    )
                    + "</tr>")
    head = ("<thead><tr><th>Dir</th><th>N</th>"
            + "".join(f"<th>μ{h}M</th><th>hit{h}M</th>"
                      for h in BACKTEST_HORIZONS_MONTHS)
            + "</tr></thead>")
    base = summary['baseline_12m'].iloc[0] if len(summary) else float('nan')
    return (f"<table class='summary'>{head}<tbody>{''.join(rows)}</tbody></table>"
            f"<p class='base'>Baseline mean 12-mo return (all months): "
            f"{base:+.1f}%</p>")


def _make_instrument_figure(name, result):
    ohlc = synthesize_monthly_ohlc(result["price"])
    cot = result["cot"]
    val_1m = result["val_1m"]
    val_4m = result["val_4m"]
    seas_avg = result["seasonal_avg"]
    seas_cur = result["seasonal_cur"]
    events = result["events"]

    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=False,
        row_heights=[0.32, 0.20, 0.14, 0.14, 0.20],
        vertical_spacing=0.045,
        subplot_titles=(
            f"{name} — monthly candles + confluence markers",
            f"COT Index (BG positioning, {LOOKBACK_QUARTERS}Q lookback) — "
            "Commercials / Non-com / Retailers",
            "Valuation 1M (vs EUR/USD + EURIBOR12M, 1-mo / 12-mo rescale)",
            "Valuation 4M (vs EUR/USD + EURIBOR12M, 4-mo / 12-mo rescale)",
            f"Seasonality — avg last {SEASONALITY_YEARS} yrs vs current year",
        ),
    )

    # --- 1) Candles + markers ---
    fig.add_trace(go.Candlestick(
        x=ohlc.index, open=ohlc["open"], high=ohlc["high"],
        low=ohlc["low"], close=ohlc["close"],
        increasing_line_color=GREEN, increasing_fillcolor=GREEN,
        decreasing_line_color=RED,   decreasing_fillcolor=RED,
        name=name, showlegend=False,
    ), row=1, col=1)
    buys  = events[events["direction"] == "BUY"]
    sells = events[events["direction"] == "SELL"]
    if len(buys):
        y = [float(ohlc.loc[d, "low"]) * 0.96 for d in buys["date"]]
        fig.add_trace(go.Scatter(
            x=list(buys["date"]), y=y, mode="markers",
            marker=dict(symbol="triangle-up", size=13, color=GREEN,
                        line=dict(color="#222", width=1)),
            name="BUY conf",
            hovertemplate="BUY %{x|%Y-%m}<extra></extra>",
        ), row=1, col=1)
    if len(sells):
        y = [float(ohlc.loc[d, "high"]) * 1.04 for d in sells["date"]]
        fig.add_trace(go.Scatter(
            x=list(sells["date"]), y=y, mode="markers",
            marker=dict(symbol="triangle-down", size=13, color=RED,
                        line=dict(color="#222", width=1)),
            name="SELL conf",
            hovertemplate="SELL %{x|%Y-%m}<extra></extra>",
        ), row=1, col=1)

    # --- 2) COT (3 legs combined) ---
    for label, col, color in [
        ("Commercials",      "commercials",    GREEN),
        ("Non-commercials",  "noncommercials", YELLOW),
        ("Retailers",        "retailers",      RED),
    ]:
        s = cot[col].dropna()
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines", name=label,
            line=dict(color=color, width=1.4),
            hovertemplate=label + ": %{y:.0f}<extra></extra>",
            showlegend=(name == "EU Property ETF (IPRP-like)"),
            legendgroup="cot", legendgrouptitle_text="COT legs",
        ), row=2, col=1)
    fig.add_hline(y=UPPER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=LOWER_THRESHOLD, line=dict(color="#888", width=1, dash="dash"), row=2, col=1)
    fig.add_hrect(y0=UPPER_THRESHOLD, y1=100, fillcolor=RED, opacity=0.05,
                  line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=LOWER_THRESHOLD, fillcolor=GREEN, opacity=0.05,
                  line_width=0, row=2, col=1)
    fig.update_yaxes(range=[-5, 105], row=2, col=1)

    # --- 3) Val 1M ---
    s = val_1m.dropna()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines", showlegend=False,
        line=dict(color="#a040ff", width=1.5),
        hovertemplate="Val 1M: %{y:.1f}<extra></extra>",
    ), row=3, col=1)
    fig.add_hline(y=VAL_UPPER, line=dict(color=RED,   width=1, dash="dash"), row=3, col=1)
    fig.add_hline(y=VAL_LOWER, line=dict(color=GREEN, width=1, dash="dash"), row=3, col=1)
    fig.add_hline(y=0, line=dict(color="#888", width=0.7), row=3, col=1)
    fig.update_yaxes(range=[-110, 110], row=3, col=1)

    # --- 4) Val 4M ---
    s = val_4m.dropna()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines", showlegend=False,
        line=dict(color=BLUE, width=1.5),
        hovertemplate="Val 4M: %{y:.1f}<extra></extra>",
    ), row=4, col=1)
    fig.add_hline(y=VAL_UPPER, line=dict(color=RED,   width=1, dash="dash"), row=4, col=1)
    fig.add_hline(y=VAL_LOWER, line=dict(color=GREEN, width=1, dash="dash"), row=4, col=1)
    fig.add_hline(y=0, line=dict(color="#888", width=0.7), row=4, col=1)
    fig.update_yaxes(range=[-110, 110], row=4, col=1)

    # --- 5) Seasonality ---
    if len(seas_avg):
        fig.add_trace(go.Scatter(
            x=seas_avg.index, y=seas_avg.values, mode="lines+markers",
            name=f"Avg last {SEASONALITY_YEARS} yrs",
            line=dict(color="#a040ff", width=2),
            hovertemplate="M%{x}: %{y:+.1f}%<extra></extra>",
            showlegend=(name == "EU Property ETF (IPRP-like)"),
            legendgroup="seas", legendgrouptitle_text="Seasonality",
        ), row=5, col=1)
    if len(seas_cur):
        fig.add_trace(go.Scatter(
            x=seas_cur.index, y=seas_cur.values, mode="lines+markers",
            name="Current year",
            line=dict(color=BLUE, width=2, dash="dot"),
            hovertemplate="M%{x}: %{y:+.1f}%<extra></extra>",
            showlegend=(name == "EU Property ETF (IPRP-like)"),
            legendgroup="seas",
        ), row=5, col=1)
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"],
        row=5, col=1,
    )

    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="COT", row=2, col=1)
    fig.update_yaxes(title_text="Val 1M", row=3, col=1)
    fig.update_yaxes(title_text="Val 4M", row=4, col=1)
    fig.update_yaxes(title_text="% from Jan", row=5, col=1)
    fig.update_xaxes(title_text="Month", row=5, col=1)

    fig.update_layout(
        template="plotly_white", height=1180,
        margin=dict(l=55, r=30, t=80, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.005,
                    xanchor="left", x=0),
    )
    return fig


def build_html_report(results, macros, monthly_price_bg, out_path, source_label):
    sections = []
    for r in results:
        fig = _make_instrument_figure(r["name"], r)
        chart_div = fig.to_html(include_plotlyjs=False, full_html=False,
                                div_id=f"chart_{abs(hash(r['name']))}")

        sections.append(f"""
<section class='instrument'>
  <h2>{r['name']}</h2>
  {chart_div}
  <div class='tables'>
    <div class='col'>
      <h3>Confluence events</h3>
      {_events_html_table(r['events'])}
    </div>
    <div class='col'>
      <h3>Summary (forward returns by direction)</h3>
      {_summary_html_table(r['summary'])}
    </div>
  </div>
</section>
""")

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'>
<title>BG Housing — Confluence Test on Tradables</title>
<script src='https://cdn.plot.ly/plotly-latest.min.js'></script>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 24px;
         background:#fafafa; color:#222; }}
  h1 {{ margin-bottom: 4px; }}
  .src {{ color:#666; font-size:13px; margin-bottom: 22px; }}
  .legend {{ background:#fff; border:1px solid #ddd; padding:12px 16px;
             border-radius:8px; margin-bottom:22px; font-size:13px; line-height:1.5; }}
  section.instrument {{ background:#fff; border:1px solid #ddd; border-radius:8px;
                        padding:14px 18px; margin-bottom:22px; }}
  .tables {{ display:flex; gap:24px; flex-wrap:wrap; }}
  .col {{ flex:1; min-width:340px; }}
  table {{ border-collapse:collapse; width:100%; font-size:12px; }}
  th, td {{ padding:4px 8px; border-bottom:1px solid #eee; text-align:right; }}
  th {{ background:#f4f4f4; text-align:right; }}
  td:first-child, th:first-child {{ text-align:left; }}
  .buy  {{ color:{GREEN}; font-weight:600; }}
  .sell {{ color:{RED};   font-weight:600; }}
  .pos  {{ color:{GREEN}; }}
  .neg  {{ color:{RED};   }}
  .base {{ font-size:12px; color:#666; margin-top:6px; }}
</style></head>
<body>
  <h1>BG Housing — Confluence Test on Tradables</h1>
  <div class='src'>data: {source_label}</div>
  <div class='legend'>
    <strong>Method:</strong> three indicators flag extremes independently —
    <strong>COT</strong> (any leg ≤{LOWER_THRESHOLD} buy / ≥{UPPER_THRESHOLD} sell),
    <strong>Valuation 4M</strong> (≤{VAL_LOWER} buy / ≥{VAL_UPPER} sell),
    <strong>Seasonality</strong> (current-yr path ±{SEASONAL_DEV_THRESHOLD}% vs avg).
    A <em>confluence</em> is when ≥ 2 votes line up in the same direction in
    the same month. Forward returns measured from the first month of each streak.
  </div>
  {''.join(sections)}
</body></html>"""
    with open(out_path, "w") as f:
        f.write(html)


# ---------- Entry point ----------

def main():
    live = os.environ.get("LIVE") == "1"
    if live:
        quarterly, monthly_price, macros = fetch_live_data()
        source_label = "LIVE (Eurostat + ECB SDW)"
    else:
        quarterly, monthly_price, macros = synthetic_demo_data()
        source_label = "SYNTHETIC (calibrated to published stats)"

    # price → EUR/m²
    quarterly["avg_price"] = quarterly["avg_price"] / BGN_PER_EUR
    monthly_price_eur = monthly_price / BGN_PER_EUR
    cot_model = build_cot_model(quarterly)

    # tradables
    tradables = synth_tradables(monthly_price_eur.index)

    instruments = [
        ("EU Property ETF (IPRP-like)", tradables["iprp"]),
        ("BG REIT — 6A6 (Advance Terrafund-like)", tradables["bg_reit"]),
        ("BG avg housing (EUR/m²) — reference", monthly_price_eur),
    ]
    results = [analyze_instrument(name, p, cot_model, macros)
               for name, p in instruments]

    build_html_report(results, macros, monthly_price_eur,
                      "bg_housing_confluence.html", source_label)

    print(f"Source: {source_label}")
    print("Wrote bg_housing_confluence.html")
    print()
    for r in results:
        n_buy = (r["events"]["direction"] == "BUY").sum()
        n_sell = (r["events"]["direction"] == "SELL").sum()
        print(f"  {r['name']}: {n_buy} BUY events, {n_sell} SELL events")
        for _, row in r["summary"].iterrows():
            print(f"     {row['direction']:5s}  n={int(row['n_events'])}"
                  f"  μ12M={row['mean_12m']:+5.1f}%"
                  f"  hit12M={row['hit_12m']:.0f}%")


if __name__ == "__main__":
    main()
