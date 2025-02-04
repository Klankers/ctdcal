"""
Generic fitting
===============

Module for fitting CTDCAL data.

This module contains the code required for fitting CTDCAL data, using methods
that are applicable to either continuous or discrete data.

Classes
-------

Functions
---------

Examples
--------

"""

import numpy as np

# import pandas as pd


def _prepare_fit_data(df, param, ref_param, zRange=None):
    """
    Remove non-finite data, trim to desired zRange, and remove extreme outliers

    2024-12-02 AJM Note to self that this could be a processors.odf item
    """

    good_data = df[np.isfinite(df[ref_param]) & np.isfinite(df[param])].copy()

    if zRange is not None:
        zMin, zMax = zRange.split(":")
        good_data = good_data[
            (good_data["CTDPRS"] > int(zMin)) & (good_data["CTDPRS"] < int(zMax))
        ]

    good_data["Diff"] = good_data[ref_param] - good_data[param]
    good_data["Flag"] = flagging.outliers(good_data["Diff"], n_sigma2=4)

    df_good = good_data[good_data["Flag"] == 2].copy()
    df_bad = good_data[good_data["Flag"] == 4].copy()

    return df_good, df_bad


def multivariate_fit(y, *args, coef_names=None, const_name="c0"):
    """
    Least-squares fit data using multiple dependent variables. Dependent
    variables must be provided in tuple pairs of (data, order) as positional
    arguments.

    If coef_names are defined, coefficients will be returned as a dict.
    Otherwise, coefficients are return as an array in the order of the
    dependent variables, sorted by decreasing powers.

    Parameters
    ----------
    y : array-like
        Indepedent variable to be fit
    args : tuple
        Pairs of dependent variable data and fit order (i.e., (data, order))
    coef_names : list-like, optional
        Base names for coefficients (i.e., "a" for 2nd order yields
        ["a2", "a1"])
    const_name : str, optional
        Name for constant offset term

    Returns
    -------
    coefs : array-like
        Least-squares fit coefficients in decreasing powers

    Examples
    --------
    Behavior when coef_names is None:

    >>> z = [1, 4, 9]
    >>> x = [1, 3, 5]
    >>> y = [1, 2, 3]
    >>> multivariate_fit(z, (x, 2), (y, 1))
    array([0.25, 0.375, 0.25, 0.125])  # [c1, c2, c3, c4]

    where z = (c1 * x ** 2) + (c2 * x) + (c3 * y) + c4

    Behavior when coef_names is given:

    >>> z = [1, 4, 9]
    >>> x = [1, 3, 5]
    >>> y = [1, 2, 3]
    >>> multivariate_fit(z, (x, 2), (y, 1), coef_names=["a", "b"])
    {"a2": 0.25, "a1": 0.375, "b1": 0.25, "c0": 0.125}

    where z = (a2 * x ** 2) + (a1 * x) + (b1 * y) + c0
    """
    to_dict = True
    if coef_names is None:
        to_dict = False
        coef_names = [""] * len(args)  # needed to prevent zip() error
    elif len(args) != len(coef_names):
        raise ValueError(
            "length of coef_names must match the number of dependent variables"
        )

    # iteratively build fit matrix
    rows, names = [], []
    for arg, coef_root in zip(args, coef_names):
        if type(arg) is not tuple:
            raise TypeError(f"Positional args must be tuples, not {type(arg)}")

        series, order = arg
        for n in np.arange(1, order + 1)[::-1]:
            rows.append(series**n)
            # n is np.int64 so series will cast to np.ndarray
            names.append(f"{coef_root}{n}")

    # add constant offset term
    rows.append(np.ones(len(y)))
    names.append(const_name)

    fit_matrix = np.vstack(rows)
    coefs = np.linalg.lstsq(fit_matrix.T, y, rcond=None)[0]

    return dict(zip(names, coefs)) if to_dict else coefs


def apply_polyfit(y, y_coefs, *args):
    """
    Apply a polynomial correction to series of data. Coefficients should be
    provided in increasing order
    (i.e., a0, a1, a2 for y_fit = y + a2 * y ** 2 + a1 * y + a0)

    For the independent variables (y), coefficients start from the zero-th
    order (i.e., constant offset). For dependent variables (args), coefficients
    start from the first order (i.e., linear term).

    Parameters
    ----------
    y : array-like
        Independent variable data to be corrected
    y_coefs : tuple of float
        Independent variable fit coefficients (i.e., (coef0, ..., coefN))
    args : tuple of (array-like, (float, float, ...))
        Dependent variable data and fit coefficients
        (i.e., (data, (coef1, ..., coefN)))

    Returns
    -------
    fitted_y : array-like
        Independent variable data with polynomial fit correction applied

    Examples
    --------
    Behavior without additional args:

    >>> y = [2, 4, 6]
    >>> apply_polyfit(y, (1, 2, 3))  # y0 = 1; y1 = 2; y2 = 3
    array([ 19.,  61., 127.])

    where fitted_y = y + y0 + (y1 * y) + (y2 * y ** 2)

    Behavior with additional args:

    >>> y = [2, 4, 6]
    >>> x = [1, 2, 3]
    >>> apply_polyfit(y, (1,), (x, (2, 3)))  # y0 = 1; x1 = 2; x2 = 3
    array([ 8., 21., 40.])

    where fitted_y = y + y0 + (x1 * x) + (x2 * x ** 2)
    """
    fitted_y = np.copy(y).astype(float)
    for n, coef in enumerate(y_coefs):
        fitted_y += coef * np.power(y, n)

    for arg in args:
        if type(arg) is not tuple:
            raise TypeError(f"Positional args must be tuples, not {type(arg)}")

        series, coefs = arg
        for n, coef in enumerate(coefs):
            fitted_y += coef * np.power(series, n + 1)

    return fitted_y
