# Airbnb Revenue Management — dynamic pricing as a perishable-inventory problem

Dynamic pricing for a single short-term-rental listing, treated exactly as airline
seat-inventory control: each stay-night is one unit of perishable inventory sold over
a 60-day booking window. Demand is **estimated from booking logs only** (the pricing
engine never sees the market's true parameters), prices are set by **dynamic
programming**, and the policy is validated by **Monte Carlo simulation against the
hidden ground-truth market**.

**Headline result (60 simulated years per policy):**

| Policy | Annual revenue | Occupancy | ADR | vs best fixed price |
|---|---|---|---|---|
| Hand-tuned host rules (weekend/summer) | $47,523 | 100% | $130 | −10.6% |
| Fixed $140 | $49,532 | 97% | $140 | −6.8% |
| Best single price (model-chosen) | $53,160 | 75% | $195 | — |
| **Dynamic program (RM)** | **$61,803** | **81%** | **$208** | **+16.3%** |

The historical host ran at 100% occupancy — which looks healthy and is the signature
of underpricing. The optimizer deliberately trades occupancy for rate, the core
revenue-management insight.

Open **`output/dashboard.html`** for the interactive results page.

## The model

**1. Market (ground truth, hidden from the pricing side)** — `bnbrm/market.py`
Shoppers arrive by a non-homogeneous Poisson process,
λ(date, t) = base · season(date) · weekend(date) · leadcurve(t) · event(date),
and buy iff willingness-to-pay ≥ price, WTP ~ Lognormal with a median that rises for
weekends, summer, events, and late shoppers (as in airlines).

**2. Demand estimation from logs** — `bnbrm/model.py`
- Arrivals: Poisson regression (log link) on Fourier seasonality, weekend flag, lead-time basis.
- Choice: lognormal-WTP survival model fitted by **censored maximum likelihood** — the
  log only records "at least one of n shoppers booked", never individual choices.
- Recovered σ̂ = 0.34 vs true 0.32 from 3 years of logs.

**3. Optimal pricing** — `bnbrm/optimize.py`
Single-unit perishable-inventory recursion, solved by backward induction on a price grid:

    V(t) = max_p  q(p,t)·p + (1 − q(p,t))·V(t−1),   V(0) = 0
    q(p,t) = 1 − exp(−λ̂(t)·P̂(WTP ≥ p))

The optimal price falls as the stay date nears unsold (spoilage risk) and is re-set
upward for strong dates — the behaviour airlines obtain from bid prices.

**4. Validation** — `run.py`
Each policy sells all 365 nights for 60 independent years of the *true* market.
Policies only ever query the fitted model, so the +16% lift is out-of-sample with
respect to model error (the fit visibly overestimates late high-price demand, and the
DP still wins — a robustness point, not a flaw).

## Run it

```bash
pip install numpy scipy
python3 run.py              # ~2 min: history → fit → DP → Monte Carlo → output/results.json
python3 make_dashboard.py   # → output/dashboard.html
```

## Honest limitations / extensions

- Synthetic market (no public listing-level booking data); the point is the method,
  and the generator is cleanly separated so real data can replace it.
- Single listing, nightly inventory; multi-night stays would make it a network RM
  problem (bid prices / DAVN), a natural extension.
- Competitor prices are not modelled; the demand curve absorbs them implicitly.
- Price grid capped at $320; strong dates sit at the cap far out, so a wider grid
  would raise the lift slightly.
