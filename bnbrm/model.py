"""
model.py - Demand estimation from booking logs (no access to ground truth).

Two pieces, mirroring airline RM practice:
  1. Arrival model:  lam_hat(doy, t)   - Poisson regression on Fourier(season),
     weekend flag, and a gamma-shaped lead-time basis.
  2. Choice model:   P(book | price, doy, t) for ONE shopper - we observe only
     "at least one of n booked", so we fit by maximum likelihood on that
     censored outcome, with a lognormal-WTP survival parameterization:
         p1(price) = 1 - Phi((ln price - mu(doy,t)) / sigma)
         mu(doy,t) = b0 + b_sin*sin + b_cos*cos + b_we*weekend + b_late*exp(-t/7)
"""

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm


def _feat_arrivals(doy, t):
    doy = np.asarray(doy, float); t = np.asarray(t, float)
    return np.column_stack([
        np.ones_like(doy),
        np.sin(2 * np.pi * doy / 365), np.cos(2 * np.pi * doy / 365),
        ((doy % 7 == 4) | (doy % 7 == 5)).astype(float),
        np.log(np.maximum(t, 0.25)),
        t,
    ])


def _feat_mu(doy, t):
    doy = np.asarray(doy, float); t = np.asarray(t, float)
    return np.column_stack([
        np.ones_like(doy),
        np.sin(2 * np.pi * doy / 365), np.cos(2 * np.pi * doy / 365),
        ((doy % 7 == 4) | (doy % 7 == 5)).astype(float),
        np.exp(-t / 7.0),
    ])


class DemandModel:
    def fit(self, hist):
        # ---- 1. arrivals: Poisson GLM by Newton steps (log link) -------------
        X = _feat_arrivals(hist["doy"], hist["t"])
        y = hist["arrivals"].astype(float)
        beta = np.zeros(X.shape[1]); beta[0] = np.log(max(y.mean(), 1e-3))
        for _ in range(60):
            eta = np.clip(X @ beta, -10, 5)
            mu = np.exp(eta)
            g = X.T @ (y - mu)
            H = (X * mu[:, None]).T @ X + 1e-6 * np.eye(X.shape[1])
            step = np.linalg.solve(H, g)
            beta += step
            if np.max(np.abs(step)) < 1e-8:
                break
        self.beta_arr = beta

        # ---- 2. censored choice model ---------------------------------------
        Xm = _feat_mu(hist["doy"], hist["t"])
        price = hist["price"]; n = hist["arrivals"]; booked = hist["booked"]

        def nll(theta):
            w, log_sigma = theta[:-1], theta[-1]
            sigma = np.exp(log_sigma)
            mu = Xm @ w
            p1 = norm.sf((np.log(price) - mu) / sigma)
            p1 = np.clip(p1, 1e-9, 1 - 1e-9)
            p_any = 1 - (1 - p1) ** n
            p_any = np.clip(p_any, 1e-12, 1 - 1e-12)
            return -np.sum(booked * np.log(p_any) + (1 - booked) * np.log(1 - p_any))

        theta0 = np.r_[np.log(120), np.zeros(Xm.shape[1] - 1), np.log(0.3)]
        res = minimize(nll, theta0, method="Nelder-Mead",
                       options={"maxiter": 20000, "xatol": 1e-6, "fatol": 1e-6})
        self.theta = res.x
        self.sigma = float(np.exp(res.x[-1]))
        self.converged = bool(res.success)
        return self

    def lam_hat(self, doy, t):
        return float(np.exp(np.clip(_feat_arrivals([doy], [t]) @ self.beta_arr, -10, 5))[0])

    def mu_hat(self, doy, t):
        return float((_feat_mu([doy], [t]) @ self.theta[:-1])[0])

    def p1(self, price, doy, t):
        """P(one shopper books at this price)."""
        return float(norm.sf((np.log(price) - self.mu_hat(doy, t)) / self.sigma))

    def book_prob(self, price, doy, t):
        """P(the night sells on day t at this price) = 1 - exp(-lam * p1)
        (Poisson thinning of arrivals by purchase probability)."""
        return 1 - np.exp(-self.lam_hat(doy, t) * self.p1(price, doy, t))
