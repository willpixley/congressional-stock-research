def model_summary(model, file_prefix, test):
    if "const" not in model.params:
        print(f"Warning: no const in model for {file_prefix} {test}, skipping")
        return None

    alpha_daily = model.params["const"]
    alpha_se = model.bse["const"]
    alpha_tstat = model.tvalues["const"]
    alpha_pvalue = model.pvalues["const"]
    alpha_annualized = (1 + alpha_daily) ** 252 - 1

    print(f"Annualized excess returns: {alpha_annualized:.2%}")

    with open(f"./output/{file_prefix}_{test}.txt", "w") as f:
        f.write(model.summary().as_text())
        f.write(f"\nAnnualized excess returns: {alpha_annualized:.2%}")

    return {
        "alpha_daily": float(alpha_daily),
        "alpha_se": float(alpha_se),
        "alpha_tstat": float(alpha_tstat),
        "alpha_pvalue": float(alpha_pvalue),
        "alpha_annualized": float(alpha_annualized),
        "df_resid": int(model.df_resid),
    }


import pandas as pd
import json

df = pd.read_csv("./data/trade_segments.csv")

TOP_X = 5000

ticker_counts = df["stock_ticker"].value_counts().head(TOP_X)
print(ticker_counts)

with open(f"./output/top_{TOP_X}_tickers.json", "w") as f:
    json.dump(ticker_counts.index.tolist(), f, indent=2)

print(f"\nWrote {len(ticker_counts)} tickers to ./output/top_{TOP_X}_tickers.json")
