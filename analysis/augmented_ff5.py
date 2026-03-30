import pandas as pd
import statsmodels.api as sm


def model_summary(model, file_prefix, test):
    print(model.summary())
    alpha_daily = model.params["const"]
    alpha_annualized = (1 + alpha_daily) ** 252 - 1
    print(f"Annualized excess returns: {alpha_annualized:.2%}%")

    with open(f"./output/{file_prefix}_{test}.txt", "w") as f:
        f.write(model.summary().as_text())


# For each day in return series it computes the average disclosure lag across their positions
def compute_disclosure_lag(member_df):
    member_df = member_df.copy()
    member_df["buy_date"] = pd.to_datetime(member_df["buy_date"])
    member_df["sell_date"] = pd.to_datetime(member_df["sell_date"])
    member_df["buy_disclosure_date"] = pd.to_datetime(member_df["buy_disclosure_date"])
    member_df["buy_disclosure_lag"] = (
        member_df["buy_disclosure_date"] - member_df["buy_date"]
    ).dt.days

    return member_df


# Ran with both Pelosi and Lisa McClain. Made models less accurate
def disclosure_lag(file_prefix, bio_guide_id):
    full_df = pd.read_csv("./data/closed_trade_segments.csv")
    factors = pd.read_csv("./data/ff5.csv", index_col="date", parse_dates=True)

    returns = pd.read_csv(
        f"./output/{file_prefix}.csv", index_col=0, parse_dates=True
    ).squeeze()

    member_df = full_df[full_df["member_bio_guide_id"] == bio_guide_id]
    member_df = compute_disclosure_lag(member_df)

    member_dates = returns.index
    daily_lag = []

    for date in member_dates:
        open_positions = member_df[
            (member_df["buy_date"] <= date) & (member_df["sell_date"] > date)
        ]
        if open_positions.empty:
            daily_lag.append(0.0)
        else:
            daily_lag.append(open_positions["buy_disclosure_lag"].mean())

    lag_series = pd.Series(daily_lag, index=member_dates, name="disclosure_lag")

    df = (
        returns.to_frame(name="ret")
        .join(factors, how="inner")
        .join(lag_series, how="inner")
    )
    df["excess_ret"] = df["ret"] - df["RF"]

    X = df[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "disclosure_lag"]]
    X = sm.add_constant(X)
    y = df["excess_ret"]

    model = sm.OLS(y, X).fit(cov_type="HC3")

    model_summary(model, file_prefix, "lag")


# Uses the daily policy uncertainty index as a 6th factor. Usually reduces alpha but not significant on my tests.
def uncertainty(file_prefix):
    factors = pd.read_csv("./data/ff5.csv", index_col="date", parse_dates=True)
    returns = pd.read_csv(
        f"./output/{file_prefix}.csv", index_col=0, parse_dates=True
    ).squeeze()

    unc = pd.read_csv("./data/uncertainty_data.csv")
    unc["date"] = pd.to_datetime(unc[["year", "month", "day"]])
    unc = unc.set_index("date")[["daily_policy_index"]]
    unc["daily_policy_index"] = (
        unc["daily_policy_index"] - unc["daily_policy_index"].mean()
    ) / unc[
        "daily_policy_index"
    ].std()  # normalize

    df = returns.to_frame(name="ret").join(factors, how="inner").join(unc, how="inner")
    df["excess_ret"] = df["ret"] - df["RF"]

    X = df[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "daily_policy_index"]]
    X = sm.add_constant(X)  # alpha
    y = df["excess_ret"]

    # model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    model = sm.OLS(y, X).fit(cov_type="HC3")

    model_summary(model, file_prefix, "unc")


if __name__ == "__main__":
    uncertainty("pelosi")
