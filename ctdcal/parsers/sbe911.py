"""
Parsing SBE911+ Data
====================

Module for parsing SeaBird's "raw" acquisition files.

This module contains the code required for parsing SeaBird's .HEX, .BL, .XMLCON and assembling an Xarray dataset for easy reading, manipulation, and exporting.
"""

import io
import xml.etree.cElementTree as ET
from pathlib import Path
from typing import Generator, Literal

import numpy as np
import pandas as pd
import xarray as xr

ERRORS = Literal["store","raise","ignore"]

def hex_to_dataset(hex:str, errors: ERRORS="raise") -> xr.Dataset:
    """
    Converts a HEX-formatted string into an xarray.Dataset for structured data storage for use in read_hex().

    Code initially written 2024 by Andrew Barna.

    Parameters
    ----------
    hex : str
        A string containing HEX-encoded data. The input may include header lines
        (starting with `*`) and data lines containing HEX characters. The header
        should include a line specifying "number of bytes per scan = X".
    errors : {'store', 'raise', 'ignore'}, optional
        Specifies how to handle invalid data lines:
        - 'raise': Raise a ValueError for lines with invalid scan lengths (default).
        - 'ignore': Skip invalid lines without raising an error.
        - 'store': Placeholder for future implementation (raises NotImplementedError).

    Returns
    -------
    xr.Dataset
        A dataset containing the parsed HEX data as a compressed DataArray, along
        with metadata extracted from the header. The dataset structure is:
        - Data variable:
          - `hex`: A DataArray with dimensions:
            - `scan`: Number of scans (rows of data).
            - `bytes_per_scan`: Bytes in each scan.
        - Attributes:
          - `hex_header`: Metadata comments extracted from the header.
    """
    _comments = []  #   hex header comments written by deck box/SeaSave
    out = []        #   hex bytes out
    datalen = 0     #   Stores # bytes per scan

    for lineno, line in enumerate(hex.splitlines(), start=1):
        if "number of bytes per scan" in line.lower():
            datalen = int(line.split("= ")[1])
            linelen = datalen * 2

        if line.startswith("*"): # comments
            _comments.append(line)
            continue

        if datalen == 0:
            raise ValueError(f"Could not find number of bytes per scan in {lineno} lines")

        if len(line) != linelen:
            if errors == "raise":
                raise ValueError(f"invalid scan lengths line: {lineno}")
            elif errors == "ignore":
                continue
            elif errors == "store":
                raise NotImplementedError("better figure out how to do this")

        out.append([*bytes.fromhex(line)])
    header = "\n".join(_comments)
    data = np.array(out, dtype=np.uint8)

    data_array = xr.DataArray(data, dims=["scan","bytes_per_scan"])
    # Compression: Tuning chunk size, especially that column as "1" results in _significant_ 
    # savings from the raw. 72MB -> 3.5MB

    data_array.encoding["zlib"] = True      # compress the data
    data_array.encoding["complevel"] = 6    # use compression level 6
    data_array.encoding["chunksizes"] = (60*60*24, 1)   # chunk every hour of data (for 24hz data)
                                                        #, and each column seperately

    return xr.Dataset({
        "hex": data_array  # TODO: decide on the name of this variable as we will live with it "forever", "hex" is awful, but maybe the best?
    },
    attrs={
        "hex_header": header
    })

def read_hex(path, xmlcon=(".XMLCON", ".xmlcon"), bl=(".bl", ), hdr=(".hdr", )) -> xr.Dataset:
    """
    Reads a HEX file and its associated metadata files, returning an xarray.Dataset.

    This function reads a HEX file and optionally associates metadata from
    `.xmlcon`, `.bl`, and `.hdr` files if they exist in the same location as
    the `.hex` file folder. The metadata is added as attributes to the resulting
    xarray.Dataset.

    Code initially written 2024 by Andrew Barna.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the HEX file.
    xmlcon : tuple of str, optional
        File suffixes to search for associated `.xmlcon` configuration files.
        Default is `(".XMLCON", ".xmlcon")`.
    bl : tuple of str, optional
        File suffixes to search for `.bl` files, which may contain additional metadata.
        Default is `(".bl",)`.
    hdr : tuple of str, optional
        File suffixes to search for `.hdr` files, potentially containing header information.
        Default is `(".hdr",)`.

    Returns
    -------
    xr.Dataset
        An xarray.Dataset containing the HEX data and metadata. The dataset includes:
        - Data variables from the HEX file.
        - Attributes:
          - `hex_filename`: Name of the HEX file.
          - `xmlcon_filename`: Name of the `.xmlcon` file (if found).
          - `xmlcon`: Content of the `.xmlcon` file (if found).
          - `bl_filename`: Name of the `.bl` file (if found).
          - `bl`: Content of the `.bl` file (if found).
          - `hdr_filename`: Name of the `.hdr` file (if found).
    """
    hex_path = Path(path)
    xmlcon_path = None
    bl_path = None
    hdr_path = None

    if xmlcon is not None:
        for suffix in xmlcon:
            if (xmlcon_p := hex_path.with_suffix(suffix)).exists():
                xmlcon_path = xmlcon_p
    if bl is not None:
        for suffix in bl:
            if (bl_p := hex_path.with_suffix(suffix)).exists():
                bl_path = bl_p
    if hdr is not None:
        for suffix in hdr:
            if (hdr_p := hex_path.with_suffix(suffix)).exists():
                hdr_path = hdr_p

    ds = hex_to_dataset(hex_path.read_text(), errors="ignore")
    ds.attrs["hex_filename"] = hex_path.name
    if xmlcon_path is not None:
        ds.attrs["xmlcon_filename"] = xmlcon_path.name
        # ds.attrs["xmlcon"] = xmlcon_path.read_text()  #   Alternative, storing the raw .xmlcon text
        ds.attrs["xmlcon_box"], ds.attrs["xmlcon_sensors"] = parse_xmlcon(xmlcon_path)
        #   Shorthand the important channel supression information
        ds.attrs["f_s"] = int(ds.attrs["xmlcon_box"]["FrequencyChannelsSuppressed"])
        ds.attrs["v_s"] = int(ds.attrs["xmlcon_box"]["VoltageWordsSuppressed"])
    if bl_path is not None:
        ds.attrs["bl_filename"] = bl_path.name
        # ds.attrs["bl"] = bl_path.read_text()  #   Alternative, storing the raw .bl text
        ds.attrs["bl"] = load_bl(bl_path)
    if hdr_path is not None:
        ds.attrs["hdr_filename"] = hdr_path.name
        # TODO... figure out why this file doesn't seem to be matching the hex header (line endings?), and what to do when it doesnt

    return ds

def load_bl(bl_path):
    """
    Reads a rosette bottle log (.bl) file and returns its data as a pandas DataFrame.

    The function reads a `.bl` file, removes non-numeric header lines, and parses 
    the data into a structured pandas DataFrame. It also performs basic validation
    checks to detect irregularities in the bottle numbers and the total number of 
    bottle closures.

    Code initially written 2024 Aaron Mau.

    Parameters
    ----------
    bl_path : str or pathlib.Path
        Path to the rosette bottle log (.bl) file.

    Returns
    -------
    pandas.DataFrame
        A DataFrame containing the parsed rosette bottle log data. The columns include:
        - `seq` (int): Sequence number of the bottle closure.
        - `bnum` (int): Bottle number.
        - `date-time` (str): Date and time of the closure (as a string).
        - `scan1` (int): Starting scan number for the bottle event.
        - `scan2` (int): Ending scan number for the bottle event.
    """
    with open(bl_path) as bl_file:
        #   Remove non-numeric starts
        bl_dat = [line for line in bl_file if ',' in line]
    
    bl = pd.read_csv(io.StringIO(''.join(bl_dat)), 
                 header=None,  #    Skip header
                 names=['seq', 'bnum', 'date-time', 'scan1', 'scan2'])

    bnum_diff = bl['bnum'].diff()
    reset_rows = bl[bnum_diff < 1]
    
    if not reset_rows.empty:
        print("Warning: Bottle number does not increment positively:")
        print(reset_rows)
    
    if len(bl) > 36:
        print(f"Warning: More than 36 bottle closures detected: {len(bl)} total")

    return bl

def parse_xmlcon(xml_config_path, encoding="cp437"):
    """
    Parses an XMLCON configuration file into configuration and sensor metadata dictionaries.

    This function reads an XMLCON file, extracts deck unit configuration settings, 
    and retrieves metadata and calibration coefficients for connected sensors.

    Code initially written 2024 Aaron Mau.

    Parameters
    ----------
    xml_config_path : str or pathlib.Path
        Path to the XMLCON file to be parsed.
    encoding : str, optional
        Encoding used to read the XMLCON file. Default is `"cp437"`.

    Returns
    -------
    tuple
        A tuple containing two dictionaries:
        - `config_dict` (dict): A dictionary of deck unit configuration settings, 
          where keys are the configuration tags and values are their respective values.
        - `sensor_dict` (dict): A dictionary of sensor metadata, where keys are sensor
          indices (as integers) and values are nested dictionaries containing metadata 
          and calibration coefficients for each sensor.

    Notes
    -----
    - The XMLCON file is parsed using an `ElementTree` object to extract both configuration 
      settings and sensor information.
    - Calibration coefficients for sensors (e.g., `SBE4` or `SBE43`) are nested within the 
      sensor metadata and are structured as dictionaries.
    - If a tag with calibration coefficients is repeated, it is appended with `2` to 
      avoid overwriting.
    """
    #   Create xlmcon element tree
    with open(xml_config_path, encoding=encoding) as xml_config_file:
        xmlread = xml_config_file.read()
    xmlcon = ET.fromstring(xmlread)
    
    config_dict = {}    #   Deck unit
    for deck_setting in xmlcon[0]:
        config_dict[deck_setting.tag.strip()] = deck_setting.text.strip()
    sensor_array_size = xmlcon.find('.//SensorArray')   #   Pull out reported sensor array size for comparison
    if sensor_array_size is not None:
        config_dict['SensorArraySize'] = int(sensor_array_size.attrib.get('Size'))
    
    sensor_dict = {}    #   Sensors connected, with coefficients
    #   JB/JT endcap channel positions
    for position in xmlcon[0][-1]:
        #   Sensor metadata (SN, cal date, etc.)
        meta = {}
        meta["SensorID"] = position.attrib["SensorID"]
        for md_entry in position[0]:
            # print(md_entry.tag, md_entry.attrib, md_entry.text)
            #   Nested coefficients found in SBE4/SBE43
            if "Coefficients" in md_entry.tag:
                # print(f"Found nested calibration coefficients in {md_entry.tag}")
                coefs = {}
                for coef in md_entry:
                    # print(coef.tag, coef.attrib, coef.text)
                    coefs[coef.tag.strip()] = coef.text.strip()
                if md_entry.tag in meta.keys():
                    meta[md_entry.tag.strip()+"2"] = coefs
                else:
                    meta[md_entry.tag.strip()] = coefs
            else:    
                meta[md_entry.tag.strip()] = md_entry.text.strip()

        sensor_dict[int(position.attrib["index"])] = meta
    
    if len(sensor_dict) != config_dict['SensorArraySize']:
        print(f"Warning: XMLCON sensor dictionary size ({len(sensor_dict)}) differs from reported SensorArraySize ({config_dict['SensorArraySize']}). Check .XMLCON file.")

    return config_dict, sensor_dict

def ds_to_hex(ds: xr.Dataset) -> Generator[bytes, None, None]:
    """The input for this function is the output of the above (we don't have a spec yet).

    When first made, this was meant to recreate the input byte for byte when moving the data across
    a very low bandwidth network (USAP).

    It works by dumping numpy to a python bytes object, dumping that to hex, uppercasing and encoding 
    using UTF8 (ASCII in this case). The output of this is a single long string which is then
    chunked though to split all the lines.

    Code initially written 2024 Andrew Barna.
    """
    yield "\r\n".join(ds.comments.splitlines()).encode("utf8")
    yield b"\r\n"
    data = bytes(ds.hex.as_numpy().values).hex().upper().encode("utf8")
    row_len = ds.dims["bytes_per_scan"] * 2
    
    for row in range(ds.dims["scan"]):
        start = row * row_len
        stop = row * row_len + row_len
        yield data[start:stop]
        yield b"\r\n"

def get_freq(hex, channel):
    #   Barna's optimized freq2
    #   should in theory only do two memory allocations/copies
    m = 3 * channel
    data = hex[:,m].astype("uint32") << 8   #   convert first byte to have enough space, shift by one byte
    data = (data | hex[:, m+1]) << 8    #   "or" in the next byte, shift by one more byte
    data = data | hex[:, m+2]   #   "or" in the last byte
    return data / 256

def hex_to_f(hex_data, f_suppressed=0):
    """
    Generate a DataArray `freq_out` with rows corresponding to scans and 
    columns corresponding to frequency channels.
    """
    f_channels = 5 - f_suppressed   # Number of frequency channels from .XMLCON
    num_scans = hex_data.shape[0]   #   For preallocations

    freq_out = xr.DataArray(
        np.full((num_scans, f_channels), np.nan),  # Create a 2D array filled with NaN
        dims=['scan', 'channel']                 # Define dimensions
    )

    # Populate the freq_out DataArray
    for channel in range(f_channels):
        freq_out[:, channel] = get_freq(hex_data, channel)

    return freq_out

def calc_v_indexes(n):
    """
    Calculate voltage byte indices. N is of type int for the channel number.

    Determine how much to "shift" the values by.

    Returns first byte index, second byte index, and if 12 bits are in lower or higher nibble.
    """
    start = (n // 2 * 3)    #   First byte index (every two channels take 3 bytes)
    high = n % 2            #   'Nibble' value of the byte
    return start + high, start + high + 1, 1 - high

def get_channel_voltage(hex, channel, freq_supressed=0, v_supresssed=0):
    """
    Extracts and normalizes the voltage for a given channel from a SeaBird hex file data array.

    The function computes the voltage for a specified channel by extracting relevant data 
    from the provided `hex` array, adjusting for suppressed frequency channels, 
    and applying bit manipulation to extract the 12-bit voltage value. It then normalizes 
    the 12-bit data to a 0-5V range.

    Code initially written 2024 Andrew Barna.

    Parameters:
    -----------
    hex : numpy.ndarray
        A 2D NumPy array containing raw hex data from the SeaBird file, with each row representing a scan 
        and each column representing a byte of data.
    
    channel : int
        The channel number (starting from 0) from which the voltage needs to be extracted.
    
    freq_supressed : int, optional
        An offset to account for suppressed frequency channels in the SeaSave configuration. 
        Default is 0, indicating no suppressed channels.
    
    v_supresssed : int, optional
        An offset to account for suppressed voltage channels. This parameter is not currently used 
        but could be incorporated if needed. Default is 0.
    """
    offset = (5 - freq_supressed) * 3
        
    first_byte_idx, second_byte_idx, shift = calc_v_indexes(channel)
    first_byte_idx += offset    #   Account for index changes from supressed channels
    second_byte_idx += offset
    
    data = hex[:, first_byte_idx].astype("uint16") << 8
    data = data | hex[:, second_byte_idx]
    data = data >> (4 * shift)  #   Apply the shift realignment
    data = data & 4095  #   Ensure only the 12 bits for the voltage are kept
    return 5 * (1 - (data/4095))    #   Normalize 12-bit value (0-4095) to 0-5V

def hex_to_v(hex, data_xmlcon, freq_supressed=0):
    """
    Extracts voltage data for all channels and returns a DataArray.

    The function calculates the voltage values for all channels in the specified range using the provided 
    hex data array and extracts the voltage values for each channel using the `get_channel_voltage` function.
    The result is stored in an `xarray.DataArray`, with dimensions corresponding to scans and channels.

    Parameters:
    -----------
    hex : numpy.ndarray
        A 2D array containing raw hex data from the SeaBird instrument, where each row represents a scan, 
        and each column corresponds to a byte of data.
    
    data_xmlcon : dict
        A dictionary containing configuration data, used to determine the number of frequency channels.
    
    freq_supressed : int, optional
        The number of frequency channels suppressed in the configuration. This is used to adjust the indices 
        for the voltage channels. Default is 0 (indicating no suppressed channels).
    
    """
    #   Use .XMLCON length, rather than what is reported by the xmlcon's SensorArraySize.
    start_v_ind = len(data_xmlcon) - (len(data_xmlcon) - 5)
    end_v_ind = len(data_xmlcon)

    if start_v_ind < 0 or start_v_ind >= end_v_ind:
        raise ValueError(f"Invalid channel indices: start_v_ind={start_v_ind}, end_v_ind={end_v_ind}")

    num_scans = hex.shape[0]   #   For preallocations
    num_channels = end_v_ind - start_v_ind 

    v_out = xr.DataArray(
        np.full((num_scans, num_channels), np.nan),  # Create a 2D array filled with NaN
        dims=['scan', 'channel']                    # Define dimensions
    )

    for channel in range(start_v_ind, end_v_ind):
        print(f"Processing voltage channel: {channel}")
        v_out[:, channel - start_v_ind] = get_channel_voltage(hex, channel, freq_supressed)

    return v_out

def odf_wrapper(hex_path):
    """
    Builds the Dataset, including engineering units.
    """
    data = read_hex(hex_path)
    print(data.attrs["f_s"])
    data["engineering"] = xr.concat([hex_to_f(data.hex, data.attrs["f_s"]),
                                     hex_to_v(data.hex, data.attrs["xmlcon_sensors"], data.attrs["f_s"])], dim="channel")    #   Frequency channels  

    return data

def parse_hdr():
    pass

def parse_btl():
    pass

def parse_ros():
    pass

def parse_cnv():
    """
    In case the .HEX are unavailable or we want to load a SeaBird-derived .CNV file

    Add a check if there is any sort of pressure binning.
    """
    pass