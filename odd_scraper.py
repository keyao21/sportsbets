import os 
import requests
import regex as re
import pickle
import time
import logging
import datetime
from pprint import pprint, pformat
from bs4 import BeautifulSoup
import pandas as pd
import config
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y.%m.%d:%H:%M:%S'
)


def get_soup(str_lookback_date, game_part): 
    date_url_part = f"?date={str_lookback_date}" if str_lookback_date else ""
    URL = f"https://www.sportsbookreview.com/betting-odds/nba-basketball/money-line/{game_part}/{date_url_part}"
    page = requests.get(URL)
    soup = BeautifulSoup(page.content, "html.parser")
    return soup


def get_tablegames(str_lookback_date, game_part):
    soup = get_soup(str_lookback_date, game_part)
    # get data table
    tablebody = soup.find(id="tbody-nba")
    if tablebody: 
        tablegames_regex = re.compile('GameRows_eventMarketGridContainer__GuplK GameRows_neverWrap__gnQNO GameRows_compact__ZqqNS.*')
        tablegames = tablebody.find_all("div", {"class" : tablegames_regex})
        return tablegames
    return None


def parse_results(tb): 
    teams_regex = re.compile('GameRows_participants__Fdd1S.*')
    teams_html = tb.find_all("div", {"class" : teams_regex})
    results = [ 
        int(t.find("div", class_="GameRows_scores__YkN24").text)
        for t in teams_html 
    ]
    return results


def parse_teams(tb): 
    teams_regex = re.compile('GameRows_participants__Fdd1S.*')
    teams_html = tb.find_all("div", {"class" : teams_regex})
    teams = [ 
        t.find("span", class_="GameRows_participantBox__0WCRz").text
        for t in teams_html 
    ]
    return teams


def parse_odds(tb): 
    odds_regex = re.compile("OddsCells_pointer___xLMm OddsCells_margin__7d2oM.*")
    tableodds = tb.find_all("span", {"class" : odds_regex})
    # should be mgm, dk, fd, caesars, pb, wynn, betrivers, maybe check this
    odds_by_book = {b:[None, None] for b in config.BOOKS}
    for i,tableodds_i in enumerate(tableodds):
        moneyline = tableodds_i.find_all("span")[-1].text
        odds_by_book[config.BOOKS[i//2]][i%2] = None if moneyline=="-" else int(moneyline)
    return odds_by_book


def parse_date(soup): 
    text_date = soup.find("div", {"class": "OddsTable_timeContainer__vSxPK"}).get_text(strip=True)
    dt = datetime.datetime.strptime(text_date,"%A, %B %d, %Y")
    return dt


def run_and_dump(lookback_dt, game_part):
    unique_filename = f"{game_part}{lookback_dt.strftime('%Y%m%d')}.dat"
    str_lookback_date = lookback_dt.strftime("%Y-%m-%d")
    logging.info(f"running for {lookback_dt}, {game_part}")
    tablegames = get_tablegames(str_lookback_date, game_part)
    if tablegames is None: # no games found 
        return
    teams_by_game = [parse_teams(tb) for tb in tablegames]
    results_by_game = [parse_results(tb) for tb in tablegames]
    odds_by_game = [parse_odds(tb) for tb in tablegames]
    data_pkg = [lookback_dt, game_part.name, teams_by_game, results_by_game, odds_by_game]
    logging.info(pformat(data_pkg))
    with open(os.path.join(config.RESULTS_DIR, unique_filename), "wb") as f: 
        pickle.dump(data_pkg, f)
    time.sleep(1)
    return data_pkg


def run_current(game_part): 
    logging.info(f"running current, {game_part}")
    soup = get_soup(None, game_part)
    dt = parse_date(soup)
    logging.info(f"date: {dt}")
    tablegames = get_tablegames(None, game_part)
    if tablegames is None: # no games found 
        return
    teams_by_game = [parse_teams(tb) for tb in tablegames]
    results_by_game = [parse_results(tb) for tb in tablegames]
    odds_by_game = [parse_odds(tb) for tb in tablegames]
    data_pkg = [dt, game_part.name, teams_by_game, results_by_game, odds_by_game]
    logging.info(pformat(data_pkg))
    return data_pkg


def test(): 
    for dt_i in [
        datetime.date(2022,12,24), # should be no games on this day? 
        datetime.date(2022,12,25),
        datetime.date(2023,2,16)
    ]: 
        run_and_dump(dt_i, config.GamePart.FULL)
        run_and_dump(dt_i, config.GamePart.HALF1)
        run_and_dump(dt_i, config.GamePart.HALF2)
        run_and_dump(dt_i, config.GamePart.Q1)
        run_and_dump(dt_i, config.GamePart.Q2)
        run_and_dump(dt_i, config.GamePart.Q3)
        run_and_dump(dt_i, config.GamePart.Q4)

    test = pickle.load(open("20221225.dat", "rb"))
    breakpoint()


if __name__ == '__main__':
    dt_range = pd.date_range(
        start=datetime.date(2019,10,3),
        end=datetime.date(2023,2,16)
    ).to_pydatetime().tolist()
    for dt_i in dt_range:
        run_and_dump(dt_i, config.GamePart.FULL)
        run_and_dump(dt_i, config.GamePart.HALF1)
        run_and_dump(dt_i, config.GamePart.HALF2)
        run_and_dump(dt_i, config.GamePart.Q1)
        run_and_dump(dt_i, config.GamePart.Q2)
        run_and_dump(dt_i, config.GamePart.Q3)
        run_and_dump(dt_i, config.GamePart.Q4)