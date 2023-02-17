import datetime
import requests
from bs4 import BeautifulSoup
import regex as re

lookback_date = datetime.date(2023,2,16)
str_lookback_date = lookback_date.strftime("%Y-%m-%d")
URL = f"https://www.sportsbookreview.com/betting-odds/nba-basketball/money-line/full-game/?date={str_lookback_date}"
page = requests.get(URL)
soup = BeautifulSoup(page.content, "html.parser")

# still need to get the books to double check maybe...
# tableheader = soup.find(id="thead-nba")

# get data table
tablebody = soup.find(id="tbody-nba")
tablegames_regex = re.compile('GameRows_eventMarketGridContainer__GuplK GameRows_neverWrap__gnQNO GameRows_compact__ZqqNS.*')
tablegames = tablebody.find_all("div", {"class" : tablegames_regex})

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
		odds_by_book[books[i//2]][i%2] = int(tableodds_i.find_all("span")[-1].text)
	return odds_by_book


teams_by_game = [parse_teams(tb) for tb in tablegames]
odds_by_game = [parse_odds(tb) for tb in tablegames]
print(teams_by_game)
print(odds_by_game)

breakpoint()