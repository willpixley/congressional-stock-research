import os
import json
import pandas as pd
import statsmodels.api as sm
from utils import model_summary


OUTPUT_DIR = "../django/output"
RESULTS_DIR = "./results"


def run_reg(file_prefix, returns_path):
    factors = pd.read_csv("./data/ff5.csv", index_col="date", parse_dates=True)

    returns = pd.read_csv(returns_path, index_col=0, parse_dates=True).squeeze()

    df = returns.to_frame(name="ret").join(factors, how="inner")
    df["excess_ret"] = df["ret"] - df["RF"]

    X = df[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]]
    X = sm.add_constant(X)
    y = df["excess_ret"]

    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})

    return model_summary(model, file_prefix, "reg")


def run_experiment(experiment_dir):
    """Run FF5 on every CSV in an experiment subdir, collect results."""
    name = os.path.basename(experiment_dir.rstrip("/"))
    csvs = sorted(f for f in os.listdir(experiment_dir) if f.endswith(".csv"))
    print(f"\n=== {name} ({len(csvs)} portfolios) ===")

    results = {}
    for fname in csvs:
        label = fname[:-4]
        path = os.path.join(experiment_dir, fname)
        try:
            results[label] = run_reg(f"{name}/{label}", path)
        except Exception as e:
            print(f"  [fail] {label}: {e}")
    return results


if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)

    experiments = [
        d
        for d in sorted(os.listdir(OUTPUT_DIR))
        if os.path.isdir(os.path.join(OUTPUT_DIR, d))
    ]

    all_results = {}
    for exp in experiments:
        all_results[exp] = run_experiment(os.path.join(OUTPUT_DIR, exp))

    with open(os.path.join(RESULTS_DIR, "all_ff5.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(
        f"\nWrote results for {len(all_results)} experiments to {RESULTS_DIR}/all_ff5.json"
    )
