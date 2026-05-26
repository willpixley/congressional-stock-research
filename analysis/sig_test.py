import json
import numpy as np
from scipy import stats


OUTLIER_THRESHOLD = 1.0


def is_outlier(result):
    return result is not None and abs(result["alpha_annualized"]) > OUTLIER_THRESHOLD


def test_ff5_vs_zero(ff5_results):
    """Test whether average FF5 alpha is significantly different from zero."""
    clean = [f for f in ff5_results if f is not None and not is_outlier(f)]
    if len(clean) < 2:
        print("FF5 vs zero: Not enough data")
        return

    daily_alphas = np.array([f["alpha_daily"] for f in clean])
    weights = np.array([1 / f["alpha_se"] ** 2 for f in clean])
    weights /= weights.sum()

    weighted_mean = np.sum(weights * daily_alphas)
    weighted_se = np.sqrt(
        np.sum(weights**2 * np.array([f["alpha_se"] ** 2 for f in clean]))
    )
    z_stat = weighted_mean / weighted_se

    p_two_tailed = 2 * stats.norm.sf(abs(z_stat))
    p_one_tailed = stats.norm.sf(z_stat)  # is alpha > 0?

    annualized = np.mean([f["alpha_annualized"] for f in clean])

    print(f"\n=== FF5 Alpha vs Zero (n={len(clean)}) ===")
    print(f"  Mean annualized alpha: {annualized:.2%}")
    print(f"  Weighted mean daily alpha: {weighted_mean:.6f}")
    print(f"  z-stat: {z_stat:.4f}")
    print(f"  p-value (two-tailed): {p_two_tailed:.4f}")
    print(f"  p-value (one-tailed, alpha > 0): {p_one_tailed:.4f}")
    print(
        f"  {'Significantly above 0 (p < 0.05)' if p_one_tailed < 0.05 else 'Not significant'}"
    )


def weighted_test(ff5_results, aug_results, test_name):
    pairs = [
        (f, a)
        for f, a in zip(ff5_results, aug_results)
        if f is not None and a is not None and not is_outlier(f) and not is_outlier(a)
    ]
    if len(pairs) < 2:
        print(f"{test_name}: Not enough data ({len(pairs)} pairs)")
        return

    diffs = np.array([a["alpha_daily"] - f["alpha_daily"] for f, a in pairs])

    weights = np.array([1 / a["alpha_se"] ** 2 for _, a in pairs])
    weights /= weights.sum()

    weighted_mean = np.sum(weights * diffs)
    weighted_se = np.sqrt(
        np.sum(weights**2 * np.array([a["alpha_se"] ** 2 for _, a in pairs]))
    )
    z_stat = weighted_mean / weighted_se
    p_value = stats.norm.cdf(z_stat)

    ff5_annualized = np.mean([f["alpha_annualized"] for f, _ in pairs])
    aug_annualized = np.mean([a["alpha_annualized"] for _, a in pairs])

    print(f"\n{test_name} (n={len(pairs)})")
    print(f"  Mean FF5 annualized alpha:       {ff5_annualized:.2%}")
    print(f"  Mean augmented annualized alpha: {aug_annualized:.2%}")
    print(f"  Weighted mean daily diff:        {weighted_mean:.6f}")
    print(f"  z-stat: {z_stat:.4f}, p-value (one-tailed): {p_value:.4f}")
    print(
        f"  {'Significantly closer to 0 (p < 0.05)' if p_value < 0.05 else 'Not significant'}"
    )


with open("./data/alphas.json") as f:
    data = json.load(f)

ff5 = [d["ff5"] for d in data]
uncertainty = [d["uncertainty"] for d in data]
disclosure = [d["disclosure"] for d in data]
conflicted = [d["conflicted"] for d in data]

# Filter to top quartile by FF5 annualized alpha
ff5_alphas = [f["alpha_annualized"] if f is not None else None for f in ff5]
PERCENTILE = 75
threshold = np.nanpercentile([a for a in ff5_alphas if a is not None], PERCENTILE)
top_q = [i for i, a in enumerate(ff5_alphas) if a is not None and a >= threshold]

print(
    f"Top {100 - PERCENTILE} percentile threshold: {threshold:.2%} ({len(top_q)} members)"
)
names = [d["name"] for d in data]


TOP_X = 30

top_q_sorted = sorted(top_q, key=lambda i: ff5_alphas[i], reverse=True)

print(f"\nTop {TOP_X} members by FF5 annualized alpha:")
print(f"{'Name':<30} {'FF5 Alpha':>12}")
print("-" * 43)
for i in top_q_sorted[:TOP_X]:
    print(f"  {names[i].title():<28} {ff5_alphas[i]:>12.2%}")

ff5 = [ff5[i] for i in top_q]
uncertainty = [uncertainty[i] for i in top_q]
disclosure = [disclosure[i] for i in top_q]
conflicted = [conflicted[i] for i in top_q]

test_ff5_vs_zero(ff5)

print(
    f"\n=== Augmented FF5 Factor Significance Tests (Top {100-PERCENTILE} percentile by FF5 Alpha) ==="
)
print("Alt: augmented alpha is significantly closer to 0 than FF5 (one-tailed)")

weighted_test(ff5, uncertainty, "Uncertainty Index")
weighted_test(ff5, disclosure, "Disclosure Lag")
weighted_test(ff5, conflicted, "Conflict of Interest")
ALPHA_LEVEL = 0.05


def is_significant(result, alpha=ALPHA_LEVEL, one_tailed=True):
    if result is None or is_outlier(result):
        return False
    z = result["alpha_daily"] / result["alpha_se"]
    p = stats.norm.sf(z) if one_tailed else 2 * stats.norm.sf(abs(z))
    return p < alpha


sig_idx = [i for i, f in enumerate(ff5) if is_significant(f)]

print(f"\n{len(sig_idx)} members with FF5 alpha significantly > 0 (p < {ALPHA_LEVEL}):")
print(f"{'Name':<30} {'Alpha':>10} {'z':>8} {'p':>8}")
print("-" * 60)
for i in sorted(sig_idx, key=lambda j: ff5[j]["alpha_annualized"], reverse=True):
    f = ff5[i]
    z = f["alpha_daily"] / f["alpha_se"]
    p = stats.norm.sf(z)
    print(
        f"  {names[i].title():<28} {f['alpha_annualized']:>10.2%} {z:>8.2f} {p:>8.4f}"
    )
