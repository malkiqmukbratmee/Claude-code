"""Extract ORB-acceptance events and pullback measurements per NY session.

Definitions
-----------
- Session: regular NY hours 09:30-16:00 ET.
- ORB (opening range): high/low of 09:30:00-09:59:59 ET (the first 30 minutes),
  built from 1-minute bars. Requires >= 25 of the 30 minutes present.
- Acceptance: the first 15-minute candle (aligned :00/:15/:30/:45, starting with
  the 10:00-10:15 candle) whose CLOSE is above the ORB high (long) or below the
  ORB low (short). Searched until the 15:30-15:45 candle inclusive.
- Pullback: measured on 1-minute data from the acceptance-candle close until
  16:00 ET, against the direction of the breakout.

Per event we record (long side shown; short side is mirrored):
- mae_pts:        acceptance_close - min(low)   (max adverse excursion, >= 0)
- mae_pct_price:  mae_pts / acceptance_close * 100
- mae_pct_range:  mae_pts / orb_range * 100
- leg_pts:        acceptance_close - orb_high   (breakout leg beyond the level)
- retrace_pct_leg: mae_pts / leg_pts * 100      (how much of the leg was given back)
- depth_below_level_pts: orb_high - min(low)    (>0 means price re-entered the range)
- retest_level:   min(low) <= orb_high          (came back to the breakout level)
- reenter_range:  min(low) <  orb_high          (traded back inside the range)
- touch_mid:      min(low) <= orb_mid
- touch_opposite: min(low) <= orb_low           (full traversal)
- close_back_inside: 16:00 close back inside/beyond the level
- minutes_to_max_pullback, minutes_to_retest
Conditioning variables:
- preopen_move_pct: prior-session 16:00 close -> today 09:30 open, in %
- rvol_at_accept:   cumulative RTH volume up to acceptance close divided by the
                    20-session rolling mean of cumulative volume at that same
                    clock time (volume-based regime normalisation)
- orb_range_pct:    ORB range as % of 09:30 open
- accept_candle_idx: which 15m candle broke (1 = 10:00-10:15)
"""
import os

import numpy as np
import pandas as pd

from prepare_data import load

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.csv")

MIN_ORB_BARS = 25
MIN_RTH_BARS = 300          # skip half days / broken sessions (full day = 390)
CANDLE_STARTS = pd.timedelta_range("10:00:00", "15:45:00", freq="15min")


def extract() -> pd.DataFrame:
    df = load()
    rth = df.between_time("09:30", "15:59")
    rth = rth[rth.index.dayofweek < 5]
    sessions = {d: g for d, g in rth.groupby(rth.index.date)}
    dates = sorted(sessions)

    # previous-session 16:00 close per date
    prev_close = {}
    last = None
    for d in dates:
        prev_close[d] = last
        last = sessions[d]["close"].iloc[-1]

    # cumulative volume at each 15m checkpoint per date, for RVOL normalisation
    ckpt_vol = {}   # date -> {checkpoint_end_minute_offset: cum volume}
    for d in dates:
        g = sessions[d]
        mins = (g.index - g.index.normalize()) - pd.Timedelta("09:30:00")
        cs = g["volume"].cumsum()
        ckpt_vol[d] = {
            int(td.total_seconds() // 60): float(cs[mins <= td].iloc[-1]) if (mins <= td).any() else np.nan
            for td in [pd.Timedelta("00:30:00")] + [c - pd.Timedelta("09:30:00") + pd.Timedelta("00:15:00") for c in CANDLE_STARTS]
        }

    rows = []
    for i, d in enumerate(dates):
        g = sessions[d]
        if len(g) < MIN_RTH_BARS or prev_close[d] is None:
            continue
        day0 = g.index[0].normalize()
        orb = g[(g.index >= day0 + pd.Timedelta("09:30:00")) & (g.index < day0 + pd.Timedelta("10:00:00"))]
        if len(orb) < MIN_ORB_BARS:
            continue
        orb_high, orb_low = orb["high"].max(), orb["low"].min()
        orb_mid = (orb_high + orb_low) / 2
        orb_range = orb_high - orb_low
        if orb_range <= 0:
            continue
        open_930 = orb["open"].iloc[0]
        preopen_move_pct = (open_930 / prev_close[d] - 1) * 100

        event = None
        for k, start in enumerate(CANDLE_STARTS, start=1):
            c = g[(g.index >= day0 + start) & (g.index < day0 + start + pd.Timedelta("15min"))]
            if len(c) < 10:
                continue
            close = c["close"].iloc[-1]
            if close > orb_high:
                event = ("long", k, start, c, close)
                break
            if close < orb_low:
                event = ("short", k, start, c, close)
                break
        if event is None:
            continue
        side, k, start, candle, acc_close = event
        acc_end = day0 + start + pd.Timedelta("15min")
        post = g[g.index >= acc_end]
        if len(post) < 30:
            continue

        if side == "long":
            level, extreme = orb_high, post["low"].min()
            mae = max(acc_close - extreme, 0.0)
            leg = acc_close - level
            depth_beyond = level - extreme
            retest = post["low"].min() <= level
            reenter = post["low"].min() < level
            mid = post["low"].min() <= orb_mid
            opp = post["low"].min() <= orb_low
            close_back = post["close"].iloc[-1] < level
            t_ext = post["low"].idxmin()
            hit = post[post["low"] <= level]
        else:
            level, extreme = orb_low, post["high"].max()
            mae = max(extreme - acc_close, 0.0)
            leg = level - acc_close
            depth_beyond = extreme - level
            retest = post["high"].max() >= level
            reenter = post["high"].max() > level
            mid = post["high"].max() >= orb_mid
            opp = post["high"].max() >= orb_high
            close_back = post["close"].iloc[-1] > level
            t_ext = post["high"].idxmax()
            hit = post[post["high"] >= level]

        # volume up to acceptance close, normalised by 20-session average at same clock time
        off = int((start - pd.Timedelta("09:30:00") + pd.Timedelta("00:15:00")).total_seconds() // 60)
        v_now = ckpt_vol[d].get(off, np.nan)
        hist = [ckpt_vol[dates[j]].get(off, np.nan) for j in range(max(0, i - 20), i)]
        hist = [h for h in hist if not np.isnan(h)]
        rvol = v_now / np.mean(hist) if hist and not np.isnan(v_now) else np.nan

        rows.append(dict(
            date=d, side=side, accept_candle_idx=k,
            accept_time=str((day0 + start + pd.Timedelta("15min")).time()),
            orb_high=orb_high, orb_low=orb_low, orb_range=orb_range,
            orb_range_pct=orb_range / open_930 * 100,
            open_930=open_930, prev_close=prev_close[d],
            preopen_move_pct=preopen_move_pct,
            accept_close=acc_close, leg_pts=leg,
            mae_pts=mae, mae_pct_price=mae / acc_close * 100,
            mae_pct_range=mae / orb_range * 100,
            retrace_pct_leg=(mae / leg * 100) if leg > 0 else np.nan,
            depth_beyond_level_pts=depth_beyond,
            retest_level=retest, reenter_range=reenter,
            touch_mid=mid, touch_opposite=opp, close_back_inside=close_back,
            minutes_to_max_pullback=(t_ext - acc_end).total_seconds() / 60,
            minutes_to_retest=(hit.index[0] - acc_end).total_seconds() / 60 if len(hit) else np.nan,
            rvol_at_accept=rvol,
            eod_close=post["close"].iloc[-1],
        ))

    ev = pd.DataFrame(rows)
    ev.to_csv(OUT, index=False)
    return ev


if __name__ == "__main__":
    ev = extract()
    print(f"events: {len(ev):,}  (long {sum(ev.side=='long')}, short {sum(ev.side=='short')})")
    print(f"dates: {ev.date.min()} -> {ev.date.max()}")
