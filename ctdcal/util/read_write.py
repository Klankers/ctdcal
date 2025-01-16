"""
Module for generic reading and writing for different data formats.

These formats are external to discrete data provided by the science party
(see `parsers` for methods).

Some of this could be handled or modeled off of cchdo.hydro -> CCHDOAccessor
"""


def load_sbe_cnv():
    pass


def write_sbe_cnv():
    pass


def load_exchange_btl():
    #   May want to make hydro a dependency? Useful to have unit translations
    #   available
    pass


def write_exchange_btl():
    pass


def load_exchange_ctd():
    pass


def write_exchange_ctd():
    pass


def load_hy1():
    #   Note that the hy1 bottle files are slightly different versions of the
    #   exchange bottle files ('exchange lite'), where units need to be
    #   referenced
    pass


def write_hy1():
    pass


def load_ct1():
    pass


def load_nc():
    pass


def write_nc():
    pass


def load_mat():
    """
    See scipy.io.loadmat
    """
    pass


def write_mat():
    """
    See scipy.io.savemat
    """
    pass


def write_hex():
    pass


def write_bl():
    """
    SeaBird-style .bl files from another discrete form.
    """
    pass


def write_btl():
    """
    SeaBird-style .btl summary file writer from another discrete form.
    """
    pass
