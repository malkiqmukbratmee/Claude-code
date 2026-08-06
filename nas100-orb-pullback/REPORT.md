# NAS100 (US Tech 100 CFD) — 30-min NY Opening Range Breakout: Pullback Statistics

- Instrument: OANDA NAS100_USD CFD, 1-minute OHLCV (UTC source, converted to America/New_York with DST)
- Sample: **3,683 acceptance events** (1,981 long, 1,702 short), 2005-01-04 to 2020-05-13 (~15.4 years)
- ORB = high/low of 09:30–10:00 ET. Acceptance = first 15-min candle (from 10:00 onward) closing outside the range.
- Pullback = maximum adverse excursion (1-min data) from the acceptance-candle close until 16:00 ET.

Median ORB range: 14.3 pts (0.49% of price). Median breakout leg at acceptance: 2.7 pts.

## 1. Overall pullback distribution

### ALL (n=3,683)

|     |   Pullback (pts) |   Pullback (% of price) |   Pullback (% of ORB range) |   Retrace (% of breakout leg) |
|:----|-----------------:|------------------------:|----------------------------:|------------------------------:|
| p10 |             1.70 |                    0.06 |                       11.81 |                         51.34 |
| p25 |             4.50 |                    0.16 |                       31.54 |                        152.04 |
| p50 |            11.00 |                    0.37 |                       75.38 |                        400.00 |
| p75 |            22.85 |                    0.75 |                      148.53 |                       1017.08 |
| p90 |            42.40 |                    1.32 |                      232.90 |                       2619.08 |

Read: p75 = 75% of events pulled back **no more than** this; p25 = 25% pulled back no more than this (equivalently 75% pulled back MORE).

|    | Outcome                             | Probability   | 95% Wilson CI   |
|---:|:------------------------------------|:--------------|:----------------|
|  0 | Retest of breakout level (ORB edge) | 82.5%         | [81.2%, 83.7%]  |
|  1 | Re-entry back inside the range      | 81.6%         | [80.3%, 82.8%]  |
|  2 | Touch of range midpoint             | 52.5%         | [50.9%, 54.1%]  |
|  3 | Full traverse to opposite side      | 31.1%         | [29.7%, 32.7%]  |
|  4 | 16:00 close back through the level  | 42.9%         | [41.3%, 44.5%]  |

Median pullback as % of ORB range: **75.4%** (bootstrap 95% CI [72.2%, 79.3%]). Median time to deepest pullback: 122 min; median time to level retest (when it happens): 6 min.

### LONG breakouts (close above range) (n=1,981)

|     |   Pullback (pts) |   Pullback (% of price) |   Pullback (% of ORB range) |   Retrace (% of breakout leg) |
|:----|-----------------:|------------------------:|----------------------------:|------------------------------:|
| p10 |             1.50 |                    0.05 |                        9.45 |                         47.93 |
| p25 |             4.00 |                    0.13 |                       27.34 |                        148.57 |
| p50 |            10.00 |                    0.34 |                       70.00 |                        409.84 |
| p75 |            22.50 |                    0.74 |                      144.96 |                       1127.42 |
| p90 |            43.20 |                    1.31 |                      235.14 |                       3030.00 |

Read: p75 = 75% of events pulled back **no more than** this; p25 = 25% pulled back no more than this (equivalently 75% pulled back MORE).

|    | Outcome                             | Probability   | 95% Wilson CI   |
|---:|:------------------------------------|:--------------|:----------------|
|  0 | Retest of breakout level (ORB edge) | 81.7%         | [80.0%, 83.4%]  |
|  1 | Re-entry back inside the range      | 80.7%         | [78.9%, 82.4%]  |
|  2 | Touch of range midpoint             | 50.4%         | [48.2%, 52.6%]  |
|  3 | Full traverse to opposite side      | 30.5%         | [28.5%, 32.6%]  |
|  4 | 16:00 close back through the level  | 40.0%         | [37.8%, 42.2%]  |

Median pullback as % of ORB range: **70.0%** (bootstrap 95% CI [65.3%, 74.6%]). Median time to deepest pullback: 105 min; median time to level retest (when it happens): 6 min.

### SHORT breakouts (close below range) (n=1,702)

|     |   Pullback (pts) |   Pullback (% of price) |   Pullback (% of ORB range) |   Retrace (% of breakout leg) |
|:----|-----------------:|------------------------:|----------------------------:|------------------------------:|
| p10 |             2.00 |                    0.08 |                       15.15 |                         56.59 |
| p25 |             5.50 |                    0.19 |                       38.15 |                        154.08 |
| p50 |            11.95 |                    0.42 |                       81.91 |                        395.94 |
| p75 |            23.07 |                    0.77 |                      150.76 |                        898.33 |
| p90 |            41.20 |                    1.34 |                      229.35 |                       2340.39 |

Read: p75 = 75% of events pulled back **no more than** this; p25 = 25% pulled back no more than this (equivalently 75% pulled back MORE).

|    | Outcome                             | Probability   | 95% Wilson CI   |
|---:|:------------------------------------|:--------------|:----------------|
|  0 | Retest of breakout level (ORB edge) | 83.4%         | [81.5%, 85.1%]  |
|  1 | Re-entry back inside the range      | 82.5%         | [80.7%, 84.3%]  |
|  2 | Touch of range midpoint             | 54.9%         | [52.6%, 57.3%]  |
|  3 | Full traverse to opposite side      | 31.9%         | [29.7%, 34.2%]  |
|  4 | 16:00 close back through the level  | 46.4%         | [44.0%, 48.7%]  |

Median pullback as % of ORB range: **81.9%** (bootstrap 95% CI [77.6%, 86.7%]). Median time to deepest pullback: 138 min; median time to level retest (when it happens): 7 min.

### Strong acceptances only (leg >= 25% of ORB range)

The unconditional 'retrace % of leg' is inflated by events whose close barely cleared the range (median leg is only ~2.7 pts), so any pullback is a huge multiple of the leg. Filtering to decisive closes gives a more tradeable read:

n=1,400 (38% of events)

|     |   Pullback (pts) |   Pullback (% of price) |   Pullback (% of ORB range) |   Retrace (% of breakout leg) |
|:----|-----------------:|------------------------:|----------------------------:|------------------------------:|
| p10 |             1.79 |                    0.06 |                       16.07 |                         30.29 |
| p25 |             4.50 |                    0.18 |                       38.78 |                         81.22 |
| p50 |            10.80 |                    0.41 |                       90.00 |                        200.00 |
| p75 |            22.73 |                    0.82 |                      171.43 |                        382.53 |
| p90 |            41.20 |                    1.33 |                      263.81 |                        615.41 |

|    | Outcome                             | Probability   | 95% Wilson CI   |
|---:|:------------------------------------|:--------------|:----------------|
|  0 | Retest of breakout level (ORB edge) | 70.4%         | [67.9%, 72.7%]  |
|  1 | Re-entry back inside the range      | 69.6%         | [67.1%, 71.9%]  |
|  2 | Touch of range midpoint             | 48.1%         | [45.5%, 50.7%]  |
|  3 | Full traverse to opposite side      | 30.9%         | [28.6%, 33.4%]  |
|  4 | 16:00 close back through the level  | 35.9%         | [33.4%, 38.4%]  |

## 2. Conditioned on the pre-open move (prev 16:00 close -> 09:30 open)

The user case: e.g. index already +1% before the NY open — what changes?

| Pre-open move    |    n |   Median pullback (% ORB range) |   Median retrace (% leg) | P(retest level) [95% CI]   | P(touch mid)   | % long breakouts   |
|:-----------------|-----:|--------------------------------:|-------------------------:|:---------------------------|:---------------|:-------------------|
| < -1%            |  196 |                           76.95 |                   437.95 | 85% [79–89]                | 52%            | 55%                |
| -1% to -0.25%    |  741 |                           75.22 |                   409.09 | 83% [80–85]                | 52%            | 53%                |
| -0.25% to +0.25% | 1503 |                           82.47 |                   437.50 | 85% [83–87]                | 57%            | 55%                |
| +0.25% to +1%    | 1034 |                           67.10 |                   344.87 | 79% [76–81]                | 47%            | 52%                |
| > +1%            |  209 |                           71.43 |                   396.08 | 78% [72–84]                | 51%            | 55%                |

Kruskal–Wallis across gap buckets on pullback (% ORB range): H=13.2, p=0.011. Spearman |pre-open move| vs pullback: rho=-0.037, p=0.025.

### Breakout direction relative to the overnight move

| Breakout vs pre-open move   |    n |   Median pullback (% ORB range) |   Median retrace (% leg) | P(retest level) [95% CI]   | P(close back inside)   |
|:----------------------------|-----:|--------------------------------:|-------------------------:|:---------------------------|:-----------------------|
| with-gap                    | 1084 |                           63.49 |                   369.53 | 78% [75–80]                | 38%                    |
| against-gap                 | 1096 |                           78.80 |                   382.40 | 84% [81–86]                | 43%                    |
| flat                        | 1503 |                           82.47 |                   437.50 | 85% [83–87]                | 46%                    |

Mann–Whitney with-gap vs against-gap pullback depth: U=550755, p=0.0032.

## 3. Conditioned on volume traded up to the breakout (RVOL)

RVOL = cumulative RTH volume at acceptance close / 20-session average at the same clock time.

| Volume regime   |    n |   Median RVOL |   Median pullback (% ORB range) |   Median retrace (% leg) | P(retest level) [95% CI]   | P(opposite side)   |
|:----------------|-----:|--------------:|--------------------------------:|-------------------------:|:---------------------------|:-------------------|
| low RVOL        | 1228 |          0.70 |                           73.15 |                   433.08 | 82% [80–84]                | 29%                |
| mid RVOL        | 1227 |          1.01 |                           77.29 |                   383.33 | 83% [81–85]                | 33%                |
| high RVOL       | 1228 |          1.37 |                           76.59 |                   395.07 | 83% [80–85]                | 31%                |

Kruskal–Wallis across RVOL terciles: H=7.1, p=0.028. Spearman RVOL vs pullback: rho=0.019, p=0.26.

## 4. By breakout timing (which 15m candle accepted)

| Acceptance candle    |    n |   Median pullback (% ORB range) |   Median retrace (% leg) | P(retest level) [95% CI]   |
|:---------------------|-----:|--------------------------------:|-------------------------:|:---------------------------|
| candle 1 (10:15:00)  | 1311 |                           83.70 |                   378.72 | 81% [78–83]                |
| candle 2 (10:30:00)  |  670 |                           87.10 |                   424.81 | 84% [81–86]                |
| candle 3 (10:45:00)  |  461 |                           91.67 |                   453.49 | 84% [80–87]                |
| candle 4 (11:00:00)  |  261 |                           81.63 |                   458.14 | 86% [81–90]                |
| candle 5 (11:15:00)  |  211 |                           73.39 |                   400.00 | 87% [82–91]                |
| candle 6 (11:30:00)  |  147 |                           64.00 |                   471.88 | 81% [74–86]                |
| candle 7+ (>= 11:45) |  622 |                           49.37 |                   390.91 | 82% [78–84]                |

## 5. Stability across years (robustness)

|   year |   n |   med_pullback_pct_range | retest_rate   |
|-------:|----:|-------------------------:|:--------------|
|   2005 | 228 |                    100.0 | 85%           |
|   2006 | 238 |                     84.7 | 82%           |
|   2007 | 243 |                     84.8 | 86%           |
|   2008 | 247 |                     85.1 | 82%           |
|   2009 | 238 |                     66.0 | 82%           |
|   2010 | 239 |                     70.7 | 80%           |
|   2011 | 246 |                     72.7 | 82%           |
|   2012 | 238 |                     75.5 | 82%           |
|   2013 | 241 |                     69.3 | 82%           |
|   2014 | 239 |                     71.4 | 84%           |
|   2015 | 238 |                     67.4 | 82%           |
|   2016 | 242 |                     73.6 | 83%           |
|   2017 | 240 |                     68.4 | 81%           |
|   2018 | 240 |                     79.2 | 84%           |
|   2019 | 237 |                     65.3 | 84%           |
|   2020 |  89 |                     76.9 | 83%           |

## 6. Methodology notes & limitations

- Feed: OANDA NAS100 CFD 1-min bars (bid/mid as published by provider); volume is CFD tick volume, a liquidity proxy, not exchange-traded contracts.
- Coverage ends 2020-05-13 (last data in the public archive). 15.4 years, every session with a valid ORB and an outside 15-min close is included — no cherry-picking.
- 'Pullback' is max adverse excursion from the acceptance close to 16:00 ET. It is measured against the acceptance-candle CLOSE (entry-at-close assumption), on 1-minute lows/highs.
- Percentile framing: pXX = XX% of events pulled back no more than that value.
- All probabilities carry 95% Wilson CIs; medians carry bootstrap CIs; bucket differences tested with Kruskal-Wallis / Mann-Whitney (non-parametric, no normality assumption).