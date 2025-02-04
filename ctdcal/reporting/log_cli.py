"""
Logging and CLI
===============

Module for CTDCAL's logging and command line printing.

This module contains all the code required for logging CTDCAL operations and
printing specific lines to the console.

Classes
-------

Functions
---------

Examples
--------

"""


def init_logger():
    pass


def print_progress_bar(
    iteration,
    total,
    prefix="",
    suffix="",
    decimals=1,
    length=100,
    fill="█",
    printEnd="\r",
):
    """
    A progress bar, helpful for implementing into loops or highlighting
    progression through processing.

    https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters/13685020
    credit: u/Greenstick
    Call in a loop to create terminal progress bar

    Parameters
    ----------
    iteration : int
        the current iteration
    total : int
        the total number of iterations
    prefix : str, optional
        line prefix
    suffix : str, optional
        line suffix
    decimals : int, optional
        positive number of decimals in percent complete
    length : int, optional
        character length of bar
    fill : str, optional
        bar fill character
    printEnd : str, optional
        end character (e.g. "\r", "\r\n")

    Returns
    -------

    Notes
    -----

    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + "-" * (length - filledLength)
    print(
        f"\r{prefix} |{bar}| {percent}% {suffix}", end=printEnd
    )  # Potential to add to log
    # Print New Line on Complete
    if iteration == total:
        print()


def write_log_txt():
    pass
