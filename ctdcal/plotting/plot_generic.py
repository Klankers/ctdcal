"""
Module for generic 2D plots related using CTD continuous and discrete data.
"""

import os

import matplotlib.pyplot as plt


def plot_engineering_runner(
    data, var_name="engineering", output_path="data/plots", format="svg"
):
    fname, _ = os.path.splitext(data.attrs["hex_filename"])
    fname = fname + "." + format
    os.makedirs(output_path, exist_ok=True)
    # Creates the directory if it doesn't exist
    output_path = os.path.join(output_path, fname)

    engineering_data = data[var_name]

    #   Get the number of columns (should be 13)
    num_columns = engineering_data.shape[1]

    #   Max of about 13 plots
    fig, axes = plt.subplots(3, 5, figsize=(15, 10))
    axes = axes.flatten()  # Flatten to easily access each subplot

    # TODO:
    # Use data.attrs["f_s"] to get number of plots that need freq on Y axis

    for i in range(num_columns):
        ax = axes[i]
        ax.scatter(data["scan"], engineering_data[:, i], s=1)  # Scatter plot
        ax.set_title(f"Channel {i + 1}")
        ax.set_xlabel("Scan Number")
        ax.set_ylabel("Voltage (V)")  # Assuming voltage data, adjust as needed
        ax.grid(True)

    # Remove any unused subplots
    for i in range(num_columns, len(axes)):
        fig.delaxes(axes[i])

    plt.tight_layout()
    plt.savefig(output_path, format=format)


def plot_profile(plot_params, cast=None):
    pass


def plot_cascade(plot_param, casts=None):
    """
    An overlay version of plot_profile for multiple casts
    """
    pass


def plot_param_vs_param():
    pass


def plot_residual_vs_pressure():
    pass


def plot_residual_vs_station():
    pass


def plot_timeline():
    pass


def plot_section():
    """
    Topography-style plot for visualizing sections or 3D comparisons
    """
    #   Bathymetry on-off
    #   Gridding options
    pass


def plot_geographic():
    #   For things like station locations, event logger info
    #   (like sensor swaps), start and end locations, etc.
    pass


def merge_plots():
    """
    For merging plots into a single figure.

    Loads multiple images and assembles them into a mosaic. Good for sections,
    casts, and geographics at the same time.
    """
    pass
