import pandas as pd
import statsmodels.api as sm


def run_reg(file_prefix):
    factors = pd.read_csv("./data/ff5.csv", index_col="date", parse_dates=True)

    returns = pd.read_csv(
        f"./output/{file_prefix}.csv", index_col=0, parse_dates=True
    ).squeeze()

    df = returns.to_frame(name="ret").join(factors, how="inner")
    df["excess_ret"] = df["ret"] - df["RF"]

    X = df[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]]
    X = sm.add_constant(X)
    y = df["excess_ret"]

    model = sm.OLS(y, X).fit(cov_type="HC3")

    print(model.summary())
    alpha_daily = model.params["const"]
    alpha_annualized = (1 + alpha_daily) ** 252 - 1
    print(f"Annualized excess returns: {alpha_annualized:.2%}%")

    with open(f"./output/{file_prefix}.txt", "w") as f:
        f.write(model.summary().as_text())
