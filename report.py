import os 
import datetime
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pretty_html_table import build_table
import utils
import config
import analysis


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
                    utils.select_cols(
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
    curropps_games_data = utils.filter_snaps_data(today_games_data)
    curr_ts = None if curropps_games_data.empty else curropps_games_data["timestamp"].unique()[0]

    # show time at top of email body
    msg.attach(MIMEText(f"""<html><body>Timestamp:{curr_ts}</body></html>""", 'html'))

    # predefine dataframe row filters
    non_started_filter = utils.get_non_started_filter(curropps_games_data)
    full_game_filter = utils.get_full_game_filter(curropps_games_data)

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
    msg = add_attachment(msg, utils.select_cols(today_games_data), filename=f"today_{today_dt.strftime('%Y%m%d')}.csv")

    # show games with signal
    if incl_hist: 
        filt_games_data = utils.select_cols(utils.filter_games_data(games_data))
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
        NHL(dev) {len(curropps_games_data)} arbs: {len(games_not_started)} not started, {len(games_full)} full, {len(games_other)} other -- ts:{curr_ts}
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
        loaded_data = utils.load_current_data()
        games_data = utils.make_games_data(loaded_data)
        games_data = analysis.add_calc_cols(games_data)
        games_data = analysis.make_arb_data(games_data)
        games_data = analysis.add_live_stats_cols(games_data)
        utils.save_df_snapshot(games_data)
        if args.email: 
            send_email(
                games_data,
                incl_hist=False
            )
        elif args.check_email and (len(games_data[games_data.arb_sig])>0): 
            send_email(
                games_data,
                incl_hist=False
            )

    elif args.hist:
        # historical run with all past games and current/next games. 
        loaded_data = utils.load_hist_data() + utils.load_current_data()
        games_data = utils.make_games_data(loaded_data)
        games_data = analysis.add_calc_cols(games_data)
        games_data = analysis.make_arb_data(games_data)
        games_data = analysis.add_live_stats_cols(games_data)
        if args.email:
            send_email(
                games_data,
                incl_hist=True
            )

    elif args.stats: 
        # run stats
        loaded_data = utils.load_snap_data()
        snaps_data = utils.make_snaps_data(loaded_data)
        snaps_data = utils.filter_snaps_data(snaps_data)
        snaps_data = snaps_data.loc[utils.get_non_started_filter(snaps_data)] # only get non-started games
        fsnapsdata_byarb = analysis.make_data_by_uniq_arb(snaps_data)
        fsnapsdata_byarb_agg_dt = analysis.make_return_stats(fsnapsdata_byarb, group_by=["date"]).sort_values("date")
        fsnapsdata_byarb_agg_gp = analysis.make_return_stats(fsnapsdata_byarb, group_by=["game_part"])
        fsnapsdata_byarb_agg_bk = analysis.make_return_stats(fsnapsdata_byarb, group_by=["bookh","booka","game_part"])
        fsnapsdata_byarb_agg = analysis.make_return_stats(fsnapsdata_byarb, group_by=["date","game_part"])
        if args.email:
            send_stat_email(
                {
                    "By date"           : fsnapsdata_byarb_agg_dt,
                    "By game part"      : fsnapsdata_byarb_agg_gp,
                    "By date, game part": fsnapsdata_byarb_agg,
                    "By bookies"        : fsnapsdata_byarb_agg_bk
                }
            )
        