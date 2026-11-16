"""
market.py - Synthetic Airbnb booking market.

One listing, one stay-night at a time. For each stay date there is a booking
horizon of H days. On each day t before the stay (t = days-to-stay, H..1),
shoppers arrive with intensity lam(t, date) and each books iff their
willingness to pay (WTP) >= posted price. The night is a single unit of
perishable inventory - exactly an airline seat.

Ground truth (hidden from the pricing policies; they only see data):
  arrivals ~ Poisson(lam),  lam = base * season(date) * dow(date) * leadcurve(t) * event
  WTP ~ Lognormal(mu(date, t), sigma)   (late shoppers pay more - same as airlines)
"""

from dataclasses import dataclass, field
import numpy as np

HORIZON = 60  # booking window in days


@dataclass
class MarketParams:
    base_arrivals: float = 0.55        # shoppers/day at horizon peak, average date
    season_amp: float = 0.35           # summer vs winter swing
    dow_uplift: float = 0.65           # Fri/Sat demand uplift
    event_days: int = 10               # random high-demand event dates per year
    event_mult: float = 2.6
    wtp_median_base: float = 120.0     # $ median WTP, average date, far out
    wtp_sigma: float = 0.32
    wtp_dow: float = 0.18              # weekend WTP uplift (log-space factor applied as *(1+x))
    wtp_season: float = 0.22
    wtp_late: float = 0.25             # last-week shoppers pay up to +25%
    lead_peak: float = 14.0            # arrivals peak ~2 weeks out
    seed: int = 7


class Market:
    def __init__(self, p: MarketParams = MarketParams()):
        self.p = p
        self.rng = np.random.default_rng(p.seed)
        self.event_dates = set(self.rng.choice(365, size=p.event_days, replace=False).tolist())

    # ---- ground-truth components -------------------------------------------
    def season(self, doy: int) -> float:
        # peak late June (doy ~ 172)
        return 1.0 + self.p.season_amp * np.cos(2 * np.pi * (doy - 172) / 365)

    def dow_factor(self, doy: int) -> float:
        dow = doy % 7  # 4=Fri, 5=Sat in our synthetic calendar
        return 1.0 + (self.p.dow_uplift if dow in (4, 5) else 0.0)

    def lead_curve(self, t: int) -> float:
        # gamma-shaped: few shoppers far out, peak near lead_peak, taper at the end
        x = max(t, 0.25)
        return (x / self.p.lead_peak) * np.exp(1 - x / self.p.lead_peak)

    def lam(self, doy: int, t: int) -> float:
        ev = self.p.event_mult if doy in self.event_dates else 1.0
        return self.p.base_arrivals * self.season(doy) * self.dow_factor(doy) * self.lead_curve(t) * ev

    def wtp_median(self, doy: int, t: int) -> float:
        m = self.p.wtp_median_base
        m *= 1 + self.p.wtp_season * np.cos(2 * np.pi * (doy - 172) / 365)
        if (doy % 7) in (4, 5):
            m *= 1 + self.p.wtp_dow
        m *= 1 + self.p.wtp_late * np.exp(-t / 7.0)      # late = pay more
        if doy in self.event_dates:
            m *= 1.35
        return m

    def buy_prob(self, price: float, doy: int, t: int) -> float:
        """P(WTP >= price) for one shopper - lognormal survival."""
        from math import erf, log, sqrt
        med = self.wtp_median(doy, t)
        z = (log(price) - log(med)) / self.p.wtp_sigma
        return 0.5 * (1 - erf(z / sqrt(2)))

    # ---- one selling season for one stay-night ------------------------------
    def sell_night(self, doy: int, policy, rng=None):
        """policy(doy, t) -> price. Returns (revenue, booked_t, price_paid, shoppers)."""
        rng = rng or self.rng
        shoppers = 0
        for t in range(HORIZON, 0, -1):
            n = rng.poisson(self.lam(doy, t))
            if n == 0:
                continue
            price = float(policy(doy, t))
            shoppers += n
            # any of the n shoppers books?
            pb = self.buy_prob(price, doy, t)
            if rng.random() < 1 - (1 - pb) ** n:
                return price, t, price, shoppers
        return 0.0, None, None, shoppers

    # ---- historical dataset for model fitting --------------------------------
    def history(self, n_years: int = 3, hist_policy=None, seed: int = 123):
        """Simulate n_years of operation under a noisy fixed-ish pricing policy
        (what a host without RM would have charged) and log shopper-level data:
        (doy, t, price, n_arrivals, booked)."""
        rng = np.random.default_rng(seed)
        if hist_policy is None:
            def hist_policy(doy, t, r=rng):
                base = 110 + 40 * ((doy % 7) in (4, 5)) + r.normal(0, 18)
                return float(np.clip(base, 60, 260))
        rows = []
        for year in range(n_years):
            for doy in range(365):
                for t in range(HORIZON, 0, -1):
                    n = rng.poisson(self.lam(doy, t))
                    if n == 0:
                        continue
                    price = hist_policy(doy, t)
                    pb = self.buy_prob(price, doy, t)
                    booked = int(rng.random() < 1 - (1 - pb) ** n)
                    rows.append((year, doy, t, price, n, booked))
                    if booked:
                        break
        import numpy.lib.recfunctions  # noqa
        arr = np.array(rows, dtype=[("year", "i4"), ("doy", "i4"), ("t", "i4"),
                                    ("price", "f8"), ("arrivals", "i4"), ("booked", "i4")])
        return arr
