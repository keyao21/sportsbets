import os 
import itertools
import pickle
import datetime
import numpy as np
import pandas as pd
from pretty_html_table import build_table
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import odd_scraper
import config


def make_games_data():
    # get historical data
    data = [
        pickle.load(open(os.path.join(config.RESULTS_DIR,f), "rb")) 
        for f in os.listdir(config.RESULTS_DIR)
    ]
    # get data for next games
    data.extend(
        odd_scraper.run_current(gp) for gp in config.GamePart
    )
    col_headers = \
        ["date", "game_part", "home", "away", "SCOREh", "SCOREa"] + \
        list(itertools.chain(*[[b+"h", b+"a"] for b in config.BOOKS]))
    all_rows = []
    for data_i in data:
        dt, game_part, teams, results, odds = data_i
        n_games = len(teams)
        rows = [[dt, game_part] for _ in range(n_games)]
        for j in range(n_games): 
            rows[j].extend(teams[j])
            rows[j].extend(results[j])
            for b in config.BOOKS: 
                rows[j].extend(odds[j][b])
        all_rows.extend(rows)
    games_data = pd.DataFrame(all_rows, columns=col_headers)
    return games_data


def calc_payout(row, col): 
    if row[col] < 0: 
        return 100
    return abs(row[col])


def calc_cost(row, col): 
    if row[col] < 0: 
        return abs(row[col])
    return 100


def opp_leg(leg): 
    return "h" if leg=="a" else "a"


def calc_rawimplprob(row, col):
    payout = calc_payout(row, col)
    cost = calc_cost(row, col)
    return cost/(payout+cost)


def add_calc_cols(games_data):
    # add columns per book
    for book in config.BOOKS:
        for leg in ["h","a"]:
            games_data[book+leg+"_rawio"] = games_data.apply(lambda r: calc_rawimplprob(r, book+leg), axis=1)
        games_data[book+"_rawiosum"] = sum(games_data[book+leg+"_rawio"] for leg in ["h","a"])
        games_data[book+"_vig"] = games_data[book+"_rawiosum"] - 1
        for leg in ["h","a"]:
            games_data[book+leg+"_io"] = games_data[book+leg+"_rawio"] - games_data[book+"_vig"]/2
    return games_data


def add_arb_cols(games_data):

    def calc_impl_cost(row, leg):
        if row["arb_sig"]: 
            ba = row["booka"]
            bh = row["bookh"]
            raw_prob_a = row[f"{ba}a_rawio"]
            raw_prob_h = row[f"{bh}h_rawio"]
            return (raw_prob_h/raw_prob_a)*row[f"book{opp_leg(leg)}_cost"]

    def calc_impl_netpayout(row, leg):
        # subtracts costs
        if row["arb_sig"]: 
            b = row[f"book{leg}"]
            raw_prob = row[f"{b}{leg}_rawio"]
            ratio = (1-raw_prob) / raw_prob
            return ratio*row[f"book{leg}_cost"] - row[f"book{opp_leg(leg)}_cost"] 

    # add arb signal columns
    h_rawio_cols = [f"{b}h_rawio" for b in config.BOOKS]
    a_rawio_cols = [f"{b}a_rawio" for b in config.BOOKS]
    games_data["arb_sig"] = games_data.apply(lambda row: min(row[h_rawio_cols])+min(row[a_rawio_cols]) < 1, axis=1)
    games_data["booka"] = games_data.apply(lambda r: config.BOOKS[np.argmin(r[a_rawio_cols])] if r["arb_sig"] else None, axis=1)
    games_data["bookh"] = games_data.apply(lambda r: config.BOOKS[np.argmin(r[h_rawio_cols])] if r["arb_sig"] else None, axis=1)
    games_data["booka_cost"] = games_data["arb_sig"].apply(lambda x: 100 if x else 0)
    games_data["bookh_cost"] = games_data.apply(lambda r: calc_impl_cost(r, leg="h"), axis=1)
    games_data["booka_netpayout"] = games_data.apply(lambda r: calc_impl_netpayout(r,leg="a"), axis=1)
    games_data["bookh_netpayout"] = games_data.apply(lambda r: calc_impl_netpayout(r,leg="h"), axis=1)
    games_data["a_rawio"] = games_data.apply(lambda r: r[f"{r['booka']}a_rawio"] if r["arb_sig"] else None, axis=1)
    games_data["h_rawio"] = games_data.apply(lambda r: r[f"{r['bookh']}h_rawio"] if r["arb_sig"] else None, axis=1)
    games_data["return"] = games_data["booka_netpayout"] / (games_data["bookh_cost"] + games_data["booka_cost"])
    return games_data


def send_email(games_data, attachments): 
    recipients = ["kyao747@gmail.com", "sivaduil@gmail.com"] 
    emaillist = [elem.strip().split(',') for elem in recipients]
    msg = MIMEMultipart()
    msg['From'] = 'helloitsmrbets@gmail.com'
    today_dt = datetime.date.today()
    today_dt_time = datetime.datetime(year=today_dt.year, month=today_dt.month, day=today_dt.day)

    # show next/today's games 
    today_games_data = games_data[games_data.date>=today_dt_time]
    html0 = f"""\
            <html>
              <head>Next/current game</head>
              <body>
                {build_table(
                    select_cols(
                        today_games_data
                        .sort_values("arb_sig",ascending=False)
                    ),
                    "blue_light"
                    ) if len(today_games_data) > 0 else "None"
                }
              </body>
            </html>
            """
    part0 = MIMEText(html0, 'html')
    msg.attach(part0)

    # show games with signal
    filt_games_data = select_cols(filter_games_data(games_data))
    filt_today_games_data = filt_games_data[filt_games_data.date>=today_dt_time]
    html1 = f"""\
            <html>
              <head>Total prob inconsistencies in next/current game</head>
              <body>
                {build_table(filt_today_games_data,"blue_light")
                    if len(filt_today_games_data) > 0 else "None"
                }
              </body>
            </html>
            """
    part1 = MIMEText(html1, 'html')
    msg.attach(part1)

    html2 = f"""\
            <html>
              <head>All total prob inconsistencies over past 30 days</head>
              <body>
                {build_table(filt_games_data,"blue_light")}
              </body>
            </html>
            """
    part2 = MIMEText(html2, 'html')
    msg.attach(part2)

    # add historical data as attachment
    hist_data_loc = attachments["hist_data_loc"]
    with open(hist_data_loc) as fp: 
        attachment = MIMEText(fp.read(), _subtype="text")
    attachment.add_header("Content-Disposition", "attachment", filename=hist_data_loc)
    msg.attach(attachment)
    
    # write subject 
    msg['Subject'] = f"{len(filt_today_games_data)} opportunities right now"

    try:
        """Checking for connection errors"""
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()#NOT NECESSARY
        server.starttls()
        server.ehlo()#NOT NECESSARY
        server.login('helloitsmrbets@gmail.com',"efutywmvxjzhkojp")
        server.sendmail(msg['From'], emaillist , msg.as_string())
        server.close()

    except Exception as e:
        print("Error for connection: {}".format(e))


def archive_df_as_csv(df, filename): 
    hist_data_loc =  os.path.join(config.ARCHIVE_DIR, filename)
    df.to_csv(hist_data_loc)
    return hist_data_loc


def select_cols(games_data): 
    return games_data\
        [["arb_sig", "date", "home", "away", "game_part"]
         + [f"book{l}{calcstr}" for calcstr in ["", "_cost", "_netpayout"] for l in ["h","a"]]
         + ["h_rawio", "a_rawio", "return"]
         + [b+l for l in ["h","a"] for b in config.BOOKS] 
         + [b+l+"_rawio" for l in ["h","a"] for b in config.BOOKS]
        ]


def filter_games_data(games_data): 
    # filter dataframe in email body
    games_data = games_data\
        [games_data.arb_sig]\
        [games_data.date > datetime.datetime.today()-datetime.timedelta(days=30)]\
        .sort_values("date",ascending=False)
    return games_data


if __name__ == '__main__':
    run_dt = datetime.date.today()
    games_data = make_games_data()
    games_data = add_calc_cols(games_data)
    games_data = add_arb_cols(games_data)
    hist_data_loc = archive_df_as_csv(games_data, filename=f"fullhistory_{run_dt.strftime('%Y%m%d')}.csv")
    send_email(
        games_data,
        attachments={"hist_data_loc": hist_data_loc}
    )
    os.remove(hist_data_loc)