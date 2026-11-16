#!/usr/bin/env python3
"""
run.py - End-to-end: generate history -> fit demand -> optimize -> simulate -> results.json

Simulation: N independent years of the SAME ground-truth market, each policy
selling every night of the year. Policies only ever see the fitted model.
"""

import json
import time
import numpy as np
from bnbrm.market import Market, HORIZON
from bnbrm.model import DemandModel
from bnbrm.optimize import DPPricer, fixed_policy, best_fixed_policy, rules_policy

t0 = time.time()
mkt = Market()

print("[1/4] simulating 3 years of booking history (host without RM)...")
hist = mkt.history(n_years=3)
n_nights = 3 * 365
occ_hist = hist["booked"].sum() / n_nights
print(f"      {len(hist)} shopper-day records, historical occupancy {occ_hist:.0%}")

print("[2/4] fitting demand model from history...")
dm = DemandModel().fit(hist)
print(f"      choice-model sigma_hat={dm.sigma:.3f} (truth 0.32), converged={dm.converged}")
# quick sanity: compare fitted vs true booking prob on a few points
for doy, t, p in [(172, 14, 150), (20, 30, 100), (177, 3, 200)]:
    true_q = 1 - np.exp(-mkt.lam(doy, t) * mkt.buy_prob(p, doy, t))
    print(f"      q(doy={doy},t={t},${p}): fitted {dm.book_prob(p,doy,t):.3f} vs true {true_q:.3f}")

print("[3/4] solving DP for 365 stay dates...")
dp = DPPricer(dm).fit()

print("[4/4] Monte Carlo: 60 years per policy...")
policies = {
    "Fixed $140": fixed_policy(140.0),
    "Best fixed price": best_fixed_policy(dm),
    "Host rules (weekend/summer)": rules_policy(),
    "DP optimal (RM)": dp,
}
N_YEARS = 60
results = {}
rng = np.random.default_rng(2026)
for name, pol in policies.items():
    seeds = rng.integers(0, 2**31, size=N_YEARS)
    rev_years, occ_years, adr_years = [], [], []
    for s in seeds:
        r = np.random.default_rng(s)
        rev = 0.0; sold = 0; prices = []
        for doy in range(365):
            revenue, t_booked, price, _ = mkt.sell_night(doy, pol, rng=r)
            rev += revenue
            if t_booked is not None:
                sold += 1
                prices.append(price)
        rev_years.append(rev)
        occ_years.append(sold / 365)
        adr_years.append(np.mean(prices) if prices else 0)
    results[name] = {
        "revenue_mean": float(np.mean(rev_years)),
        "revenue_se": float(np.std(rev_years) / np.sqrt(N_YEARS)),
        "occupancy": float(np.mean(occ_years)),
        "adr": float(np.mean(adr_years)),   # average daily (sold-night) rate
    }
    print(f"      {name:30s} rev ${results[name]['revenue_mean']:>9,.0f} "
          f"± {2*results[name]['revenue_se']:,.0f}  occ {results[name]['occupancy']:.0%} "
          f"ADR ${results[name]['adr']:.0f}")

base = results["Best fixed price"]["revenue_mean"]
for name in results:
    results[name]["lift_vs_best_fixed"] = results[name]["revenue_mean"] / base - 1

# ---- artifacts for the dashboard --------------------------------------------
ev = [d for d in sorted(mkt.event_dates) if 150 < d < 260]
ev_day = ev[0] if ev else sorted(mkt.event_dates)[-1]
sample_dates = {"Off-peak weekday (doy 23)": 23, "Summer weekend (doy 173)": 173,
                f"Event day (doy {ev_day})": ev_day}
price_paths = {label: [float(dp.prices[d][t]) for t in range(HORIZON, 0, -1)]
               for label, d in sample_dates.items()}
monthly = []
for m in range(12):
    days = range(m * 30, min((m + 1) * 30, 365))
    monthly.append({
        "dp_price": float(np.mean([dp.prices[d][14] for d in days])),
        "value": float(np.mean([dp.values[d][HORIZON] for d in days])),
    })

out = {
    "results": results,
    "price_paths": price_paths,
    "horizon": HORIZON,
    "monthly": monthly,
    "history_occupancy": float(occ_hist),
    "sigma_hat": dm.sigma,
    "n_years_sim": N_YEARS,
    "runtime_s": round(time.time() - t0, 1),
}
with open("output/results.json", "w") as f:
    json.dump(out, f, indent=1)
print(f"done in {out['runtime_s']}s -> output/results.json")
