"""
optimize.py - Dynamic-programming price policy (the revenue-management core).

State: the night is still unsold with t days to go. Let V(t) be the expected
revenue-to-go under optimal pricing. With q(p,t) = P(sell today at price p):

    V(t) = max_p  q(p,t) * p + (1 - q(p,t)) * V(t-1),      V(0) = 0

Solved by backward induction over a price grid, per stay date. This is the
textbook single-unit perishable-inventory RM problem (one seat / one night).
The optimal price naturally falls as the stay date approaches with no booking
(spoilage risk) and rises when demand for that date is strong - behaviour
airlines get from bid prices.
"""

import numpy as np
from .market import HORIZON

PRICE_GRID = np.arange(60, 321, 5.0)


def dp_policy(model, doy, horizon=HORIZON, grid=PRICE_GRID):
    """Return (prices[t] for t=1..horizon, V[t])."""
    V = np.zeros(horizon + 1)
    best_p = np.zeros(horizon + 1)
    for t in range(1, horizon + 1):
        q = np.array([model.book_prob(p, doy, t) for p in grid])
        val = q * grid + (1 - q) * V[t - 1]
        i = int(np.argmax(val))
        V[t] = val[i]
        best_p[t] = grid[i]
    return best_p, V


class DPPricer:
    """Precompute policies for all 365 stay dates."""
    def __init__(self, model):
        self.model = model
        self.prices = {}
        self.values = {}

    def fit(self, dates=range(365)):
        for doy in dates:
            p, v = dp_policy(self.model, doy)
            self.prices[doy] = p
            self.values[doy] = v
        return self

    def __call__(self, doy, t):
        return self.prices[doy][min(t, HORIZON)]


# ---- baseline policies -------------------------------------------------------
def fixed_policy(price=140.0):
    return lambda doy, t: price


def best_fixed_policy(model, grid=PRICE_GRID, dates=range(0, 365, 7)):
    """The best single price (chosen with the same model - a fair baseline)."""
    def season_rev(p):
        tot = 0.0
        for doy in dates:
            no_sale = 1.0
            for t in range(HORIZON, 0, -1):
                no_sale *= 1 - model.book_prob(p, doy, t)
            tot += p * (1 - no_sale)
        return tot
    revs = [season_rev(p) for p in grid]
    return fixed_policy(float(grid[int(np.argmax(revs))]))


def rules_policy(base=120.0):
    """What a thoughtful host does by hand: weekend + summer + last-minute discount."""
    def f(doy, t):
        p = base
        if (doy % 7) in (4, 5):
            p *= 1.30
        p *= 1 + 0.15 * np.cos(2 * np.pi * (doy - 172) / 365)
        if t <= 3:
            p *= 0.85
        return p
    return f
