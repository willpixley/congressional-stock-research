import os
import pandas as pd
from ff5 import run_reg
from scipy import stats


output_dir = "../django/output"
files = [f for f in os.listdir(output_dir) if f.endswith(".csv")]
print(f"Found {len(files)} return files...")

significant = 0
total = 0

for file in files:
    prefix = file.replace(".csv", "")
    result = run_reg(prefix)
    if result is None:
        continue
    total += 1
    # One-tailed p-value: is alpha significantly greater than 0?
    t_stat = result["alpha_tstat"]
    df_resid = result.get("df_resid")
    p_one_tailed = stats.t.sf(t_stat, df=df_resid)  # sf = 1 - cdf, upper tail

    if result["alpha_daily"] > 0 and p_one_tailed < 0.05:
        significant += 1
        print(
            f"  {prefix}: alpha={result['alpha_annualized']:.2%}, t={t_stat:.4f}, p={p_one_tailed:.4f}"
        )

print(f"\n{significant}/{total} members have alpha significantly above 0 (p < 0.05)")
