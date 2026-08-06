# NAS100 30-min NY ORB — Final Playbook (2005–2020, 3,683 events)

ORB = 09:30–10:00 ET (16:30–17:00 Bulgarian). Acceptance = first 15m candle
closing outside the range (earliest close 10:15 ET / 17:15 BG). All windows end
at the 16:00 ET (23:00 BG) session close — strictly intraday. Median range:
14.3 pts (~0.5% of price). Longs shown; shorts mirrored, ~2–5pp worse.
Full statistics with CIs: REPORT.md, REPORT_PLUS1_PDH.md.

## 1. Direction at the moment of acceptance
- Day closes with the breakout: 75% | beyond the edge: 60% | inside: 25% | reversal beyond opposite edge: 15%.
- On ±1% directional days the acceptance pointed the right way 86% of the time.

## 2. The pullback map (measured from the broken edge)
- Retest of the edge: 82.5% of all sessions, median 6 min after the acceptance close.
- Median deepest pullback of a session: 50% of the range (the mid).
- Winners only (close beyond edge, n=2,090) — limit-fill probabilities:
  +50% of range above edge 96% | +35% 93% | **+25% 90%** | +10% 81% | edge itself 69%.
- Where the floor lands when it holds above: modal zone **0–10% of range above the edge**
  (34% of holders); probability decays monotonically higher up — no secondary level at 25%.
- Median floor before a new HH (holders): +15–16% of range above the edge — the same number
  in four independent cuts (+1 candle, pre-PDH, pre-HH, whole-day).

## 3. The decision tree
1. Momentum branch (31%): no 15m close ever back inside → floor holds the edge,
   day closes with the breakout 98.5%. Tell: new HH within 15 min.
2. Fail branch (69%): a 15m candle closes back inside → median depth 85% of range.
   Still 2:1 for the original side: next break is same-side 67%, day closes against only 35%.
3. Double distribution (35% of fails): opposite-side acceptance prints → flips to
   77% close against the original, 61% beyond the opposite edge, 11% recovery.
4. Directional-day filter (±1%): pullbacks halve (median 30% of range), mid touched
   only 15%, 45% hold beyond the edge all day.

## 4. Touches of the edge line
- Winner sessions: 0 touches 31%, 1 touch 22%, 2+ 48%. Mean 1.85. After a first touch,
  another follows 69% of the time (median 2 total) — a missed retest usually re-offers.
- Touch count does NOT weaken the level: P(close beyond edge) is flat 47–49% from the
  1st to the 7th touch. Reversal probability actually falls with more touches.
- Only early crowding is a caution: 3+ separate touches before 11:00 ET (18:00 BG)
  flips odds toward reversal (~35–50%), but only ~1.7% of sessions get there (small n).

## 5. What does NOT work
- Volume (RVOL to the breakout): no predictive power for pullback depth (rho=0.02, p=0.26).
- Touch counting as a fade signal (flat, see above).
- Waiting for the edge itself as the only entry: misses 1 in 3 winners.

## 6. One paragraph
The broken ORB edge is a magnet, not a wall: 4 of 5 breakouts come back toward it within
minutes, the pullback floor clusters in the first 10% of the range above it, and nine of
ten winning sessions dip to edge+25% — but the level survives any number of touches at a
flat coin-flip rate, and the only statistically decisive reversal signal is a 15-minute
close back inside followed by acceptance of the opposite side (77% reversal close). Trade
the zone edge→edge+25%, respect the second acceptance, ignore the touch count and volume.
