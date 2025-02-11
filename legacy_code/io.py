"""
A module for handling ODF input-output files related to CTDCAL.
"""

import logging
from io import BufferedIOBase, BytesIO, StringIO
from pathlib import Path
from typing import Union
from zipfile import ZipFile, is_zipfile
from zipimport import ZipImportError

import pandas as pd
import requests

log = logging.getLogger(__name__)


def load_cnv(cnv_file: Union[str, Path]) -> pd.DataFrame:
    """
    Load Sea-Bird converted (.cnv) cast file into DataFrame
    """
    with open(cnv_file) as f:
        file = f.readlines()

    # parse column names
    info = dict()
    cols = []
    for idx, line in enumerate(file):
        # get variable info
        if line.strip("# \n").startswith(("nquan", "nvalues", "units", "bad_flag")):
            k, v = line.strip("# \n").split("=")
            info[k.strip()] = v.strip()

        # get column names
        elif line.strip("# ").startswith("name"):
            # expected format is:   # name 0 = col_name: long_description
            cols.append(line.split(":")[0].split("=")[-1].strip())

        # last row before data begins
        elif line.startswith("*END*"):
            data_index = idx + 1
            break

        # anything else is a comment line
        else:
            continue  # pragma: no cover

    # read data
    return pd.read_csv(
        cnv_file,
        skiprows=range(0, data_index),
        # delim_whitespace=True,
        sep=r"\s+",
        names=cols,
        engine="python",
        skipinitialspace=True,
        na_values=info["bad_flag"],
    )


def load_exchange_btl(btl_file: Union[str, Path]) -> pd.DataFrame:
    """
    Load WHP-exchange bottle file (_hy1.csv) into DataFrame. File can be on local
    file system or downloaded from an appropriate cchdo.ucsd.edu link
    (e.g., https://cchdo.ucsd.edu/data/19436/325020210316_hy1.csv)

    Adapted from cchdo.hydro package.

    Parameters
    ----------
    btl_file : str or Path
        Name or URL of file to be loaded

    Returns
    -------
    df : DataFrame
        Loaded bottle file
    """
    # read from url
    if isinstance(btl_file, (str, Path)) and str(btl_file).startswith("http"):
        log.info(f"Loading bottle file {Path(btl_file).name} from http link")
        file = requests.get(btl_file).text.splitlines(keepends=True)

    # read from file
    elif isinstance(btl_file, (str, Path)):
        log.info(f"Loading bottle file {Path(btl_file).name} from local file")
        with open(btl_file) as f:
            file = f.readlines()

    # find index of units row
    for idx, line in enumerate(file):
        # skip comment lines (which may reference EXPOCODE and break membership test)
        if line.strip().startswith("#"):
            continue

        # find index of units row
        if "EXPOCODE" in line:
            units = idx + 1  # units row immediately follows column names
            break

    return pd.read_csv(
        StringIO("".join(file)),
        skiprows=[0, units],
        skipfooter=1,
        engine="python",
        comment="#",
        skipinitialspace=True,
    )


def load_exchange_ctd(
    ctd_file: Union[str, Path, BufferedIOBase],
    n_files=None,
    recursed=False,
) -> pd.DataFrame:
    """
    Load WHP-exchange CTD file(s) (_ct1.csv) into DataFrame. File(s) can be on local
    file system or downloaded from an appropriate cchdo.ucsd.edu link
    (e.g., https://cchdo.ucsd.edu/data/19434/325020210316_ct1.zip)

    Adapted from cchdo.hydro package.

    Parameters
    ----------
    ctd_file : str or Path
        Name or URL of file to be loaded

    n_files : int, optional
        Number of files to load from .zip archive

    Returns
    -------
    header : dict or list of dict
        File metadata from header(s) (e.g., EXPOCODE, STNNBR, CASTNO)
    df : DataFrame or list of DataFrame
        Loaded CTD file(s)
    """
    # read from url (.zip)
    if isinstance(ctd_file, (str, Path)) and str(ctd_file).startswith("http"):
        log.info(f"Loading CTD file {Path(ctd_file).name} from http link")
        data_raw = BytesIO(requests.get(ctd_file).content)

    # read from file
    elif isinstance(ctd_file, (str, Path)):
        log.info(f"Loading CTD file {Path(ctd_file).name} from local file")
        with open(ctd_file, "rb") as f:
            data_raw = BytesIO(f.read())

    # read from open file
    elif isinstance(ctd_file, BufferedIOBase):
        log.info("Loading open file object")
        data_raw = BytesIO(ctd_file.read())

    # .zip special behavior
    if is_zipfile(data_raw):
        log.info("Loading CTD files from .zip")

        if recursed is True:
            raise ZipImportError("Recursive .zip files encountered... exiting")

        data_raw.seek(0)  # is_zipfile moves cursor to EOF, reset to start
        zip_contents = []
        with ZipFile(data_raw) as zf:
            for zipinfo in zf.infolist():
                zip_contents.append(BytesIO(zf.read(zipinfo)))

        # list comprehension is same as using functools.partial, just different syntax
        return zip(
            *[load_exchange_ctd(zc, recursed=True) for zc in zip_contents[:n_files]]
        )

    else:
        data_raw.seek(0)  # is_zipfile moves cursor to EOF, reset to start
        file = data_raw.read().decode("utf8").splitlines(keepends=True)

    # process metadata
    for idx, line in enumerate(file):
        # skip comment lines (which may reference CTDPRS and break membership test)
        if line.strip().startswith("#"):
            continue

        # find header info
        if line.startswith("NUMBER_HEADERS"):
            header_ind = idx

        # find index of units row
        if "CTDPRS" in line:
            columns = idx
            units = idx + 1  # units row immediately follows column names
            break

    # break down header rows
    header = {}
    for line in file[header_ind:columns]:
        k, v = line.strip("\n").split("=")
        header[k.strip()] = v.strip()

    return header, pd.read_csv(
        StringIO("".join(file)),
        skiprows=list(range(0, columns)) + [units],  # skip up to column names (+ units)
        skipfooter=1,
        engine="python",
        comment="#",
        skipinitialspace=True,
    )
