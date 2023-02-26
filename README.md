# Mr. Bets

## Runbook

### Arb Screen
    - 8am - 7pm, hourly
    - 7pm - 12am, every 10 min 
    - Scrapes for current/next games from odds website
    - Create and save snap dataframe after enrichment
### Stats
    - 7am
    - Load and summarize based on snap dataframes
    - Notes: 
        - filtered out PB arbs
        - duration is floored at 10 min (possible not actually that long)
#### Columns
    - sum_dur: sum of duration of unique arb opportunities
    - sum_returnxdur: sum of product of return and dur
    - wavg_return: duration weighted average return
## Data
    - HIST_DIR: historical data scraped from odds website (only opening data)
    - DATA_DIR: current data saved at every arb screen run (before enrichment)
    - SNAP_DIR: snap data saved at every arb screen run (after enrichment)
## Research 
Do something like 
```python
import sys 
sys.path.insert(0, '..')
from analysis import *

loaded_data = load_hist_data() \
            + load_current_data() \
            + load_snap_data()
games_data = make_games_data(loaded_data)
games_data = add_calc_cols(games_data)
games_data = add_arb_cols(games_data)
```
## Glossary 
    - *_io: implied probability (with vig adjustment)
    - *_rawio: raw implied probabiliy (without vig adjustment)
    - bookh_cost: cost needed for net payouts on each event to be equal 
        - (*_rawio ratio) x booka_cost
    - *_netpayout: cost * (1 - raw_implied_prob)/raw_implied_prob - (cost of opposite leg)
        - opposite legs should be equal
    - return: net_payout / (sum cost)
        - also: 1 / (sum raw_implied_prob) - 1