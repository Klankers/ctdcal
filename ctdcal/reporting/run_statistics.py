"""
Module for logging individual CTDCAL runs

Use log_cli to write the log file out.
"""


def run_log_start():
    """
    Stuff like tic, check files to be run, possible time estimates?
    """
    pass


def run_log_end():
    """
    Toc, # of stations run as per the designated list, # of failures/files
    unaccounted for, etc.
    """
    pass


def run_fit_params():
    """
    Record the iterative fitting parameters, potentially in a verbose manner

    col0 : SSSCC or equivalent identifier for station and cast
    col1 : Fit param ([pressure?], temp, cond, oxy, other)
    col2 : Eq. type (SBE, PMEL, polynomial, RINKO, other)
    col3 : Coef type (global, group, cast, other)
    col4 : Dict of fit coefficients (A: -1.5566e-10, B: 3.40556e2,
    gain: 1.0031e0, etc.)
    col5 : Iteration # (if applicable)
    """
    pass
