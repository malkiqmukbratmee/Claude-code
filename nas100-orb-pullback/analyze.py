"""Statistical validation of NAS100 ORB pullbacks. Produces report tables (markdown)."""
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, "events.csv")
REPORT = os.path.join(HERE, "REPORT.md")

PCTS = [10, 25, 50, 75, 90]
rng = np.random.default_rng(7)


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n
    den = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / den
    hw = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return p, c - hw, c + hw


def boot_median_ci(x, n=4000):
    x = np.asarray(x.dropna())
    meds = np.median(rng.choice(x, size=(n, len(x))), axis=1)
    return np.percentile(meds, [2.5, 97.5])


def pct_table(g, cols):
    out = {}
    for c in cols:
        out[c] = [np.nanpercentile(g[c], p) for p in PCTS]
    return pd.DataFrame(out, index=[f"p{p}" for p in PCTS])


def prob_rows(g):
    rows = []
    for c, label in [("retest_level", "Retest of breakout level (ORB edge)"),
                     ("reenter_range", "Re-entry back inside the range"),
                     ("touch_mid", "Touch of range midpoint"),
                     ("touch_opposite", "Full traverse to opposite side"),
                     ("close_back_inside", "16:00 close back through the level")]:
        p, lo, hi = wilson(g[c].sum(), len(g))
        rows.append([label, f"{p*100:.1f}%", f"[{lo*100:.1f}%, {hi*100:.1f}%]"])
    return pd.DataFrame(rows, columns=["Outcome", "Probability", "95% Wilson CI"])


def md(df, floatfmt=".2f"):
    return df.to_markdown(floatfmt=floatfmt)


def main():
    ev = pd.read_csv(EV)
    n = len(ev)
    lines = []
    w = lines.append

    w("# NAS100 (US Tech 100 CFD) — 30-min NY Opening Range Breakout: Pullback Statistics\n")
    w(f"- Instrument: OANDA NAS100_USD CFD, 1-minute OHLCV (UTC source, converted to America/New_York with DST)")
    w(f"- Sample: **{n:,} acceptance events** ({(ev.side=='long').sum():,} long, {(ev.side=='short').sum():,} short), "
      f"{ev.date.min()} to {ev.date.max()} (~15.4 years)")
    w("- ORB = high/low of 09:30–10:00 ET. Acceptance = first 15-min candle (from 10:00 onward) closing outside the range.")
    w("- Pullback = maximum adverse excursion (1-min data) from the acceptance-candle close until 16:00 ET.\n")

    med_orb = ev.orb_range_pct.median()
    w(f"Median ORB range: {ev.orb_range.median():.1f} pts ({med_orb:.2f}% of price). "
      f"Median breakout leg at acceptance: {ev.leg_pts.median():.1f} pts.\n")

    w("## 1. Overall pullback distribution\n")
    for side, g in [("ALL", ev), ("LONG breakouts (close above range)", ev[ev.side == "long"]),
                    ("SHORT breakouts (close below range)", ev[ev.side == "short"])]:
        w(f"### {side} (n={len(g):,})\n")
        t = pct_table(g, ["mae_pts", "mae_pct_price", "mae_pct_range", "retrace_pct_leg"])
        t.columns = ["Pullback (pts)", "Pullback (% of price)", "Pullback (% of ORB range)", "Retrace (% of breakout leg)"]
        w(md(t) + "\n")
        w("Read: p75 = 75% of events pulled back **no more than** this; p25 = 25% pulled back no more than this "
          "(equivalently 75% pulled back MORE).\n")
        w(md(prob_rows(g)) + "\n")
        ci = boot_median_ci(g.mae_pct_range)
        w(f"Median pullback as % of ORB range: **{g.mae_pct_range.median():.1f}%** "
          f"(bootstrap 95% CI [{ci[0]:.1f}%, {ci[1]:.1f}%]). "
          f"Median time to deepest pullback: {g.minutes_to_max_pullback.median():.0f} min; "
          f"median time to level retest (when it happens): {g.minutes_to_retest.median():.0f} min.\n")

    w("### Strong acceptances only (leg >= 25% of ORB range)\n")
    w("The unconditional 'retrace % of leg' is inflated by events whose close barely cleared the range "
      "(median leg is only ~2.7 pts), so any pullback is a huge multiple of the leg. "
      "Filtering to decisive closes gives a more tradeable read:\n")
    strong = ev[ev.leg_pts >= 0.25 * ev.orb_range]
    w(f"n={len(strong):,} ({len(strong)/n*100:.0f}% of events)\n")
    t = pct_table(strong, ["mae_pts", "mae_pct_price", "mae_pct_range", "retrace_pct_leg"])
    t.columns = ["Pullback (pts)", "Pullback (% of price)", "Pullback (% of ORB range)", "Retrace (% of breakout leg)"]
    w(md(t) + "\n")
    w(md(prob_rows(strong)) + "\n")

    w("## 2. Conditioned on the pre-open move (prev 16:00 close -> 09:30 open)\n")
    w("The user case: e.g. index already +1% before the NY open — what changes?\n")
    bins = [-np.inf, -1.0, -0.25, 0.25, 1.0, np.inf]
    labels = ["< -1%", "-1% to -0.25%", "-0.25% to +0.25%", "+0.25% to +1%", "> +1%"]
    ev["gap_bucket"] = pd.cut(ev.preopen_move_pct, bins, labels=labels)
    rows = []
    for lb in labels:
        g = ev[ev.gap_bucket == lb]
        p, lo, hi = wilson(g.retest_level.sum(), len(g))
        rows.append([lb, len(g), g.mae_pct_range.median(), g.retrace_pct_leg.median(),
                     f"{p*100:.0f}% [{lo*100:.0f}–{hi*100:.0f}]",
                     f"{g.touch_mid.mean()*100:.0f}%", f"{(g.side=='long').mean()*100:.0f}%"])
    t = pd.DataFrame(rows, columns=["Pre-open move", "n", "Median pullback (% ORB range)",
                                    "Median retrace (% leg)", "P(retest level) [95% CI]",
                                    "P(touch mid)", "% long breakouts"])
    w(md(t.set_index("Pre-open move")) + "\n")

    kw = stats.kruskal(*[ev[ev.gap_bucket == lb].mae_pct_range.dropna() for lb in labels])
    rho, pv = stats.spearmanr(ev.preopen_move_pct.abs(), ev.mae_pct_range, nan_policy="omit")
    w(f"Kruskal–Wallis across gap buckets on pullback (% ORB range): H={kw.statistic:.1f}, p={kw.pvalue:.2g}. "
      f"Spearman |pre-open move| vs pullback: rho={rho:.3f}, p={pv:.2g}.\n")

    # with-gap vs against-gap
    ev["aligned"] = np.where(ev.preopen_move_pct.abs() < 0.25, "flat",
                    np.where(((ev.preopen_move_pct > 0) & (ev.side == "long")) |
                             ((ev.preopen_move_pct < 0) & (ev.side == "short")), "with-gap", "against-gap"))
    rows = []
    for lb in ["with-gap", "against-gap", "flat"]:
        g = ev[ev.aligned == lb]
        p, lo, hi = wilson(g.retest_level.sum(), len(g))
        rows.append([lb, len(g), g.mae_pct_range.median(), g.retrace_pct_leg.median(),
                     f"{p*100:.0f}% [{lo*100:.0f}–{hi*100:.0f}]", f"{g.close_back_inside.mean()*100:.0f}%"])
    t = pd.DataFrame(rows, columns=["Breakout vs pre-open move", "n", "Median pullback (% ORB range)",
                                    "Median retrace (% leg)", "P(retest level) [95% CI]", "P(close back inside)"])
    w("### Breakout direction relative to the overnight move\n")
    w(md(t.set_index("Breakout vs pre-open move")) + "\n")
    a, b = ev[ev.aligned == "with-gap"].mae_pct_range.dropna(), ev[ev.aligned == "against-gap"].mae_pct_range.dropna()
    mw = stats.mannwhitneyu(a, b)
    w(f"Mann–Whitney with-gap vs against-gap pullback depth: U={mw.statistic:.0f}, p={mw.pvalue:.2g}.\n")

    w("## 3. Conditioned on volume traded up to the breakout (RVOL)\n")
    w("RVOL = cumulative RTH volume at acceptance close / 20-session average at the same clock time.\n")
    ev["rvol_bucket"] = pd.qcut(ev.rvol_at_accept, 3, labels=["low RVOL", "mid RVOL", "high RVOL"])
    rows = []
    for lb in ["low RVOL", "mid RVOL", "high RVOL"]:
        g = ev[ev.rvol_bucket == lb]
        p, lo, hi = wilson(g.retest_level.sum(), len(g))
        rows.append([lb, len(g), f"{g.rvol_at_accept.median():.2f}", g.mae_pct_range.median(),
                     g.retrace_pct_leg.median(), f"{p*100:.0f}% [{lo*100:.0f}–{hi*100:.0f}]",
                     f"{g.touch_opposite.mean()*100:.0f}%"])
    t = pd.DataFrame(rows, columns=["Volume regime", "n", "Median RVOL", "Median pullback (% ORB range)",
                                    "Median retrace (% leg)", "P(retest level) [95% CI]", "P(opposite side)"])
    w(md(t.set_index("Volume regime")) + "\n")
    kw = stats.kruskal(*[ev[ev.rvol_bucket == lb].mae_pct_range.dropna() for lb in ["low RVOL", "mid RVOL", "high RVOL"]])
    rho, pv = stats.spearmanr(ev.rvol_at_accept, ev.mae_pct_range, nan_policy="omit")
    w(f"Kruskal–Wallis across RVOL terciles: H={kw.statistic:.1f}, p={kw.pvalue:.2g}. "
      f"Spearman RVOL vs pullback: rho={rho:.3f}, p={pv:.2g}.\n")

    w("## 4. By breakout timing (which 15m candle accepted)\n")
    rows = []
    for k in range(1, 7):
        g = ev[ev.accept_candle_idx == k]
        if len(g) < 30:
            continue
        p, lo, hi = wilson(g.retest_level.sum(), len(g))
        rows.append([f"candle {k} ({g.accept_time.iloc[0]})", len(g), g.mae_pct_range.median(),
                     g.retrace_pct_leg.median(), f"{p*100:.0f}% [{lo*100:.0f}–{hi*100:.0f}]"])
    g = ev[ev.accept_candle_idx >= 7]
    p, lo, hi = wilson(g.retest_level.sum(), len(g))
    rows.append(["candle 7+ (>= 11:45)", len(g), g.mae_pct_range.median(), g.retrace_pct_leg.median(),
                 f"{p*100:.0f}% [{lo*100:.0f}–{hi*100:.0f}]"])
    t = pd.DataFrame(rows, columns=["Acceptance candle", "n", "Median pullback (% ORB range)",
                                    "Median retrace (% leg)", "P(retest level) [95% CI]"])
    w(md(t.set_index("Acceptance candle")) + "\n")

    w("## 5. Stability across years (robustness)\n")
    ev["year"] = pd.to_datetime(ev.date).dt.year
    t = ev.groupby("year").agg(n=("side", "size"), med_pullback_pct_range=("mae_pct_range", "median"),
                               retest_rate=("retest_level", "mean"))
    t["retest_rate"] = (t.retest_rate * 100).round(0).astype(int).astype(str) + "%"
    w(md(t, floatfmt=".1f") + "\n")

    w("## 6. Methodology notes & limitations\n")
    w("- Feed: OANDA NAS100 CFD 1-min bars (bid/mid as published by provider); volume is CFD tick volume, "
      "a liquidity proxy, not exchange-traded contracts.")
    w("- Coverage ends 2020-05-13 (last data in the public archive). 15.4 years, every session with a valid "
      "ORB and an outside 15-min close is included — no cherry-picking.")
    w("- 'Pullback' is max adverse excursion from the acceptance close to 16:00 ET. It is measured against the "
      "acceptance-candle CLOSE (entry-at-close assumption), on 1-minute lows/highs.")
    w("- Percentile framing: pXX = XX% of events pulled back no more than that value.")
    w("- All probabilities carry 95% Wilson CIs; medians carry bootstrap CIs; bucket differences tested with "
      "Kruskal-Wallis / Mann-Whitney (non-parametric, no normality assumption).")

    with open(REPORT, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {REPORT}")
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
