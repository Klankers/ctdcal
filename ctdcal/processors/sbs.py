"""
Module of data manipulation routines, as defined by SeaBird Scientific (SBS)
"""

import numpy as np
import pandas as pd
import inspect

import yaml
import xarray as xr
import gsw

# Lookup table
with open("ctdcal/util/lookup_table.yaml", "r") as yaml_file:
    sensor_lookup = yaml.safe_load(yaml_file)


def _check_coefs(coefs_in, expected):
    """
    Compare function input coefs with expected coefficients.

    Parameters:
    -----------
    coefs_in : dictionary of str
        Sensor coefficients dictionary defined by XMLCON
    expected : list of str
        A list of coefficient key names for checking against coefs_in
    """
    missing_coefs = sorted(set(expected) - set(coefs_in))
    if missing_coefs != []:
        raise KeyError(f"Coefficient dictionary missing keys: {missing_coefs}")


def _check_freq(freq):
    """
    Convert to np.array, NaN out zeroes, convert to float if needed
    """
    freq = np.array(freq)
    # name of function calling _check_freq
    sensor = inspect.stack()[1].function

    if freq.dtype != float:  # can sometimes come in as object
        print(f"Attempting to convert {freq.dtype} to float for {sensor}")
        # log.warning(f"Attempting to convert {freq.dtype} to float for {sensor}")
        freq = freq.astype(float)

    if 0 in freq:
        N_zeroes = (freq == 0).sum()
        print(
            f"Found {N_zeroes} zero frequency readings in {sensor}, replacing with NaN"
        )
        # log.warning(
        #     f"Found {N_zeroes} zero frequency readings in {sensor}, replacing with NaN"
        # )
        freq[freq == 0] = np.nan

    return freq


def _check_volts(volts, v_min=0, v_max=5):
    """Convert to np.array, NaN out values outside of 0-5V, convert to float if needed"""
    volts = np.array(volts)
    sensor = inspect.stack()[1].function  # name of function calling _check_volts

    if volts.dtype != float:  # can sometimes come in as object
        log.warning(f"Attempting to convert {volts.dtype} to float for {sensor}")
        volts = volts.astype(float)

    if any(volts < v_min) or any(volts > v_max):
        log.warning(
            f"{sensor} has values outside of {v_min}-{v_max}V, replacing with NaN"
        )
        volts[volts < v_min] = np.nan
        volts[volts > v_max] = np.nan

    return volts


def convert_science(data, xmlcon_sensors, sensor_lookup=sensor_lookup):
    """
    Takes a xarray.Dataset and converts respective frequencies and voltages
    based on the entries within the XMLCON.

    Order must be as follows:
    1. Temperature (no dependencies): ID 55
    2. Pressure (T dependency): ID 45
    3. Conductivity (T and P dependencies): ID 3
    4. Oxygen (T, P, C dependencies): ID 38
    5. All auxiliary voltage channels
        * Alt is seperate function
    """

    #   Map the channels, sensorIDs, and priorities for processing
    #   Build dataframe from dictionary
    sensor_df = pd.DataFrame(
        list(
            {
                key: sensor.get("SensorID") for key, sensor in xmlcon_sensors.items()
            }.items()
        ),
        columns=["channel", "sensorID"],
    )
    sensor_df["sensorID"] = sensor_df["sensorID"].astype(str)
    sensor_df["function"] = [
        sensor_lookup[key]["function"] for key in list(sensor_df.sensorID.values)
    ]
    sensor_df["short_name"] = [
        sensor_lookup[key]["short_name"] for key in list(sensor_df.sensorID.values)
    ]
    sensor_df["priority"] = [
        sensor_lookup[key]["priority"] for key in list(sensor_df.sensorID.values)
    ]
    sensor_df = sensor_df.sort_values(by="priority", ascending=True)  # Sort by priority

    #   Reassign the RINKO and misc. voltage channels (IDs 27, 61)
    #   which could be defined under multiple sensor types
    for idx, _ in sensor_df.loc[
        sensor_df["short_name"].isin(["FREE", "U_DEF_poly"])].iterrows():
        if "rinko" in xmlcon_sensors[idx]["SensorName"].lower():
            sensor_df.loc[idx, "short_name"] = "RINKO"
        elif xmlcon_sensors[idx]["SensorName"] != "":
            sensor_df.loc[idx, "short_name"] = xmlcon_sensors[idx]["SensorName"]
        
    #   Build "new" column names, looking for multiple channels
    channel_names = sensor_df["short_name"].tolist()
    name_tracker = {}  # Dictionary of short_name, #times
    for i in range(len(channel_names)):
        name = channel_names[i]
        if name in name_tracker:
            name_tracker[name] += 1
            channel_names[i] = f"{name}{name_tracker[name]}"
        else:
            #   Don't rename if it hasn't been seen before
            name_tracker[name] = 1
    sensor_df["new_names"] = channel_names

    #   Mapping functions from the lookup_table.yaml
    function_map = {
        "sbs.sbe3": sbe3,
        "sbs.sbe4": sbe4,
        "sbs.sbe9": sbe9,
        "sbs.sbe43": sbe43,
        "sbs.sbe_altimeter": sbe_altimeter,
        "sbs.seapoint_fluor": seapoint_fluor,
        "sbs.v_out": v_out,
    }

    #   Preallocate space, an empty array for science units
    science_temp = xr.DataArray(
        np.zeros((len(data.engineering), len(sensor_df))),
        dims=("scan", "channel"),
        coords={"channel": sensor_df.sort_values("channel")["new_names"]},
    )

    #   Ordered by priority, SBE3 first, then 9, 4, 43, aux
    for channel in sensor_df.channel:
        this_channel = sensor_df.loc[sensor_df.channel == channel]
        func = function_map.get(this_channel["function"].iloc[0])
        coefs = xmlcon_sensors[channel]
        col_name = this_channel["short_name"].iloc[0]
        print(f"XMLCON entry: Channel {channel}, {col_name}, {this_channel["new_names"].iloc[0]}")
        match this_channel["sensorID"].iloc[0]:
            case "55":
                #   SBE3
                data_out = func(data.engineering[:, channel], coefs)
            case "45":
                #   SBE9
                data_out = func(
                    data.engineering[:, channel],
                    data.meta_columns.sel(variable="sbe9_temp"),
                    coefs,
                )
            case "3":
                #   SBE4C
                #   Dependent on SBE3 for appropriate line for 4C
                if this_channel["new_names"].item()[-1].isdigit():
                    t = science_temp.sel(channel="CTDTMP2")
                else:
                    t = science_temp.sel(channel="CTDTMP")
                p = science_temp.sel(channel="CTDPRS")
                data_out = func(
                    data.engineering[:, channel], t, p, coefs["Coefficients2"]
                )
            case "38":
                #   SBE43
                #   In case of second SBE43
                if this_channel["new_names"].item()[-1].isdigit():
                    t = science_temp.sel(channel="CTDTMP2")
                    c = science_temp.sel(channel="CTDCOND2")
                else:
                    t = science_temp.sel(channel="CTDTMP")
                    c = science_temp.sel(channel="CTDCOND")
                p = science_temp.sel(channel="CTDPRS")  #   Could already be defined
                data_out = func(data.engineering[:, channel], p, t, c,
                                coefs["CalibrationCoefficients2"], #   Use the 2007 equation
                                lat=data.meta_columns.sel(variable="lat")[0].item(),
                                lon=data.meta_columns.sel(variable="lon")[0].item(),
                                hyst_check=True)
            #   Getting down to auxiliary and derived products

            case "0":
                #   Altimeter
                data_out = func(data.engineering[:, channel], coefs)
            case "11":
                #   Seapoint fluorometer
                data_out = func(data.engineering[:, channel], coefs)
            case "61":
                #   Generic v_out
                if "rinko" in this_channel["new_names"].iloc[0].lower():
                    #   If this is the first of the two rinko channels
                    if not this_channel["new_names"].item()[-1].isdigit():
                        # hysteresis correct then pass through oxy channel voltage (see Uchida, 2010)
                        p = science_temp.sel(channel="CTDPRS")  # Already defined?
                        data_out = sbe43_hysteresis_voltage(
                            data.engineering[:, channel], p,
                            {"H1": 0.0065, "H2": 5000, "H3": 2000, "offset": 0})
                    else:
                        #   otherwise output the rinko temperature as a voltage
                        data_out = v_out(data.engineering[:, channel])
                else:
                    data_out = func(data.engineering[:, channel])
            case _:
                #   Return the source voltage out
                #   Add other routines as needed
                # print(f"Unidentified function for {col_name}."
                #         f"\nOutputting voltage, unmodified.")
                data_out = func(data.engineering[:, channel])

        science_temp.loc[:, science_temp.channel[channel]] = data_out

    #   Append the new dataset as "science"
    data["science"] = science_temp
    return data


def sbe3(freq, coefs, decimals=4):
    """
    SBE equation for converting SBE3 frequency to temperature.
    SensorID: 55

    Parameters
    ----------
    freq : array-like
        Raw frequency (Hz)
    coefs : dict
        Dictionary of calibration coefficients (G, H, I, J, F0)
    decimals : int
        Number of decimal points to round output data to.

    Returns
    -------
    t_ITS90 : array-like
        Converted temperature (ITS-90)
    """

    use_coefs = ["G", "H", "I", "J", "F0"]
    _check_coefs(coefs, use_coefs)
    freq = _check_freq(freq)

    for key in use_coefs:
        coefs[key] = float(coefs[key])

    t_ITS90 = (
        1
        / (
            coefs["G"]
            + coefs["H"] * (np.log(coefs["F0"] / freq))
            + coefs["I"] * np.power((np.log(coefs["F0"] / freq)), 2)
            + coefs["J"] * np.power((np.log(coefs["F0"] / freq)), 3)
        )
        - 273.15
    )
    return np.around(t_ITS90, decimals)


def sbe4(freq, t, p, coefs, decimals=4):
    """
    SBE equation for converting SBE4 frequency to conductivity. This conversion
    is valid for both SBE4C (profiling) and SBE4M (mooring).
    SensorID: 3

    Parameters
    ----------
    freq : array-like
        Raw frequency (Hz)
    t : array-like
        Converted temperature (ITS-90 degrees C)
    p : array-like
        Converted pressure (dbar)
    coefs : dict
        Dictionary of calibration coefficients (G, H, I, J, CPcor, CTcor)

    Returns
    -------
    c_mS_cm : array-like
        Converted conductivity (mS/cm)
    """

    use_coefs = ["G", "H", "I", "J", "CPcor", "CTcor"]
    _check_coefs(coefs, use_coefs)
    for key in use_coefs:
        coefs[key] = float(coefs[key])

    freq_kHz = _check_freq(freq) * 1e-3  # equation expects kHz

    c_S_m = (
        coefs["G"]
        + coefs["H"] * np.power(freq_kHz, 2)
        + coefs["I"] * np.power(freq_kHz, 3)
        + coefs["J"] * np.power(freq_kHz, 4)
    ) / (10 * (1 + coefs["CTcor"] * np.array(t) + coefs["CPcor"] * np.array(p)))
    c_mS_cm = c_S_m * 10  # S/m to mS/cm

    return np.around(c_mS_cm, decimals)


def sbe9(freq, t_probe, coefs, decimals=4):
    """
    SBE/STS(?) equation for converting SBE9 frequency to pressure.
    SensorID: 45

    Parameters
    ----------
    freq : array-like
        Raw frequency (Hz)
    t_probe : array-like
        Raw integer measurement from the Digiquartz temperature probe
    coefs : dict
        Dictionary of calibration coefficients
        (T1, T2, T3, T4, T5, C1, C2, C3, D1, D2, AD590M, AD590B)

    Returns
    -------
    p_dbar : array-like
        Converted pressure (dbar)
    """

    use_coefs = (
        ["T1", "T2", "T3", "T4", "T5"]
        + ["C1", "C2", "C3"]
        + ["D1", "D2"]
        + ["AD590M", "AD590B"]
        + ["Slope", "Offset"]
    )
    _check_coefs(
        coefs,
        use_coefs,
    )
    for key in use_coefs:
        coefs[key] = float(coefs[key])

    freq_MHz = _check_freq(freq) * 1e-6  # equation expects MHz
    t_probe_new = (coefs["AD590M"] * np.array(t_probe).astype(int)) + coefs["AD590B"]

    T0 = (
        coefs["T1"]
        + coefs["T2"] * t_probe_new
        + coefs["T3"] * np.power(t_probe_new, 2)
        + coefs["T4"] * np.power(t_probe_new, 3)
    )
    w = 1 - T0 * T0 * freq_MHz * freq_MHz
    p_dbar = (
        0.6894759
        * (
            (
                coefs["C1"]
                + coefs["C2"] * t_probe_new
                + coefs["C3"] * t_probe_new * t_probe_new
            )
            * w
            * (1 - (coefs["D1"] + coefs["D2"] * t_probe_new) * w)
            - 14.7
        )
        * coefs["Slope"]
        + coefs["Offset"]
    )
    return np.around(p_dbar, decimals)


def sbe43(volts, p, t, c, coefs, lat=0.0, lon=0.0, decimals=4, hyst_check=False):
    # NOTE: lat/lon = 0 is not "acceptable" for GSW, come up with something else?
    """
    SBE equation for converting SBE43 engineering units to oxygen (ml/l).
    SensorID: 38

    Parameters
    ----------
    volts : array-like
        Raw voltage
    p : array-like
        Converted pressure (dbar)
    t : array-like
        Converted temperature (Celsius)
    c : array-like
        Converted conductivity (mS/cm)
    coefs : dict
        Dictionary of calibration coefficients (Soc, offset, Tau20, A, B, C, E)
    lat : array-like, optional
        Latitude (decimal degrees north)
    lon : array-like, optional
        Longitude (decimal degrees)
    hyst_check : boolean, optional
        Whether to apply hysteresis correction to SBE43 voltage. Defaults to false.

    Returns
    -------
    oxy_umolkg : array-like
        Converted oxygen (umol/kg)
    # oxy_ml_l : array-like
    #     Converted oxygen (mL/L)
    """
    use_coefs = ["Soc", "offset", "Tau20", "A", "B", "C", "E"]
    _check_coefs(coefs, use_coefs)
    volts_original = _check_volts(volts)

    for key in use_coefs:
        coefs[key] = float(coefs[key])

    if hyst_check:
        volts = sbe43_hysteresis_voltage(volts_original, p, coefs)

    t_Kelvin = np.array(t) + 273.15

    SP = gsw.SP_from_C(c, t, p)
    SA = gsw.SA_from_SP(SP, p, lon, lat)
    CT = gsw.CT_from_t(SA, t, p)
    sigma0 = gsw.sigma0(SA, CT)
    o2sol = gsw.O2sol(SA, CT, p, lon, lat)  # umol/kg
    o2sol_ml_l = oxy_umolkg_to_ml(o2sol, sigma0)  # equation expects mL/L

    # NOTE: lat/lon always required to get o2sol (and need SA/CT for sigma0 anyway)
    # the above is equivalent to:
    # pt = gsw.pt0_from_t(SA, t, p)
    # o2sol = gsw.O2sol_SP_pt(s, pt)

    oxy_ml_l = (
        coefs["Soc"]
        * (volts + coefs["offset"])
        * (
            1.0
            + coefs["A"] * np.array(t)
            + coefs["B"] * np.power(t, 2)
            + coefs["C"] * np.power(t, 3)
        )
        * o2sol_ml_l
        * np.exp(coefs["E"] * np.array(p) / t_Kelvin)
    )
    oxy_umolkg = oxy_ml_to_umolkg(oxy_ml_l, sigma0)

    return np.around(oxy_umolkg, decimals)

def oxy_umolkg_to_ml(oxy_umol_kg, sigma0):
    """Convert dissolved oxygen from units of micromol/kg to mL/L.

    Parameters
    ----------
    oxy_umol_kg : array-like
        Dissolved oxygen in units of [umol/kg]
    sigma0 : array-like
        Potential density anomaly (i.e. sigma - 1000) referenced to 0 dbar [kg/m^3]

    Returns
    -------
    oxy_mL_L : array-like
        Dissolved oxygen in units of [mL/L]

    Notes
    -----
    Conversion value 44660 is exact for oxygen gas and derived from the ideal gas law.
    (c.f. Sea-Bird Application Note 64, pg. 6)
    """

    oxy_mL_L = oxy_umol_kg * (sigma0 + 1000) / 44660

    return oxy_mL_L

def oxy_ml_to_umolkg(oxy_mL_L, sigma0):
    """Convert dissolved oxygen from units of mL/L to micromol/kg.

    Parameters
    ----------
    oxy_mL_L : array-like
        Dissolved oxygen in units of [mL/L]
    sigma0 : array-like
        Potential density anomaly (i.e. sigma - 1000) referenced to 0 dbar [kg/m^3]

    Returns
    -------
    oxy_umol_kg : array-like
        Dissolved oxygen in units of [umol/kg]

    Notes
    -----
    Conversion value 44660 is exact for oxygen gas and derived from the ideal gas law.
    (c.f. Sea-Bird Application Note 64, pg. 6)
    """

    oxy_umol_kg = oxy_mL_L * 44660 / (sigma0 + 1000)

    return oxy_umol_kg

def sbe43_hysteresis_voltage(volts, p, coefs, sample_freq=24):
    """
    SBE equation for removing hysteresis from raw voltage values. This function must
    be run before the sbe43 conversion function above.

    Oxygen hysteresis can be corrected after conversion from volts to oxygen
    concentration, see oxy_fitting.hysteresis_correction()

    Parameters
    ----------
    volts : array-like
        Raw voltage
    p : array-like
        CTD pressure values (dbar)
    coefs : dict
        Dictionary of calibration coefficients (H1, H2, H3, offset)
    sample_freq : scalar, optional
        CTD sampling frequency (Hz)

    Returns
    -------
    volts_corrected : array-like
        Hysteresis-corrected voltage

    Notes
    -----
    The hysteresis algorithm is backward-looking so scan 0 must be skipped (as no
    information is available before the first scan).

    See Application Note 64-3 for more information.
    """
    use_coefs = ["H1", "H2", "H3", "offset"]
    _check_coefs(coefs, use_coefs)
    volts = _check_volts(volts)
    for key in use_coefs:
        coefs[key] = float(coefs[key])

    dt = 1 / sample_freq
    D = 1 + coefs["H1"] * (np.exp(np.array(p) / coefs["H2"]) - 1)
    C = np.exp(-1 * dt / coefs["H3"])

    oxy_volts = volts + coefs["offset"]
    oxy_volts_new = np.zeros(oxy_volts.shape)
    oxy_volts_new[0] = oxy_volts[0]
    for i in np.arange(1, len(oxy_volts)):
        oxy_volts_new[i] = (
            (oxy_volts[i] + (oxy_volts_new[i - 1] * C * D[i])) - (oxy_volts[i - 1] * C)
        ) / D[i]

    volts_corrected = oxy_volts_new - coefs["offset"]

    return volts_corrected

def sbe_altimeter(volts, coefs, decimals=1):
    """
    SBE equation for converting altimeter voltages to meters. This conversion
    is valid for altimeters integrated with any Sea-Bird CTD (e.g. 9+, 19, 25).
    Sensor ID: 0

    Parameters
    ----------
    volts : array-like
        Raw voltages
    coefs : dict
        Dictionary of calibration coefficients (ScaleFactor, Offset)

    Returns
    -------
    bottom_distance : array-like
        Distance from the altimeter to an object below it (meters)

    Notes
    -----
    Equation provdided by SBE in Application Note 95, page 1.

    While the SBE documentation refers to a Teledyne Benthos or Valeport altimeter,
    the equation works for all altimeters typically found in the wild.
    """
    use_coefs = ["ScaleFactor", "Offset"]
    _check_coefs(coefs, use_coefs)
    volts = _check_volts(volts)
    for key in use_coefs:
        coefs[key] = float(coefs[key])

    bottom_distance = (300 * volts / coefs["ScaleFactor"]) + coefs["Offset"]

    return np.around(bottom_distance, decimals)

def seapoint_fluor(volts, coefs, decimals=6):
    """
    Raw voltage supplied from fluorometer right now, after looking at xmlcon.
    The method will do nothing but spit out the exact values that came in.
    SensorID: 11

    Parameters
    ----------
    volts : array-like
        Raw voltage
    coefs : dict
        Dictionary of calibration coefficients (GainSetting, Offset)

    Returns
    -------
    fluoro : array-like
        Raw voltage

    Notes
    -----
    According to .xmlcon, GainSetting "is an array index, not the actual gain setting."
    """
    _check_coefs(coefs, ["GainSetting", "Offset"])
    volts = np.array(volts)
    fluoro = np.around(volts, decimals) #   Return voltage

    return fluoro

def v_out(source):
    #   Return voltage source
    return source
