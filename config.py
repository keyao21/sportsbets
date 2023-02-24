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

