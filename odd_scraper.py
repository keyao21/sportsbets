import requests
import regex as re
import pickle
import time 
import datetime
from pprint import pprint
from bs4 import BeautifulSoup
import pandas as pd


def get_tablegames(str_lookback_date):
	URL = f"https://www.sportsbookreview.com/betting-odds/nba-basketball/money-line/full-game/?date={str_lookback_date}"
	page = requests.get(URL)
	soup = BeautifulSoup(page.content, "html.parser")

	# still need to get the books to double check maybe...
	# tableheader = soup.find(id="thead-nba")

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
	tableodds
	# should be mgm, dk, fd, caesars, pb, wynn, betrivers, maybe check this
	books = ["MG", "DK", "FD", "CS", "PB", "WY", "BR"]
	odds_by_book = {b:[None, None] for b in books}
	for i,tableodds_i in enumerate(tableodds):
		moneyline = tableodds_i.find_all("span")[-1].text
		odds_by_book[books[i//2]][i%2] = None if moneyline=="-" else int(moneyline)
	return odds_by_book

def run_and_dump(lookback_dt):
	str_lookback_date = lookback_dt.strftime("%Y-%m-%d")
	print("running for ", lookback_dt)
	tablegames = get_tablegames(str_lookback_date)
	if tablegames is None: # no games found 
		return
	teams_by_game = [parse_teams(tb) for tb in tablegames]
	results_by_game = [parse_results(tb) for tb in tablegames]
	odds_by_game = [parse_odds(tb) for tb in tablegames]
	print(teams_by_game)
	print(results_by_game)
	print(odds_by_game)
	data_pkg = [lookback_dt, teams_by_game, results_by_game, odds_by_game]
	with open(f"dataresults/{lookback_dt.strftime('%Y%m%d')}.dat", "wb") as f: 
		pickle.dump(data_pkg, f)
	time.sleep(1)
	return data_pkg

def test(): 
	for dt_i in [
		datetime.date(2022,12,24), # should be no games on this day? 
		datetime.date(2022,12,25),
		datetime.date(2023,2,16)
	]: 
		run_and_dump(dt_i)

	test = pickle.load(open("20221225.dat", "rb"))
	breakpoint()


if __name__ == '__main__':
	dt_range = pd.date_range(start=datetime.date(2018,1,1),end=datetime.date(2023,2,16) ).to_pydatetime().tolist()
	for dt in dt_range: 
		dt_datapkg = run_and_dump(dt)