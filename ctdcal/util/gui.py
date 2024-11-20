"""
GUI
===

Module for CTDCAL's graphical user interface.

This module handles all of the associated graphical user interface steps, allowing users to navigate or perform basic CTDCAL functions without needing to type in code. Associated definitions from brainstorming in late 2024.

Classes
-------

Functions
---------

Examples
--------

>>> import gui
>>> gui.start_window()

"""
### Module for the graphical user interface.

#   Associated definitions from brainstorming 

def start_window():
    """
    The main window, with a bunch of buttons (below)

    Long description

    Parameters
    ----------
    something : type
        description

    Returns
    -------

    Raises
    ------

    Notes
    -----

    Examples
    --------

    """
    pass

def configure_cruise():
    """
    Initialize the cruise file directories, processing routines, etc.
    """
    pass

def add_casts():
    """
    Add a cast, with specified run parameters or instructions if necessary
    """
    pass

def edit_configs():
    """
    Adjust the configuration or run parameters for existing casts
    """
    pass

def view_plots():
    """
    Visualize the different plots CTDCAL can make without outputting anything. Basically, you should not need to open ODV.
    """
    pass

def view_reports():
    """
    Visualize or generate reports.
    """
    pass

def qaqc():
    """
    Tools for quality control, such as manual flagging, **fit** flags, or continuous section flags.
    
    Wrap our QC tool into this, the SBE43 coef tester, etc.

    Whatever tools would be helpful for analysts
    """
    pass

def convert_files():
    """
    Taking products and converting formats or doing quick stuff.
    """
    pass

def cleanup_visualizer():
    """
    A way to visualize what filters, despikes, would do to the data files. Possibly lump into qaqc.
    """
    pass

def event_logger():
    """
    An event logger, for reporting purposes.
    """
    pass

def gui_settings():
    """
    Popup settings for this window.
    """
    pass

def go():
    """
    The GO button, showing a pop-up progress bar
    """
    pass