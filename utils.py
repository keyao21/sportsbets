import os 
import datetime
from pretty_html_table import build_table
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import config


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


def select_cols(games_data): 
    return games_data\
        [["arb_sig", "statustxt", "game_part", "home", "away"]
         + [f"book{l}{calcstr}" for calcstr in ["", "_cost"] for l in ["h","a"]]
         + ["return", "h_rawio", "a_rawio"]
         + [f"book{l}_netpayout" for l in ["h","a"]]
         #+ [b+l for l in ["h","a"] for b in config.BOOKS]
        ]


def filter_games_data(games_data): 
    # filter dataframe in email body
    games_data = games_data\
        .loc[~games_data.arb_sig.isnull() & games_data.arb_sig]\
        .loc[games_data.date > datetime.datetime.today()-datetime.timedelta(days=30)]\
        .sort_values("date",ascending=False)
    return games_data


def filter_snaps_data(snaps_data): 
    # get only usable return periods
    # filter out unusable bookies like PB.
    games_data = snaps_data
    fsnaps_data = games_data\
        .loc[~games_data.arb_sig.isnull() & games_data.arb_sig]\
        .loc[(games_data.game_part.map(config.game_part_order) > games_data.period_adj)]\
        .loc[games_data.status != 3]\
        .loc[~(((games_data.bookh.str.match("PB")) | (games_data.booka.str.match("PB"))) & ~games_data.game_part.str.match("FULL"))]\
        .loc[
        # crazy stuff for excluding DK interquarter stuff when you cant bet.
        # if the game has started, DK is a book, and the current quarter/half is not in the betting quarter half
         ~(
           ~(games_data.period_adj==0 | games_data.period_adj.isnull()) 
           & ((games_data.bookh=="DK") | (games_data.booka=="DK")) 
           & (games_data.game_part.map(config.game_part_start) > games_data.period_adj) 
          )
        ]
    return fsnaps_data


def add_attachment(msg, games_data, filename): 
    archive_loc = os.path.join(config.ARCHIVE_DIR, filename)
    games_data.to_csv(archive_loc)
    with open(archive_loc) as fp: 
        attachment = MIMEText(fp.read(), _subtype="text")
    attachment.add_header("Content-Disposition", "attachment", filename=archive_loc)
    msg.attach(attachment)
    os.remove(archive_loc)
    return msg


def create_text_part(header, table, sort_cols, ascending=False): 
    html = f"""\
            <html>
              <head>
                {header}
              </head>
              <body>
                {build_table(
                    select_cols(
                        table
                        .sort_values(by=sort_cols,ascending=ascending)
                    ),
                    "blue_light"
                    ) if len(table) > 0 else "No current arbs"
                }
              </body>
            </html>
            """
    return MIMEText(html, 'html')


def send_email(games_data, incl_hist):
    recipients = ["kyao747@gmail.com", "sivaduil@gmail.com"] 
    emaillist = [elem.strip().split(',') for elem in recipients]
    msg = MIMEMultipart()
    msg['From'] = 'helloitsmrbets@gmail.com'
    today_dt = datetime.date.today()
    today_dt_time = datetime.datetime(year=today_dt.year, month=today_dt.month, day=today_dt.day)

    # show current opps 
    today_games_data = games_data.loc[games_data.date>=today_dt_time]
    curropps_games_data = filter_snaps_data(today_games_data)
    curr_ts = None if curropps_games_data.empty else curropps_games_data["timestamp"].unique()[0]

    # show time at top of email body
    msg.attach(MIMEText(f"""<html><body>Timestamp:{curr_ts}</body></html>""", 'html'))

    # predefine dataframe row filters
    non_started_filter = (curropps_games_data.status.isnull() | curropps_games_data.status.isin([0,1]))
    full_game_filter = (curropps_games_data.game_part=="FULL")

    # filtered games 
    games_not_started = curropps_games_data.loc[non_started_filter]
    games_full = curropps_games_data\
        .loc[~non_started_filter]\
        .loc[full_game_filter]
    games_other = curropps_games_data\
        .loc[~non_started_filter]\
        .loc[~full_game_filter]

    # show not started game bets first
    msg.attach(
        create_text_part(
            header="Games not started",
            table=games_not_started,
            sort_cols=["return", "arb_sig", "date", "home", "away", "game_part"],
            ascending=False
        )
    )
    # show full game bets
    msg.attach(
        create_text_part(
            header="Full games",
            table=games_full,
            sort_cols=["return", "arb_sig", "date", "home", "away", "game_part"],
            ascending=False
        )
    )
    # show every other bet
    msg.attach(
        create_text_part(
            header="Non-Full games",
            table=games_other,
            sort_cols=["period_adj"],
            ascending=False
        )
    )
    # show next/upcoming bets 
    msg.attach(
        create_text_part(
            header="All games",
            table=today_games_data,
            sort_cols=["status", "return", "arb_sig", "date", "home", "away", "game_part"],
            ascending=False
        )
    )
    msg = add_attachment(msg, select_cols(today_games_data), filename=f"today_{today_dt.strftime('%Y%m%d')}.csv")

    # show games with signal
    if incl_hist: 
        filt_games_data = select_cols(filter_games_data(games_data))
        msg.attach(
            create_text_part(
                header="All total prob inconsistencies over past 30 days",
                table=filt_games_data,
                sort_cols=None
            )
        )
        msg = add_attachment(msg, filt_games_data, filename=f"hist_{today_dt.strftime('%Y%m%d')}.csv")

    end_html = MIMEText("<html><head>End of email goodbye</html></head>", 'html')
    msg.attach(end_html)

    # write subject 
    msg['Subject'] = f"""\
        {len(curropps_games_data)} arbs: {len(games_not_started)} not started, {len(games_full)} full, {len(games_other)} other -- ts:{curr_ts}
        """

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


def send_stat_email(stats_data):
    recipients = ["kyao747@gmail.com","sivaduil@gmail.com"] 
    emaillist = [elem.strip().split(',') for elem in recipients]
    msg = MIMEMultipart()
    msg['From'] = 'helloitsmrbets@gmail.com'
    today_dt = datetime.date.today()
    today_dt_time = datetime.datetime(year=today_dt.year, month=today_dt.month, day=today_dt.day)
    
    def add_table(msg, name, table): 
        # show next/today's games 
        html1 = f"""\
                <html>
                  <head>{name}</head>
                  <body>
                    {build_table(
                        table.reset_index(),
                        "blue_light"
                        ) if len(table) > 0 else "None"
                    }
                  </body>
                </html>
                """
        part1 = MIMEText(html1, 'html')
        msg.attach(part1)
        msg = add_attachment(msg, table, filename=f"{name}stats_{today_dt.strftime('%Y%m%d')}.csv")
        return msg

    for name,table in stats_data.items(): 
        msg = add_table(msg, name, table)

    # write subject 
    msg['Subject'] = f"whats up dummy here are ur stats"

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
