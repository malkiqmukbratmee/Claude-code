"""Follow-up study: the candle AFTER the acceptance close (+1 candle) and the
path to the Previous Day High (PDH).

For LONG acceptances (first 15m close above the 30-min NY opening range):
  1. +1 candle (the 15 minutes right after the acceptance close): how far does
     its low pull back, measured vs the acceptance close and vs the ORB high
     (negative distance = dipped back inside the range)?
  2. Continuation to PDH: among events not already above PDH at acceptance,
     how often does price go on to touch the previous session's high before
     16:00 ET, and for those that do — how deep was the pullback BEFORE the
     touch (the "how far back toward the ORB does it come first" question)?
Short side is mirrored against the Previous Day Low for symmetry.

PDH definitions computed:
  - pdh_rth:   previous session 09:30-16:00 ET high  (primary)
  - pdh_daily: previous completed 17:00->17:00 ET daily candle high
"""
import os

import numpy as np
import pandas as pd

from prepare_data import load

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, "events.csv")
OUT = os.path.join(HERE, "REPORT_PLUS1_PDH.md")
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


def main():
    df = load()
    ev = pd.read_csv(EV, parse_dates=["date"])
    rth = df.between_time("09:30", "15:59")
    rth = rth[rth.index.dayofweek < 5]
    sessions = {d: g for d, g in rth.groupby(rth.index.date)}
    dates = sorted(sessions)
    prev_rth_high = {}
    prev_rth_low = {}
    for i, d in enumerate(dates):
        if i:
            prev_rth_high[d] = sessions[dates[i - 1]]["high"].max()
            prev_rth_low[d] = sessions[dates[i - 1]]["low"].min()

    # previous completed 17:00->17:00 ET daily candle
    roll = df.copy()
    roll_date = (roll.index - pd.Timedelta("17:00:00")).date  # day the 17:00-roll candle belongs to
    dhigh = pd.Series(roll["high"].values, index=roll_date).groupby(level=0).max()
    dlow = pd.Series(roll["low"].values, index=roll_date).groupby(level=0).min()

    rows = []
    for _, e in ev.iterrows():
        d = e.date.date()
        g = sessions.get(d)
        if g is None or d not in prev_rth_high:
            continue
        day0 = g.index[0].normalize()
        acc_end = day0 + pd.Timedelta(e.accept_time)
        plus1 = g[(g.index >= acc_end) & (g.index < acc_end + pd.Timedelta("15min"))]
        post = g[g.index >= acc_end]
        if len(plus1) < 10 or len(post) < 30:
            continue

        # previous daily candle (17:00 roll): candle covering prev business day
        prior_days = dhigh.index[dhigh.index < d]
        pdh_daily = dhigh[prior_days[-1]] if len(prior_days) else np.nan
        pdl_daily = dlow[prior_days[-1]] if len(prior_days) else np.nan

        if e.side == "long":
            tgt_rth, tgt_daily = prev_rth_high[d], pdh_daily
            p1_ext = plus1["low"].min()
            p1_pull = e.accept_close - p1_ext
            p1_dist_level = p1_ext - e.orb_high          # <0 = re-entered range on +1
            p1_cont = plus1["close"].iloc[-1] > e.accept_close
            already = e.accept_close >= tgt_rth
            touch = post[post["high"] >= tgt_rth]
            if len(touch):
                pre = post[post.index <= touch.index[0]]
                pull_before = e.accept_close - pre["low"].min()
                dist_level_before = pre["low"].min() - e.orb_high
            eod_beyond = post["close"].iloc[-1] >= tgt_rth
            touched_daily = post["high"].max() >= tgt_daily if not np.isnan(tgt_daily) else np.nan
            already_daily = e.accept_close >= tgt_daily if not np.isnan(tgt_daily) else np.nan
        else:
            tgt_rth, tgt_daily = prev_rth_low[d], pdl_daily
            p1_ext = plus1["high"].max()
            p1_pull = p1_ext - e.accept_close
            p1_dist_level = e.orb_low - p1_ext
            p1_cont = plus1["close"].iloc[-1] < e.accept_close
            already = e.accept_close <= tgt_rth
            touch = post[post["low"] <= tgt_rth]
            if len(touch):
                pre = post[post.index <= touch.index[0]]
                pull_before = pre["high"].max() - e.accept_close
                dist_level_before = e.orb_low - pre["high"].max()
            eod_beyond = post["close"].iloc[-1] <= tgt_rth
            touched_daily = post["low"].min() <= tgt_daily if not np.isnan(tgt_daily) else np.nan
            already_daily = e.accept_close <= tgt_daily if not np.isnan(tgt_daily) else np.nan

        rows.append(dict(
            date=d, side=e.side, orb_range=e.orb_range, accept_close=e.accept_close,
            p1_pull_pts=p1_pull, p1_pull_pct_range=p1_pull / e.orb_range * 100,
            p1_dist_level_pts=p1_dist_level, p1_dist_level_pct_range=p1_dist_level / e.orb_range * 100,
            p1_reentered=p1_dist_level < 0, p1_closed_cont=p1_cont,
            already_beyond_pdh=already,
            touched_pdh=bool(len(touch)),
            mins_to_pdh=(touch.index[0] - acc_end).total_seconds() / 60 if len(touch) else np.nan,
            pull_before_pdh_pts=pull_before if len(touch) else np.nan,
            pull_before_pdh_pct_range=pull_before / e.orb_range * 100 if len(touch) else np.nan,
            dist_level_before_pdh_pts=dist_level_before if len(touch) else np.nan,
            dist_level_before_pdh_pct_range=dist_level_before / e.orb_range * 100 if len(touch) else np.nan,
            eod_close_beyond_pdh=eod_beyond,
            touched_pdh_daily=touched_daily, already_beyond_pdh_daily=already_daily,
        ))

    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(HERE, "events_plus1_pdh.csv"), index=False)

    lines = []
    w = lines.append
    w("# NAS100 ORB follow-up: the +1 candle and the road to the Previous Day High/Low\n")
    w(f"Same 2005–2020 sample; n={len(r):,} events ({(r.side=='long').sum():,} long, {(r.side=='short').sum():,} short). "
      "All distances also expressed as % of that day's ORB range (median 14.3 pts).\n")

    for side, tgt in [("long", "PDH (previous RTH session high)"), ("short", "PDL (previous RTH session low)")]:
        g = r[r.side == side]
        w(f"## {side.upper()} acceptances (n={len(g):,}) — target: {tgt}\n")

        w("### The +1 candle (first 15 minutes after the acceptance close)\n")
        t = pd.DataFrame({
            "Pullback from accept close (pts)": [np.nanpercentile(g.p1_pull_pts, p) for p in PCTS],
            "Pullback (% of ORB range)": [np.nanpercentile(g.p1_pull_pct_range, p) for p in PCTS],
            "Low distance vs broken ORB edge (pts)": [np.nanpercentile(g.p1_dist_level_pts, p) for p in PCTS],
            "Distance vs edge (% of range)": [np.nanpercentile(g.p1_dist_level_pct_range, p) for p in PCTS],
        }, index=[f"p{p}" for p in PCTS])
        w(t.to_markdown(floatfmt=".2f") + "\n")
        w("(negative 'distance vs edge' = the +1 candle traded back INSIDE the opening range)\n")
        p, lo, hi = wilson(g.p1_reentered.sum(), len(g))
        w(f"- +1 candle dips back inside the range: **{p*100:.1f}%** [CI {lo*100:.1f}–{hi*100:.1f}]")
        p, lo, hi = wilson(g.p1_closed_cont.sum(), len(g))
        w(f"- +1 candle closes in continuation (beyond the acceptance close): **{p*100:.1f}%** [CI {lo*100:.1f}–{hi*100:.1f}]\n")

        w("### Continuation to the previous day's extreme\n")
        alr = g.already_beyond_pdh
        w(f"- Already beyond the target at acceptance (gap days): {alr.mean()*100:.1f}% ({alr.sum()} events) — excluded below.")
        gg = g[~alr]
        p, lo, hi = wilson(gg.touched_pdh.sum(), len(gg))
        w(f"- Of the remaining {len(gg):,}: touch the target before 16:00: **{p*100:.1f}%** [CI {lo*100:.1f}–{hi*100:.1f}]; "
          f"median time to touch {gg.mins_to_pdh.median():.0f} min.")
        p, lo, hi = wilson(gg.eod_close_beyond_pdh.sum(), len(gg))
        w(f"- 16:00 close beyond the target: **{p*100:.1f}%** [CI {lo*100:.1f}–{hi*100:.1f}].")
        gd = g[g.already_beyond_pdh_daily == False]  # noqa: E712
        if len(gd):
            p, lo, hi = wilson(gd.touched_pdh_daily.sum(), len(gd))
            w(f"- Using the 17:00-roll daily candle instead: touch rate {p*100:.1f}% [CI {lo*100:.1f}–{hi*100:.1f}].\n")

        hit = gg[gg.touched_pdh]
        w(f"### Pullback BEFORE the target was touched (n={len(hit):,} touchers)\n")
        t = pd.DataFrame({
            "Pullback from accept close (pts)": [np.nanpercentile(hit.pull_before_pdh_pts, p) for p in PCTS],
            "Pullback (% of ORB range)": [np.nanpercentile(hit.pull_before_pdh_pct_range, p) for p in PCTS],
            "Deepest point vs ORB edge (pts)": [np.nanpercentile(hit.dist_level_before_pdh_pts, p) for p in PCTS],
            "Deepest vs edge (% of range)": [np.nanpercentile(hit.dist_level_before_pdh_pct_range, p) for p in PCTS],
        }, index=[f"p{p}" for p in PCTS])
        w(t.to_markdown(floatfmt=".2f") + "\n")
        w("(negative 'deepest vs edge' = price re-entered the range on the way to the target; "
          "positive = the pullback held above/below the broken edge)\n")
        for c, lbl in [((hit.dist_level_before_pdh_pts < 0), "re-entered the range before reaching the target"),
                       ((hit.pull_before_pdh_pct_range <= 10), "went almost straight (pullback <= 10% of range)")]:
            p, lo, hi = wilson(c.sum(), len(hit))
            w(f"- {lbl}: **{p*100:.1f}%** [CI {lo*100:.1f}–{hi*100:.1f}]")
        w("")

    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {OUT}, events: {len(r)}")


if __name__ == "__main__":
    main()
