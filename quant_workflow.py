"""
Quantitative Finance Workflow
==============================
Stage 1 - Parameter estimation from synthetic historical data
Stage 2 - Monte Carlo simulation (Geometric Brownian Motion)
Stage 3 - Mean-Variance portfolio optimisation (Max Sharpe)
Stage 4 - Out-of-sample backtest vs equal-weight benchmark

Assets: SPY, TLT, GLD, QQQ (synthetic data with realistic parameters)
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.optimize import minimize

np.random.seed(42)

# ── CONFIG ─────────────────────────────────────────────────────────
TICKERS  = ["SPY", "TLT", "GLD", "QQQ"]
N_IN     = 1008   # in-sample trading days (~4 years)
N_OUT    = 756    # out-of-sample days     (~3 years)
N_SIMS   = 2000   # Monte Carlo scenarios
RF_DAILY = 0.02 / 252

# Realistic annualised parameters
# ANN_MU (annualised drift) is the expected annual return for each asset. The values used are:
# SPY: 10%,  TLT: 3%,  GLD: 6%,  QQQ: 14%
# These come from long-run historical averages. SPY (the S&P 500) has returned roughly 10% annually over the past century. TLT (20-year Treasury bonds) has earned around 3% in real terms. GLD (gold) around 6% long-run. QQQ (Nasdaq-100) around 14% given its tech concentration. In a real workflow you'd estimate these from your historical return data — we hardcoded them here since we don't have live data access.
# ANN_SIGMA (annualised volatility) is the standard deviation of annual returns — how much each asset bounces around its mean:
# SPY: 18%,  TLT: 12%,  GLD: 16%,  QQQ: 25%
# Again these are well-established empirical figures. QQQ is the most volatile (25%) because tech stocks swing hard. TLT is the calmest (12%) because government bond prices move more predictably. In practice you'd estimate sigma from historical daily returns and multiply by √252 to annualise.
# CORR (the correlation matrix) is where it gets interesting. The values come from the observed co-movement between these four assets over history:
# SPY / TLT : -0.30  → bonds and stocks tend to move opposite directions
#              (classic "flight to safety" — when stocks crash, investors pile into bonds)

# SPY / GLD :  0.05  → gold and stocks are nearly uncorrelated
#              (gold is driven by inflation and fear, not earnings)

# SPY / QQQ :  0.88  → stocks and tech move almost in lockstep
#              (QQQ is heavily concentrated in the same companies that drive SPY)

# TLT / GLD :  0.20  → mild positive correlation
#              (both benefit when real rates fall or uncertainty rises)

# TLT / QQQ : -0.25  → bonds and tech move somewhat opposite
#              (rising rates hurt long-duration bonds and growth stocks similarly)
# Correlations are the trickiest parameter to estimate well because they're unstable — the SPY/TLT correlation was reliably negative for two decades, then turned positive in 2022 when the Fed hiked rates and both assets fell simultaneously. That breakdown is exactly the kind of thing that makes out-of-sample performance diverge from in-sample expectations, which is visible in our Stage 4 results.
# In a production system, all three of these would be estimated from data using a rolling window (to capture recent regime) or an exponentially weighted scheme (to downweight older observations), rather than hardcoded. Some shops also run separate estimates for crisis and calm regimes and blend them.
ANN_MU    = np.array([0.10,  0.03,  0.06,  0.14])
ANN_SIGMA = np.array([0.18,  0.12,  0.16,  0.25])
CORR = np.array([
    [ 1.00, -0.30,  0.05,  0.88],
    [-0.30,  1.00,  0.20, -0.25],
    [ 0.05,  0.20,  1.00,  0.02],
    [ 0.88, -0.25,  0.02,  1.00],
])

n = len(TICKERS)
daily_mu    = ANN_MU / 252
daily_sigma = ANN_SIGMA / np.sqrt(252)
L_true      = np.linalg.cholesky(CORR)

# ══════════════════════════════════════════════════════════════════
# STAGE 1 - GENERATE HISTORY & ESTIMATE PARAMETERS
# ══════════════════════════════════════════════════════════════════
print("=" * 60)
print("STAGE 1 - Generating synthetic history & estimating parameters")
print("=" * 60)

def gen_prices(T, S0, mu, sigma, L):
    Z    = np.random.standard_normal((T, n))
    Zc   = Z @ L.T
    lr   = (mu - 0.5 * sigma**2) + sigma * Zc
    price = S0 * np.exp(np.cumsum(lr, axis=0))
    return lr, price

S0 = np.array([400.0, 150.0, 175.0, 300.0])
lr_in,  px_in  = gen_prices(N_IN,  S0,         daily_mu, daily_sigma, L_true)
lr_out, px_out = gen_prices(N_OUT, px_in[-1],  daily_mu, daily_sigma, L_true)

df_in  = pd.DataFrame(lr_in,  columns=TICKERS)
df_out = pd.DataFrame(lr_out, columns=TICKERS)

mu_est    = df_in.mean()
sigma_est = df_in.std()
corr_est  = df_in.corr()
cov_est   = df_in.cov()

print(f"\nIn-sample  : {N_IN} days")
print(f"Out-of-sample: {N_OUT} days")
print("\nEstimated annualised parameters:")
print(pd.DataFrame({
    "Ann. Return (%)":     (mu_est * 252 * 100).round(2),
    "Ann. Volatility (%)": (sigma_est * np.sqrt(252) * 100).round(2),
}).to_string())
print("\nEstimated correlation matrix:")
print(corr_est.round(3).to_string())

# ══════════════════════════════════════════════════════════════════
# STAGE 2 - MONTE CARLO SIMULATION (GBM)
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STAGE 2 - Monte Carlo simulation (GBM + Cholesky correlations)")
print("=" * 60)

L_est = np.linalg.cholesky(corr_est.values)
sim_cum = np.zeros((N_SIMS, n))

for s in range(N_SIMS):
    Z    = np.random.standard_normal((N_OUT, n))
    Zc   = Z @ L_est.T
    lr   = mu_est.values + sigma_est.values * Zc
    sim_cum[s] = lr.sum(axis=0)

sim_simple = np.exp(sim_cum) - 1

print(f"\nGenerated {N_SIMS:,} scenarios over {N_OUT} trading days")
for i, t in enumerate(TICKERS):
    print(f"  {t}: mean={sim_simple[:,i].mean()*100:.1f}%  std={sim_simple[:,i].std()*100:.1f}%")

# ══════════════════════════════════════════════════════════════════
# STAGE 3 - MEAN-VARIANCE OPTIMISATION (MAX SHARPE)
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STAGE 3 - Mean-Variance optimisation (Maximum Sharpe Ratio)")
print("=" * 60)

ann_mu_e  = mu_est.values * 252
ann_cov_e = cov_est.values * 252

def pstats(w):
    w  = np.array(w)
    r  = ann_mu_e @ w
    v  = np.sqrt(w @ ann_cov_e @ w)
    sh = (r - RF_DAILY * 252) / v
    return r, v, sh

res  = minimize(lambda w: -pstats(w)[2],
                np.ones(n)/n,
                method="SLSQP",
                bounds=[(0,1)]*n,
                constraints={"type":"eq","fun":lambda w: w.sum()-1},
                options={"ftol":1e-9,"maxiter":1000})

opt_w = res.x
opt_r, opt_v, opt_sh = pstats(opt_w)
eq_r,  eq_v,  eq_sh  = pstats(np.ones(n)/n)

print("\nOptimal weights (Max Sharpe):")
for t, w in zip(TICKERS, opt_w):
    print(f"  {t}: {w*100:.1f}%")
print(f"\n  Ann. return   : {opt_r*100:.2f}%")
print(f"  Ann. vol      : {opt_v*100:.2f}%")
print(f"  Sharpe ratio  : {opt_sh:.3f}")
print(f"\nEqual-weight:")
print(f"  Ann. return   : {eq_r*100:.2f}%")
print(f"  Ann. vol      : {eq_v*100:.2f}%")
print(f"  Sharpe ratio  : {eq_sh:.3f}")

# ══════════════════════════════════════════════════════════════════
# STAGE 4 - BACKTEST
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STAGE 4 - Out-of-sample backtest")
print("=" * 60)

opt_daily = (df_out * opt_w).sum(axis=1)
eq_daily  = (df_out * (1.0/n)).sum(axis=1)
opt_cum   = 100 * np.exp(opt_daily.cumsum())
eq_cum    = 100 * np.exp(eq_daily.cumsum())

def print_stats(dl, label):
    ann_r = dl.mean() * 252
    ann_v = dl.std()  * np.sqrt(252)
    sh    = (ann_r - RF_DAILY*252) / ann_v
    cum   = np.exp(dl.cumsum())
    dd    = (1 - cum/cum.cummax()).max()
    tot   = (np.exp(dl.sum()) - 1) * 100
    print(f"\n  [{label}]")
    print(f"    Total return  : {tot:.2f}%")
    print(f"    Ann. return   : {ann_r*100:.2f}%")
    print(f"    Ann. vol      : {ann_v*100:.2f}%")
    print(f"    Sharpe ratio  : {sh:.3f}")
    print(f"    Max drawdown  : {dd*100:.2f}%")

print_stats(opt_daily, "Optimised portfolio")
print_stats(eq_daily,  "Equal-weight benchmark")

# ══════════════════════════════════════════════════════════════════
# PLOT
# ══════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(16, 14))
fig.suptitle(
    "Quantitative Finance Workflow\n"
    "Stage 1: Parameter Estimation  |  Stage 2: GBM Monte Carlo  |  "
    "Stage 3: Markowitz Optimisation  |  Stage 4: Backtest",
    fontsize=13, fontweight="bold", y=0.99
)
gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.50, wspace=0.35)

# Panel 1 - MC paths
ax1 = fig.add_subplot(gs[0, :])
S0_spy = px_in[-1, TICKERS.index("SPY")]
for s in range(min(300, N_SIMS)):
    Z    = np.random.standard_normal((N_OUT, n))
    Zc   = Z @ L_est.T
    lr   = mu_est.values + sigma_est.values * Zc
    path = S0_spy * np.exp(np.cumsum(lr[:, TICKERS.index("SPY")]))
    ax1.plot(path, color="steelblue", alpha=0.04, linewidth=0.7)
ax1.plot(px_out[:, TICKERS.index("SPY")], color="crimson",
         linewidth=2.2, label="Realised SPY path (out-of-sample)", zorder=5)
ax1.axhline(S0_spy, color="black", linestyle="--", linewidth=0.8, label="Start price")
ax1.set_title("Stage 2 - Monte Carlo: 300 GBM paths for SPY (blue) vs realised path (red)")
ax1.set_xlabel("Trading Days")
ax1.set_ylabel("Price ($)")
ax1.legend(fontsize=9)
ax1.grid(alpha=0.2)

# Panel 2 - Efficient frontier
ax2 = fig.add_subplot(gs[1, 0])
rv, vv, sv = [], [], []
for _ in range(4000):
    w = np.random.dirichlet(np.ones(n))
    r, v, s = pstats(w)
    rv.append(r); vv.append(v); sv.append(s)
sc = ax2.scatter(vv, rv, c=sv, cmap="RdYlGn", alpha=0.4, s=5)
plt.colorbar(sc, ax=ax2, label="Sharpe ratio")
ax2.scatter(opt_v, opt_r, color="blue",   s=150, zorder=6, marker="*",
            label=f"Max Sharpe ({opt_sh:.2f})")
ax2.scatter(eq_v,  eq_r,  color="orange", s=80,  zorder=6, marker="D",
            label=f"Equal weight ({eq_sh:.2f})")
ax2.set_title("Stage 3 - Efficient Frontier")
ax2.set_xlabel("Annual Volatility")
ax2.set_ylabel("Annual Return")
ax2.legend(fontsize=9)
ax2.grid(alpha=0.2)

# Panel 3 - Weights
ax3 = fig.add_subplot(gs[1, 1])
cols = ["#2196F3","#4CAF50","#FF9800","#9C27B0"]
bars = ax3.bar(TICKERS, opt_w*100, color=cols, edgecolor="white", width=0.5)
ax3.axhline(25, color="gray", linestyle="--", linewidth=1.2, label="Equal weight 25%")
for bar, w in zip(bars, opt_w):
    ax3.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.8,
             f"{w*100:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
ax3.set_title("Stage 3 - Optimal Portfolio Weights")
ax3.set_ylabel("Weight (%)")
ax3.set_ylim(0, max(opt_w)*100+12)
ax3.legend(fontsize=9)
ax3.grid(axis="y", alpha=0.2)

# Panel 4 - Cumulative performance
ax4 = fig.add_subplot(gs[2, 0])
ax4.plot(opt_cum.values, color="blue",   linewidth=2.0, label="Optimised portfolio")
ax4.plot(eq_cum.values,  color="orange", linewidth=2.0, label="Equal-weight benchmark")
ax4.axhline(100, color="black", linestyle="--", linewidth=0.8)
ax4.set_title("Stage 4 - Backtest: Cumulative Performance ($100 start)")
ax4.set_xlabel("Trading Days (out-of-sample)")
ax4.set_ylabel("Portfolio Value ($)")
ax4.legend(fontsize=9)
ax4.grid(alpha=0.2)

# Panel 5 - Drawdown
ax5 = fig.add_subplot(gs[2, 1])
opt_dd = 1 - np.exp(opt_daily.cumsum())/np.exp(opt_daily.cumsum()).cummax()
eq_dd  = 1 - np.exp(eq_daily.cumsum()) /np.exp(eq_daily.cumsum()).cummax()
ax5.fill_between(range(len(opt_dd)), -opt_dd*100,
                 color="blue",   alpha=0.45, label="Optimised portfolio")
ax5.fill_between(range(len(eq_dd)),  -eq_dd*100,
                 color="orange", alpha=0.45, label="Equal-weight benchmark")
ax5.set_title("Stage 4 - Drawdown (%)")
ax5.set_xlabel("Trading Days (out-of-sample)")
ax5.set_ylabel("Drawdown (%)")
ax5.legend(fontsize=9)
ax5.grid(alpha=0.2)

plt.savefig("/sessions/relaxed-stoic-johnson/mnt/outputs/quant_workflow.png",
            dpi=150, bbox_inches="tight")
print("\nChart saved.")
print("Done.")