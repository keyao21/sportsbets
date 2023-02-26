from enum import Enum

HIST_DIR = "/home/yaokevin/projects/sportsbets/hist"
DATA_DIR = "/home/yaokevin/projects/sportsbets/data"
SNAPS_DIR = "/home/yaokevin/projects/sportsbets/snaps"
ARCHIVE_DIR = "/home/yaokevin/projects/sportsbets/archive"
BOOKS = ["MG", "DK", "FD", "CS", "PB", "WY", "BR"]


class GamePart(str, Enum): 
    FULL = "full-game"
    HALF1 = "1st-half"
    HALF2 = "2nd-half"
    Q1 = "1st-quarter"
    Q2 = "2nd-quarter"
    Q3 = "3rd-quarter"
    Q4 = "4th-quarter"


game_part_order = {
    "HALF1" : 3,
    "Q1"    : 2,
    "Q2"    : 3,
    "Q3"    : 4,
    "Q4"    : float("inf"),
    "HALF2" : float("inf"),
    "FULL"  : float("inf")
}
