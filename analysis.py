import os 
import itertools
import functools
import pickle
import argparse
import datetime
import numpy as np
import pandas as pd
from nba_api.live.nba.endpoints import scoreboard
import odd_scraper
import config
import utils


def load_hist_data(): 
    # get historical data
    data = [
        pickle.load(open(os.path.join(config.HIST_DIR,f), "rb")) 
        for f in os.listdir(config.HIST_DIR)
    ]
    return data


def load_snap_data(): 
    # get snap daily data
    data = [
        pickle.load(open(os.path.join(config.SNAPS_DIR,f), "rb")) 
        for f in os.listdir(config.SNAPS_DIR)
    ]
    return data


def load_current_data(): 
    # get data for next games
    data = [
        odd_scraper.run_current(gp) 
        for gp in config.GamePart
    ]
    return data


def make_games_data(data):
    col_headers = \
        ["timestamp", "date", "game_part", "home", "away", "SCOREh", "SCOREa"] + \
        list(itertools.chain(*[[b+"h", b+"a"] for b in config.BOOKS]))
    all_rows = []
    for data_i in data:
        n_games = len(data_i["teams"])
        rows = [
            [data_i["timestamp"], data_i["date"], data_i["game_part"]] 
            for _ in range(n_games)
        ]
        for j in range(n_games):
            short_teams = [
                t if t not in utils.SBR_TEAMS else utils.SBR_TEAMS[t] 
                for t in data_i["teams"][j]
            ]
            rows[j].extend(short_teams)
            rows[j].extend(data_i["score"][j])
            for b in config.BOOKS: 
                rows[j].extend(data_i["odds_by_book"][j][b])
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
            games_data[book+leg+"_rawio"] = games_data.apply(lambda r: 
                np.nan if r[book+leg] is None else calc_rawimplprob(r, book+leg), axis=1)
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
    
    def arb_sig(row): 
        if not (row[h_rawio_cols].isnull().all() or row[a_rawio_cols].isnull().all()) :
            return np.nanmin(row[h_rawio_cols])+np.nanmin(row[a_rawio_cols]) < 1
        return False

    games_data["arb_sig"] = games_data.apply(arb_sig, axis=1)
    games_data["booka"] = games_data.apply(lambda r: None if not r["arb_sig"] else config.BOOKS[np.nanargmin(r[a_rawio_cols])], axis=1)
    games_data["bookh"] = games_data.apply(lambda r: None if not r["arb_sig"] else config.BOOKS[np.nanargmin(r[h_rawio_cols])], axis=1)
    games_data["booka_cost"] = games_data["arb_sig"].apply(lambda x: 100 if x else 0)
    games_data["bookh_cost"] = games_data.apply(lambda r: calc_impl_cost(r, leg="h"), axis=1)
    games_data["booka_netpayout"] = games_data.apply(lambda r: calc_impl_netpayout(r,leg="a"), axis=1)
    games_data["bookh_netpayout"] = games_data.apply(lambda r: calc_impl_netpayout(r,leg="h"), axis=1)
    games_data["a_rawio"] = games_data.apply(lambda r: r[f"{r['booka']}a_rawio"] if r["arb_sig"] else None, axis=1)
    games_data["h_rawio"] = games_data.apply(lambda r: r[f"{r['bookh']}h_rawio"] if r["arb_sig"] else None, axis=1)
    games_data["return"] = games_data["booka_netpayout"] / (games_data["bookh_cost"] + games_data["booka_cost"])
    return games_data


def make_arb_data(games_data):
    key_cols = ["timestamp", "date", "game_part", "home", "away", "SCOREh", "SCOREa"]
    h_rawio_cols = [f"{b}h_rawio" for b in config.BOOKS]
    a_rawio_cols = [f"{b}a_rawio" for b in config.BOOKS]
    odds_cols = [b+l for l in ["h","a"] for b in config.BOOKS]
    games_raw_odds = games_data.loc[:,key_cols + h_rawio_cols + a_rawio_cols]
    games_raw_odds = games_raw_odds.set_index(key_cols)
    games_raw_odds.columns = pd.MultiIndex.from_tuples(
        [("h", b) for b in config.BOOKS] + [("a", b) for b in config.BOOKS]
    )
    def create_stack_df(games_raw_odds, leg): 
        games_raw_odds = games_raw_odds[leg]
        games_raw_odds.columns.name = f"book{leg}"
        games_raw_odds = games_raw_odds.stack()
        games_raw_odds.name = f"{leg}_rawio"
        games_raw_odds = games_raw_odds.reset_index().set_index(key_cols)
        return games_raw_odds
    stackh = create_stack_df(games_raw_odds, "h")
    stacka = create_stack_df(games_raw_odds, "a")
    combos = pd.merge(
        stackh,
        stacka,
        how="outer",
        left_index=True,
        right_index=True
    ).reset_index()
    combos["arb_sig"] = (~combos.h_rawio.isnull())&(~combos.a_rawio.isnull())&(combos.h_rawio+combos.a_rawio<1.0)
    arbs = combos.loc[combos.arb_sig]
    arbs = arbs.assign(booka_cost=100)
    arbs["bookh_cost"] = (arbs["h_rawio"]/arbs["a_rawio"]) * arbs["booka_cost"] 
    arbs["booka_netpayout"] = ((1-arbs["a_rawio"])/arbs["a_rawio"]) * arbs["booka_cost"] - arbs["bookh_cost"]
    arbs["bookh_netpayout"] = arbs["booka_netpayout"]
    arbs["return"] = (1/(arbs["h_rawio"]+arbs["a_rawio"])) - 1
    arb_cols = ["booka_cost", "bookh_cost", "booka_netpayout", "bookh_netpayout", "return"]
    arb_data = pd.merge(
        pd.merge(
            combos,arbs[arb_cols],
            how="left",
            left_index=True, right_index=True
        ),
        games_data.loc[:,key_cols + odds_cols].set_index(key_cols),
        how="left",
        on=key_cols
    )
    return arb_data


def add_live_stats_cols(games_data):
    score_board_inst = scoreboard.ScoreBoard()
    score_boards = score_board_inst.get_dict()
    stats_data = [
        [
            games["awayTeam"]["teamTricode"],
            games["homeTeam"]["teamTricode"], # why is the away team flipped? is this a bug or am i dumb
            games["gameStatusText"],
            games["gameStatus"],
            games["period"]
        ] 
        for games in score_boards["scoreboard"]["games"]
    ]
    stats_data_df = pd.DataFrame(
        stats_data, 
        columns=["home","away","statustxt","status","period"]
    )
    # (hacky?) way to adjust end periods and remove end of quarters and finals when theyre no longer valid for the bet
    stats_data_df["period_adj"] = stats_data_df["period"] \
        + (stats_data_df["statustxt"].str.contains("End|Half", regex=True) | stats_data_df["period"]==3).astype(int)
    today_dt = datetime.date.today()
    today_dt_time = datetime.datetime(year=today_dt.year, month=today_dt.month, day=today_dt.day)
    stats_data_df["date"] = today_dt_time
    games_data = pd.merge(
        games_data,
        stats_data_df,
        on=["home","away","date"],
        how="left"
    )
    games_data["status"] = games_data["status"].fillna(0) # set status default
    return games_data


def save_df_snapshot(df):
    ts = datetime.datetime.now()
    filename = f"snap_{ts.strftime('%Y%m%d%H%M%S')}.dat"
    with open(os.path.join(config.SNAPS_DIR, filename), "wb") as f:
        df['timestamp'] = ts
        pickle.dump(df, f)


def make_snaps_data(data): 
    return functools.reduce(
        lambda d1,d2: pd.concat([d1,d2], ignore_index=True), 
        data
    )


def make_data_by_uniq_arb(snaps_data): 
    # agg by unique bet arbs
    snaps_data["return_dummy"] = snaps_data["return"]
    fsnapsdata_byarb = snaps_data\
        [~snaps_data["return"].isnull()]\
        .groupby(["return_dummy","date","game_part","home","away","bookh","booka"])\
        .agg(
            arb_return=('return', lambda x: x.sum()/len(x)),
            n_timestamps=('return', len),
            duration_in_min=('timestamp', lambda x: 
                10 if len(x) == 1 
                else (max(x)-min(x)).total_seconds()/60 )
        )
    return fsnapsdata_byarb


def make_return_stats(fsnapsdata_byarb, group_by=["date","game_part"]):
    # agg by game_part
    fsnapsdata_byarb["returnxdur"] = fsnapsdata_byarb["arb_return"] * fsnapsdata_byarb["duration_in_min"]
    fsnapsdata_byarb_agg = \
        fsnapsdata_byarb.groupby(group_by)\
            .agg(
                n_samples=('arb_return', len),
                avg_return=('arb_return', lambda x: x.sum()/len(x)),
                sum_returnxdur=('returnxdur', sum),
                sum_dur=('duration_in_min', sum),
                avg_dur=('duration_in_min', lambda x: x.sum()/len(x))
        )
    fsnapsdata_byarb_agg["wavg_return"] = fsnapsdata_byarb_agg["sum_returnxdur"] / fsnapsdata_byarb_agg["sum_dur"]
    fsnapsdata_byarb_agg = fsnapsdata_byarb_agg.sort_values(["wavg_return"], ascending=False)
    return fsnapsdata_byarb_agg


if __name__ == '__main__':
    run_dt = datetime.date.today()
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--simple', action='store_true')
    group.add_argument('--hist', action='store_true')
    group.add_argument('--stats', action='store_true')
    parser.add_argument('--email', action='store_true')
    parser.add_argument('--check_email', action='store_true')
    args = parser.parse_args()

    if args.simple:
        # general run for current/next games.
        loaded_data = load_current_data()
        games_data = make_games_data(loaded_data)
        games_data = add_calc_cols(games_data)
        games_data = make_arb_data(games_data)
        games_data = add_live_stats_cols(games_data)
        save_df_snapshot(games_data)
        if args.email: 
            utils.send_email(
                games_data,
                incl_hist=False
            )
        elif args.check_email and (len(games_data[games_data.arb_sig])>0): 
            utils.send_email(
                games_data,
                incl_hist=False
            )

    elif args.hist:
        # historical run with all past games and current/next games. 
        loaded_data = load_hist_data() + load_current_data()
        games_data = make_games_data(loaded_data)
        games_data = add_calc_cols(games_data)
        games_data = make_arb_data(games_data)
        games_data = add_live_stats_cols(games_data)
        if args.email:
            utils.send_email(
                games_data,
                incl_hist=True
            )

    elif args.stats: 
        # run stats
        loaded_data = load_snap_data()
        snaps_data = make_snaps_data(loaded_data)
        snaps_data = utils.filter_snaps_data(snaps_data)
        fsnapsdata_byarb = make_data_by_uniq_arb(snaps_data)
        fsnapsdata_byarb_agg_dt = make_return_stats(fsnapsdata_byarb, group_by=["date"]).sort_values("date")
        fsnapsdata_byarb_agg_gp = make_return_stats(fsnapsdata_byarb, group_by=["game_part"])
        fsnapsdata_byarb_agg_bk = make_return_stats(fsnapsdata_byarb, group_by=["bookh","booka","game_part"])
        fsnapsdata_byarb_agg = make_return_stats(fsnapsdata_byarb, group_by=["date","game_part"])
        if args.email:
            utils.send_stat_email(
                {
                    "By date"           : fsnapsdata_byarb_agg_dt,
                    "By game part"      : fsnapsdata_byarb_agg_gp,
                    "By date, game part": fsnapsdata_byarb_agg,
                    "By bookies"        : fsnapsdata_byarb_agg_bk
                }
            )
        