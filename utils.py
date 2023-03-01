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
        [["arb_sig", "statustxt", "game_part", "timestamp", "date", "home", "away"]
         + ["h_rawio", "a_rawio", "return"]
         + [f"book{l}{calcstr}" for calcstr in ["", "_cost", "_netpayout"] for l in ["h","a"]]
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


def add_attachment(msg, games_data, filename): 
    archive_loc = os.path.join(config.ARCHIVE_DIR, filename)
    games_data.to_csv(archive_loc)
    with open(archive_loc) as fp: 
        attachment = MIMEText(fp.read(), _subtype="text")
    attachment.add_header("Content-Disposition", "attachment", filename=archive_loc)
    msg.attach(attachment)
    os.remove(archive_loc)
    return msg


def send_email(games_data, incl_hist):
    recipients = ["kyao747@gmail.com", "sivaduil@gmail.com"] 
    emaillist = [elem.strip().split(',') for elem in recipients]
    msg = MIMEMultipart()
    msg['From'] = 'helloitsmrbets@gmail.com'
    today_dt = datetime.date.today()
    today_dt_time = datetime.datetime(year=today_dt.year, month=today_dt.month, day=today_dt.day)
    # show current opps 
    curropps_games_data = games_data\
        [games_data.date>=today_dt_time]\
        [games_data.arb_sig]\
        [games_data.status != 3]\
        [(games_data.game_part.map(config.game_part_order) > games_data.period_adj)]
        # [~games_data.period.isnull() & 

    html0 = f"""\
            <html>
              <body>
                {build_table(
                    select_cols(
                        curropps_games_data
                        .sort_values(by=["return", "arb_sig", "date", "home", "away", "game_part"],ascending=False)
                    ),
                    "blue_light"
                    ) if len(curropps_games_data) > 0 else "No current arbs"
                }
              </body>
            </html>
            """
    part0 = MIMEText(html0, 'html')
    msg.attach(part0)

    # show next/today's games 
    today_games_data = games_data[games_data.date>=today_dt_time]
    today_games_data_select = select_cols(
        today_games_data
        .sort_values(by=["status", "return", "arb_sig", "date", "home", "away", "game_part"],ascending=False)
    )
    html1 = f"""\
            <html>
              <head>Next/current games</head>
              <body>
                {build_table(
                    today_games_data_select,
                    "blue_light"
                    ) if len(today_games_data_select) > 0 else "None"
                }
              </body>
            </html>
            """
    part1 = MIMEText(html1, 'html')
    msg.attach(part1)
    msg = add_attachment(msg, today_games_data_select, filename=f"today_{today_dt.strftime('%Y%m%d')}.csv")

    # show games with signal
    filt_games_data = select_cols(filter_games_data(games_data))
    if incl_hist: 
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
        msg = add_attachment(msg, filt_games_data, filename=f"hist_{today_dt.strftime('%Y%m%d')}.csv")

    # write subject 
    msg['Subject'] = f"{len(curropps_games_data)} arbs right now"

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
