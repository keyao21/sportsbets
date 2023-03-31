import os
import datetime
import itertools
import functools
import pickle
from enum import Enum
import pandas as pd
import config
import odd_scraper


NBAAPI_TEAMS = {   
    "Atlanta Hawks": "ATL", 
    "Boston Celtics": "BOS", 
    "Cleveland Cavaliers": "CLE", 
    "New Orleans Pelicans": "NOP", 
    "Chicago Bulls": "CHI", 
    "Dallas Mavericks": "DAL", 
    "Denver Nuggets": "DEN", 
    "Golden State Warriors": "GSW", 
    "Houston Rockets": "HOU", 
    "Los Angeles Clippers": "LAC", 
    "Los Angeles Lakers": "LAL", 
    "Miami Heat": "MIA", 
    "Milwaukee Bucks": "MIL", 
    "Minnesota Timberwolves": "MIN", 
    "Brooklyn Nets": "BKN", 
    "New York Knicks": "NYK", 
    "Orlando Magic": "ORL", 
    "Indiana Pacers": "IND", 
    "Philadelphia 76ers": "PHI", 
    "Phoenix Suns": "PHX", 
    "Portland Trail Blazers": "POR", 
    "Sacramento Kings": "SAC", 
    "San Antonio Spurs": "SAS", 
    "Oklahoma City Thunder": "OKC", 
    "Toronto Raptors": "TOR", 
    "Utah Jazz": "UTA", 
    "Memphis Grizzlies": "MEM", 
    "Washington Wizards": "WAS", 
    "Detroit Pistons": "DET", 
    "Charlotte Hornets": "CHA"
}

SBR_TEAMS = {
    "Atlanta": "ATL",
    "Boston": "BOS",
    "Brooklyn": "BKN",
    "Charlotte": "CHA",
    "Chicago": "CHI",
    "Cleveland": "CLE",
    "Dallas": "DAL",
    "Denver": "DEN",
    "Detroit": "DET",
    "Golden State": "GSW",
    "Houston": "HOU",
    "Indiana": "IND",
    "L.A. Clippers": "LAC",
    "L.A. Lakers": "LAL",
    "Memphis": "MEM",
    "Miami": "MIA",
    "Milwaukee": "MIL",
    "Minnesota": "MIN",
    "New Orleans": "NOP",
    "New York": "NYK",
    "Oklahoma City": "OKC",
    "Orlando": "ORL",
    "Philadelphia": "PHI",
    "Phoenix": "PHX",
    "Portland": "POR",
    "Sacramento": "SAC",
    "San Antonio": "SAS",
    "Toronto": "TOR",
    "Utah": "UTA",
    "Washington": "WAS"
}

SBR_NHL_TEAMS = {
    "BOS":"BOS",
    "CBJ":"CLB",
    "FLA":"FLA",
    "MTL":"MON",
    "OTT":"OTT",
    "PHI":"PHI",
    "PIT":"PIT",
    "NSH":"NAS",
    "TB":"TB",
    "WSH":"WAS",
    "DET":"DET",
    "CAR":"CAR",
    "CHI":"CHI",
    "STL":"STL",
    "EDM":"EDM",
    "LA":"LA",
    "SEA":"SEA",
    "ANA":"ANA",
    "SJ":"SJ",
    "VGK":"VEG"
}



class GamePart(str, Enum): 
    FULL = "full-game"
    HALF1 = "1st-half"
    HALF2 = "2nd-half"
    Q1 = "1st-quarter"
    Q2 = "2nd-quarter"
    Q3 = "3rd-quarter"
    Q4 = "4th-quarter"


GAME_PART_ORDER = { # maps to period where betting ends (exclusive)
    "HALF1" : 3,
    "Q1"    : 2,
    "Q2"    : 3,
    "Q3"    : 4,
    "Q4"    : float("inf"),
    "HALF2" : float("inf"),
    "FULL"  : float("inf")
}

GAME_PART_START = { # maps to period where betting starts
    "HALF1" : 1,
    "Q1"    : 1,
    "Q2"    : 2,
    "Q3"    : 3,
    "Q4"    : 4,
    "HALF2" : 3,
    "FULL"  : 1
}


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
        for gp in GamePart
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
                # t if t not in SBR_TEAMS else SBR_TEAMS[t]
                t if t not in SBR_NHL_TEAMS else SBR_NHL_TEAMS[t] 
                for t in data_i["teams"][j]
            ]
            rows[j].extend(short_teams)
            rows[j].extend(data_i["score"][j])
            for b in config.BOOKS: 
                rows[j].extend(data_i["odds_by_book"][j][b])
        all_rows.extend(rows)
    games_data = pd.DataFrame(all_rows, columns=col_headers)
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


def select_cols(games_data): 
    return games_data\
        [["arb_sig", "statustxt", "game_part", "home", "away"]
         + [f"book{l}{calcstr}" for calcstr in ["", "_cost"] for l in ["h","a"]]
         + ["return", "h_rawio", "a_rawio"]
         + [f"book{l}_netpayout" for l in ["h","a"]]
         #+ [b+l for l in ["h","a"] for b in config.BOOKS]
        ]


def filter_games_data(games_data): 
    # filter dataframe in email body. this is a general filter.
    games_data = games_data\
        .loc[~games_data.arb_sig.isnull() & games_data.arb_sig]\
        .loc[games_data.date > datetime.datetime.today()-datetime.timedelta(days=30)]\
        .sort_values("date",ascending=False)
    return games_data


def filter_snaps_data(games_data): 
    # this is a specific filter
    # get only usable return periods
    # filter out unusable bookies like PB.
    fsnaps_data = games_data\
        .loc[~games_data.arb_sig.isnull() & games_data.arb_sig]\
        .loc[(games_data.game_part.map(GAME_PART_ORDER) > games_data.period_adj)]\
        .loc[games_data.status != 3]\
        .loc[~(((games_data.bookh.str.match("PB")) | (games_data.booka.str.match("PB"))) & ~games_data.game_part.str.match("FULL"))]\
        .loc[
        # crazy stuff for excluding DK interquarter stuff when you cant bet.
        # if the game has started, DK is a book, and the current quarter/half is not in the betting quarter half
         ~(
           ~(games_data.period_adj==0 | games_data.period_adj.isnull()) 
           & ((games_data.bookh=="DK") | (games_data.booka=="DK")) 
           & (games_data.game_part.map(GAME_PART_START) > games_data.period_adj) 
          )
        ]
    return fsnaps_data


def get_non_started_filter(games_data): 
    return (games_data.status.isnull() | games_data.status.isin([0,1]))


def get_full_game_filter(games_data): 
    return (games_data.game_part=="FULL")
