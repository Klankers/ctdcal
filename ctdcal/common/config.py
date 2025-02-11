"""
Config
======

A module for handling user and autogenerated configuration YAML files.

This module handles the .yml or YAML files required for a run.
These YAML files include the following:
* Cruise specifics, required for reporting and data products (chief sci.,
oxygen units, etc.)
* CTD configuration, as defined by .XMLCON, and fitting parameters
* Cast-by-cast instructions as defined by the user (full casts, LADCP only
where no bottles are fired, etc.)
* (If not predefined) User-defined routines for CTD processing (such as
skipping SBE35 fitting, or applying alternative filters)

Classes
-------

Functions
---------

Notes
-----

Examples
--------

"""


def build_cruise():
    """
    Builds the config file associated with the cruise for reporting and data
    product purposes.
    """
    pass


def build_sensor_package():
    """
    Builds the config for a specific CTD based on the .XMLCON.

    It checks the .XMLCON files for consecutive casts and looks for sensor
    swaps, mapping .XMLCONs to particular casts for assembling fit groupings
    automatically.
    """
    pass


def build_cast_by_cast():
    """
    Builds the cast-by-cast instruction configuration file for specific CTDCAL
    instructions regarding a particular cast.
    """
    pass


def build_user_routine():
    """
    Assembles a list of potential commands and combines them into a template
    for CTDCAL processing, as defined by user selection.

    For example:
    * Parse the SBE9 first
    * Align the CTD plumbing
    * Despike
    * Roll filter
    * Assign quality control flags to CTD params
    * Fit oxygen data ONLY
    * Bin average
    * Write as .NC
    """
    pass


def edit_config(config_path):
    """
    Loads an existing configuration file for the user to edit it.

    Works using YAML levels, where each level is able to be added to, removed,
    or have a child built therin.

    Example:
    I'm working with the .XMLCON "sensor_package.yaml" and I notice there is a
    "RINKO" sensor with no info. I have the calib sheet, but no digital media
    for it, so I hit "edit_config" to adjust the "RINKO" field and add
    calibration coefficients that can be referenced later.
    * For each sensor, I should be able to add a field and call it whatever I
    want
    * For each field inside of that, I should be able to populate a dictionary
    like how the SBE.XMLCON stores its calib. coeffs

    Example 2:
    I'm coming close to the end of a cruise and I finally got the contact info
    for the chief sci. I've been processing data the whole time, working
    on the cruise report, and now I want to add their info to the report.
    I hit "edit_config" for the "cruise.yaml" and adjust the blank entry so
    that CTDCAL can pull from it in the future.

    Example 3:
    I'm processing a particular cast and I want to try a different fitting
    method. I can hit "edit_config" for the "cast_by_cast.yaml" and adjust the
    entry for that specific cast to be a different routine defined elsewhere
    which CTDCAL can use for a rerun.
    """
    pass


def add_cast(cast_config_path):
    """
    Loads the cast.yaml file and gets user cast instructions how how this cast
    should be handled in CTDCAL.
    """
    pass
