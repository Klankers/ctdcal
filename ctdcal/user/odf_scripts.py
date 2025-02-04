"""
Scripts and wrappers for normal ODF subroutines.

Below is a long, arduous list of what needs to happen during a typical ODF
run of CTDCAL:

--Pre-run checks--
* Init overall logger (reporting)
* Check files for changes (common/util)
--The run--
* Init run logger (reporting)
* Load cruise_config.yaml, CTD_package_config.yaml (.XMLCON tracker), cast_config.yaml (parsers)
* SSSCC assembly to cumulative .NC file:
    * Parse .HEX, .XMLCON, .BL (parsers)
    * Check .XMLCON for changes (common/util)
        * If so, add to CTD_package_config (common/util)
        * Build RINKO calib info, if it doesn't exist -> Just a .CSV or something of the factory coeffs, merge with .XMLCON (read_write)
    * Check .HEX header for alignment information (processors) - advance if necessary
    * Convert to engineering units (freq., voltages) (processors) - keep original columns
    * Convert to science units (processors) - keep original columns
        * Hysteresis correction in SBE43, RINKO - keep original columns (processors)
        * Plot SBE43, RINKO with/without hysteresis correction (plotting)
    --Discrete file assembly--
    * Load the reft data (parsers)
    * Load the autosal data (parsers)
        * Extract standards
    * Load the Winkler data (parsers)
        * Extract standards
        * Parse the .VOL file and merge
    --Manual flag assembly--
    * Load any manual bottle, discrete, CTD, or event flags (parsers/read_write)
        * Bottle - all discrete samples for this are bad and should not be referenced (flag all refs 4)
        * Discrete - for specific analysis, there was an issue that they didn't capture (flag this ref 4)
        * CTD - there was a section of the CTD cast where data was bad for a particular scan/depth/time range (flag CTD data 3)
        * Event - there was some other event that happened/misc. (custom procedure)
--Data conversion and sequestration--
* Assemble master "reference" data (util)
* Convert new .HEX to .NC, save intermediate file (processors)
    * Consists of entire dataset prior to any manipulations - hexadecimal, engineering units, science units
    * Assembled .BL -> What we know about:
    * The 3 core config files
    * Assembled discrete "reference" data: REFT, SALT, OXY, with two sets of standards
* Do R2R style checks (reporting), generate stoplights (reporting)
--Data manipulation--
* For each cast in cumulative file:
    --Continuous--
    * Remove ondeck -> cut out to "ondeck.nc" file (processors)
        * Get ondeck pre-post averages (including looking for bad casts)
        * Plot ondeck times + 500 points of buffer into cast (plotting)
    * Remove soak -> cut out to "soaks.nc" file (processors)
        * Plot depth vs scan number to the cutoff point + 500 points (plotting)
    * Get estimate of bottom depth from altimeter response (processors)
    * Get bottom lat/lon/datetime (processors)
    * Do preliminary data cleanup (processors.ctd)
        * Despike (processors) - interpolate over
            * If any spikes, plot them before and after
        * Roll filter to remove loops - overwrite with latest
            * Plot before and after, overlayed
        * (Have support for smoothing filter, but don't do at this step, * Run smoothing filter, flag bad points as 3)
        * Grubb's Test (https://en.wikipedia.org/wiki/Grubbs%27s_test) for outlier flagging (flagging)
            * Plot outliers (plotting -> histogram)
        * Slope Test to look for outliers (look for sharp changes in slope "disjointed-ness") but don't flag them, just plot it up (flagging)
            * Plot steep slopes (plotting -> zoomed property-property)
        * Q-Test (https://en.wikipedia.org/wiki/Dixon%27s_Q_test?
    * Apply pressure offset (fitting.ctd)
    * Split up/downcasts (processors)
    * Plot unfit up vs downcasts with residuals (plotting)
    * Assign CTD flags where appropriate before fitting (flagging)
    * (Optional) Derive auxiliary units - xmiss in %, fluor, etc. (processors)
    --Discrete from CTD--
    * Extract bottle upcast mean values and flags from CTD upcasts (processors)
    * Extract prefit downcast bottle mean values and flags (processors)
    * (Optional: Compare extracts to .BTL) (processors)
    * Check .BL vs mean values for problems like missing bottles and relabeling, assign to extracts (processors)
    * Assign manual CTD discrete flags where appropriate before fitting (flagging)
    * Save extracted bottle values as .nc for final comparison (read_write)
    --Handle references--
    * To each, assign our manual flags where appropriate when done (flagging)
    * Process discrete REFT
        * Value checks & flags (flagging)
        * Save statistics (reporting)
    * Process discrete autosal SALT
        * Value checks & flags (flagging)
        * Standard offset and gain calculation and application (processors)
        * Derive conductivity (processors)
        * Save statistics (reporting)
    * Process discrete Winkler OXY
        * Value checks & flags (flagging)
        * Flask volume corrections (processors)
        * Rho_T calculation (processors)
        * Calculate mL/L (processors)
    --Fitting--
    * Calibrate CTD temperature
        * Global - group polyfit (fitting)
        * Save global, group, SSSCC fit coeffs and offsets (uncal'd downcast bottle values vs current at each iteration) (reporting)
        * Plot primary and secondary CTD temp. trace residuals (plotting)
    * Calibrate CTD conductivity
        * Global - group polyfit (fitting)
        * Save global, group, SSSCC fit coeffs and offsets (uncal'd downcast bottle values vs current at each iteration) (reporting)
        * Plot primary and secondary CTD cond. trace residuals (plotting)
    * Calculations (processors)
        * Practical salinity
        * Absolute salinity
        * Conservative temperature
        * Sigma-theta (density) from SA and CT
        * Oxygen solubility
    * Calibrate CTD oxygen
        * Density matching for 43 voltage (processors)
        * Define weights (fitting)
        * Station by station fitting, PMEL equation (fitting)
        * Convert units to umol/kg (processors)
    * Calibrate CTD RINKO
        * (Optional) Density matching for RINKOV
        * (Optional: Global - group - station)
        * Cast-by-cast iterations of weighted Uchida scipy.optimize.minimize() (fitting)
        * Convert units to umol/kg (processors)
    * Plot SBE43 vs RINKO, should get a straight line (plotting)
    --Post-calib plotting--
    (all plotting)
    * Continuous C, T, O vs press. overlay (colored by SSSCC)
    * Deepest continuous C, T, O vs press. overlay (colored by SSSCC)
    * Pre-post fit CTD comparison (load ctd_prefit.nc)
    * Pre-post fit bottle comparison (load bottle_prefit.nc)
    * C, T, O vs press. and section distance section (colored by value)
    * Residual plots for bottle data like normal
    * Station geographic plot
    * Timeline plot
    * Discrete data bar charts (bins for flags, values ran, etc.) (inc. nuts)
    * Discrete data vs press. scatter (inc. nuts)
    * Merges:
        * Geographic + timeline combo
        For each of C, T, O:
        * Geographic + timeline combo, pre-post CTD, pre-post bottle, bottle residual, section
--Exports and cleanup--
* Bin data (processors)
* Backfill surface w/ flags (processors)
* Create .hy1 file (for ODF internal purposes on the boat) w/ user-defined columns (read_write)
* Write out final .nc (read_write)
* Use hydro for exchange format (util/read_write)
* Conclude run logger (reporting)
* Write run report from run log and .nc files (reporting)
* Conclude overall logger (reporting)
* Write overall performance report from run log and .nc files (reporting)

In the future, this can all be made into a YAML file, where every routine can be easily assembled and referenced for easy reordering
without the user ever needing to open a text editor.
"""

#   Temporary: Add odfsbe to path until it is available through pypi
import sys
import xarray as xr
from pathlib import Path

sys.path.append("/Users/ajmau/other_code/odfsbe/odf/sbe")
import __init__ as sbereader
import accessors as xmlcon_junk

from ctdcal.processors import sbs

# from sbereader import odf_wrapper

#   hex_path = Path("00102.hex")


def run_wrapper() -> xr.Dataset:
    #   Load the data from the odfsbe reader as a xarray.Dataset
    data = sbereader.odf_wrapper("00102.hex")
    xmlcon_box, xmlcon_sensors = xmlcon_junk.parse_xmlcon(data.xmlcon)
    data = sbs.convert_science(data, xmlcon_sensors)

    return data
