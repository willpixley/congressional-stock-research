# Overview

The code in this repository is used to import, clean, and manage the data for the congressional stock research project. It is adapted from an existing project — a web app dedicated to tracking, analyzing, and displaying congresional stock trades in a web app. The original web app used a Django backend connected to a Postgres DB. I decided to stick with this architecture as it allows for robust data validation and easy data manipulation with Python. It also required minimal setup since I merely had to adapt the existing code to fit the use case. I've stripped away the aspects of the codebase I no longer need, like daily updates and API endpoints. The core data ingestion and management remains the same, however. The goal is that this will help you easily 

# Getting started
1. Install Docker
2. Edit `example.env` to contain your required secrets and rename it to `.env`
    - Instructions provided in the comments of that file
3. Make sure the Docker daemon is running, either by opening the Desktop app or using the CLI tool
4. Run `docker compose up` to create and run the container 
5. Visit `localhost:8000` in your browser to make sure it is up and running. If it says "OK", everything is working as intended
6. This may or may not create the correct tables. To ensure it, exec into the Django docker container and run the migrations:
    1. Run `docker exec -it django sh` to enter the shell inside the django docker container
    2. In the shell, run `python manage.py makemigrations`
    3. Run `python manage.py migrate`. This should populate the DB with the correct tables.


# Reproducing data

If you run these multiple times, I recommend wiping the corresponding tables through the Postgres console. You can enter postgres console using `docker exec -it db psql -U postgres`. I also recommend performing data creation in the order it is listed below. This cuts dependencies between tables and reduces errors.

## Stocks

This will populate the table `server_stock` with over 11,000 stocks from three different American exchanges. *Note: Around 20 stocks were inserted manually. These can be found in `get_stocks.py` in the `manually_inserted_stocks` array. I inserted these manually using the postgres console, but writing a script to import these would be trivial.*

1. Enter the Django shell using the steps in "Getting Started" step 6.
2. Run `python get_stocks.py`. This will pull stocks from the files in the `/data` directory. Since the code currently does not support Sectors, it creates a placeholder sector

## Member Info

Populates the `server_congressmember`, `server_term`, and `server_congress` tables.

1. Enter the Django shell
2. Run `python get_member_info.py`. It creates congresses 80 - 119, scrapes member IDs, then populates detailed member info and terms
    - This command will take around 30 minutes. There are `time.sleep()` calls between each API call to avoid rate limiting. Feel free to delete or modify these to cut the time, but it may end up throwing errors. Or grab a coffee and watch a show. Your call.

## Stock Trades

The moment you've all been waiting for. This command will populate the `server_trade` table from the CSV stored in the `/data` directory. The data was downloaded from [Quiver Quant](https://www.quiverquant.com/) and covers congressional trades from 2012 (the beginning of the STOCK Act) through the end of 2025. There are 109,000 rows in the dataset, but I was only able to correctly import and attribute 91,342 of them (after manually inserting the stocks mentioned above). 

1. Enter the Django shell
2. Run `python get_trades.py`
3. It will take a few minutes to run and print out the errors it sees along the way. *It will look like everything is erroring out. It is not*
4. Check the `trade_insert_report.json` for a full breakdown of errors and missing stocks. Stocks are missing due to being delisted, renamed, or on foreign exchanges. It is very difficult to find bulk datasets that contain. 
    - I could have created `Stock` objects on the fly, but chose not to because some entries are garbage values and cannot be verified that they are correct/real stocks.

## Trade Segments

Creates buy/sell pairs from the trades, matched on Member, stock, and amount. Segments can either be classified as "open" or "closed". A "closed" segment is a segment that has both a buy and sell trade. An "open" segment is simply a buy trade without a matching sell trade. 

1. Enter the Django shell
2. Run `python manage.py create_segments`
3. The command will create around 46,595 segments. 24,269 closed, 22,326 open


# Running into issues?

I believe this data should be easily available to anyone who wants it. If you're having trouble and are unable to solve it, feel free to send me an email at [will@willpixley.com](mailto:will@willpixley.com)