# NAS100 30-min NY ORB — Combined Playbook (2005–2020, 3,683 events)

All statistics from the full study (see REPORT.md, REPORT_PLUS1_PDH.md).
Long side shown; shorts are mirrored (slightly deeper pullbacks, slightly worse odds).
Median ORB range: 14.3 pts (~0.5% of price). "Edge" = the broken ORB boundary.

## Pullback expectation measured FROM the broken edge (longs)

Positive = distance back INTO the range; negative = floor held above the edge.

| Percentile | Depth vs edge | In % of ORB range |
|---|---|---|
| p10 | held +1.7 pts above | −11.5% |
| p25 | 1.1 pts inside | 8.8% |
| **p50** | **7.2 pts inside** | **50% (range mid)** |
| p75 | 18.5 pts inside | 122% (through the whole range) |
| p90 | 38 pts inside | 212% |

Mean depth: 15.2 pts (81% of range) — dragged up by fat tail; the MEDIAN
expectation from the edge is a pullback to the middle of the range.

## Direction (unconditional, at the moment of acceptance)

- Day closes in the breakout direction (vs 09:30 open): **75%**
- Day closes beyond the edge: **60%** | inside the range: 25% | beyond the opposite edge: **15%**

## The decision tree (the real learnings)

1. **Acceptance prints** (first 15m close outside). Base case: 82% will retest
   the edge, median first retest ~6 min. Only 49% of +1 candles continue.
2. **Momentum branch (~31%)**: no 15m candle ever closes back inside.
   Median floor: **0.5 pts ABOVE the edge** (holds the level). Day closes in
   breakout direction **98.5%** of the time. This is the "never look back" day.
   Realtime tell: new HH within 15 min (76% of continuations do it in ≤15 min,
   median 3 min).
3. **Fail branch (~69%)**: some 15m candle closes back inside. Median depth
   from the edge: **12.5 pts / ~85% of the range**. But direction is NOT dead:
   - 67% → next break is the SAME side again (re-acceptance 71%)
   - 23% → next break is the opposite side
   - Day still closes against the original breakout only ~35%.
4. **Double distribution** (opposite acceptance after the fail, ~35% of fails):
   NOW direction flips — day closes against the original breakout **77%**,
   below the opposite edge **61%**, back beyond the original edge only **11%**.
5. **Clear directional day filter** (±1% open→close, hindsight): pullback from
   the edge halves (median MAE 30% of range, mid touched only 15%), retest
   probability drops to 56%, and 45% hold beyond the edge all day with a floor
   at ~+16% of range beyond the edge.

## One-paragraph synthesis

From the ORB high, the average expectation is a pullback to ~50% of the range
(median; mean deeper at ~80% due to tail). The single most informative realtime
signal is whether any 15m candle closes back inside: if none does (1 in 3
days), the floor is the edge itself and direction is near-certain (98%+); once
one does (2 in 3 days), expect the middle of the range and treat direction as
2:1 in favor of the original side UNTIL an opposite-side acceptance prints —
that second close flips the day to 3:1 against the original breakout with a
61% chance of a trend close beyond the far edge.
