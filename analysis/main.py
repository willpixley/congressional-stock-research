from ff5 import *
from portfolio import *
import sys
import pandas as pd

if __name__ == "__main__":
    df = pd.read_csv("./data/closed_trade_segments.csv")

    try:
        bio_guide_id = sys.argv[1]
        file_prefix = sys.argv[2]
    except:
        print("Provide args bio_guide_id and file_prefix")
        print(
            df.groupby(["member_bio_guide_id", "member_name"])
            .size()
            .reset_index(name="trade_count")
            .sort_values("trade_count", ascending=False)
            .head(50)
        )
        quit()
    # print(
    #     df.groupby(["member_bio_guide_id", "member_name"])
    #     .size()
    #     .reset_index(name="trade_count")
    #     .sort_values("trade_count", ascending=False)
    #     .head(50)
    # )
    returns = get_portfolio_returns(bio_guide_id, df)
    returns.to_csv(f"./output/{file_prefix}.csv")

    run_reg(file_prefix)


## M001136 Lisa C. McClain
