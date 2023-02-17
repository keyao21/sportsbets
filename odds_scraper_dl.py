import requests
import regex as re
import pickle
import time
import datetime
from pprint import pprint
from bs4 import BeautifulSoup
import pandas as pd
import logging
import tempfile

# We are assuming this order - maybe would be nice to verify it in the header?
books = ["MG", "DK", "FD", "CS", "PB", "WY", "BR"]

results_dir = "dataresults_dl"

def get_tablegames(date):
    str_lookback_date = date.strftime("%Y-%m-%d")
    URL = f"https://www.sportsbookreview.com/betting-odds/nba-basketball/money-line/full-game/?date={str_lookback_date}"
    logging.info(f"Fetching page {URL}")
    page = requests.get(URL)
    soup = BeautifulSoup(page.content, "html.parser")

    # get data table
    tablebody = soup.find(id="tbody-nba")
    if tablebody:
        tablegames_regex = re.compile(
            'GameRows_eventMarketGridContainer__GuplK GameRows_neverWrap__gnQNO GameRows_compact__ZqqNS.*')
        tablegames = tablebody.find_all("div", {"class": tablegames_regex})
        return tablegames
    return None


def parse_results(date, game_table):
    teams_regex = re.compile('GameRows_participants__Fdd1S.*')
    teams_html = game_table.find_all("div", {"class": teams_regex})

    teams = [
        t.find("span", class_="GameRows_participantBox__0WCRz").text
        for t in teams_html
    ]
    score = [
        int(t.find("div", class_="GameRows_scores__YkN24").text)
        for t in teams_html
    ]

    odds_regex = re.compile("OddsCells_pointer___xLMm OddsCells_margin__7d2oM.*")
    tableodds = game_table.find_all("span", {"class": odds_regex})

    odds_by_book = {b: [None, None] for b in books}
    for i, tableodds_i in enumerate(tableodds):
        try:
            moneyline = int(tableodds_i.find_all("span")[-1].text)
        except ValueError:
            moneyline = None

        odds_by_book[books[i // 2]][i % 2] = moneyline

    return {
        "date": date,
        "teams": teams,
        "score": score,
        "odds_by_book": odds_by_book
    }


def get_results_for_date(date):
    logging.info(f"Getting results for {date}")
    tablegames = get_tablegames(date)
    if tablegames is None:  # no games found
        logging.warning(f"No results found for {date}")
        return None

    return [parse_results(date, tb) for tb in tablegames]


def dump_results_for_dates(date_range, filename="results", delay=1):
    results = []
    for date in date_range:
        try:
            results.append(get_results_for_date(date))
        except Exception as e:
            logging.exception(f"Encountered error parsing date {date}", exc_info=e)

        # Avoid querying the website too much
        time.sleep(delay)

    with open(f"{results_dir}/{filename}.dat", "xb") as f:
        pickle.dump(results, f)


def test_get_results():
    pprint(get_results_for_date(datetime.date(2022, 12, 24)))
    pprint(get_results_for_date(datetime.date(2022, 12, 25)))
    pprint(get_results_for_date(datetime.date(2023, 2, 16)))


def load(filename = "results"):
    results = pickle.load(open(f"{results_dir}/results.dat", "rb"))
    pprint(results)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # start_date = datetime.date(2019, 10, 22)
    start_date = datetime.date(2023, 2, 14)
    end_date = datetime.date(2023, 2, 16)
    date_range = pd.date_range(start=start_date, end=end_date).to_pydatetime().tolist()

    dump_results_for_dates(date_range)
