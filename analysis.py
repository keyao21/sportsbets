import requests
import json
import datetime
import numpy as np
import pandas as pd
import config
import utils
from nba_api.live.nba.endpoints import scoreboard


def calc_payout(row, col): 
    if row[col] < 0: 
        return 100
    return abs(row[col])


def calc_cost(row, col): 
    if row[col] < 0: 
        return abs(row[col])
    return 100


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
    combos = pd.merge(
        create_stack_df(games_raw_odds, "h"),
        create_stack_df(games_raw_odds, "a"),
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


def deprecated_add_live_stats_cols(games_data):
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
        + (stats_data_df["statustxt"].str.contains("End|Half", regex=True) | (stats_data_df["period"]==3)).astype(int)
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


def add_live_stats_cols(games_data):
    url = 'http://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard'
    r = requests.get(url)
    data = json.loads(r.text)
    stats_data = [
        [
            event["shortName"].split(" @ ")[1],
            event["shortName"].split(" @ ")[0],
            event["status"]["type"]["shortDetail"], # 
            event["status"]["type"]["name"],
            event["status"]["type"]["completed"],
            event["status"]["type"]["description"],
            event["status"]["period"]
        ]
        for event  in data["events"]
    ]
    stats_data_df = pd.DataFrame(
        stats_data,
        columns=["home","away","shortDetail","name","completed","description","period"]
        # columns=["home","away","statustxt","status","period"]
    )
    stats_data_df["statustxt"] = stats_data_df["shortDetail"]
    stats_data_df["status"] = stats_data_df["name"].map({
        "STATUS_FINAL":3,
        "STATUS_IN_PROGRESS":2,
        "STATUS_END_PERIOD":2,
        "STATUS_SCHEDULED":1
    })
    stats_data_df["period"]
    # (hacky?) way to adjust end periods and remove end of quarters and finals when theyre no longer valid for the bet
    stats_data_df["period_adj"] = stats_data_df["period"] \
        + (stats_data_df["statustxt"].str.contains("End|Final", regex=True)).astype(int)
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
