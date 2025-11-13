# InVEST Plugin: RouteDEM with TFA Range Input

## About
A plugin for InVEST that provides an alternative version of the RouteDEM utility. This version includes a "Threshold Flow Accumulation Range" input, which allows it to compute outputs for a range of TFAs in a single run.

Since threshold flow accumulation is only relevant in cases where streams are calculated from the flow accumulation output, this plugin always calculates flow direction, flow accumulation, and streams.

## Usage
1. First, install this plugin. The easiest way to do this is via the InVEST Workbench (version 3.17.0 or later). You can download and install this plugin using its git URL [https://github.com/natcap/invest-routedem-tfa-range.git](https://github.com/natcap/invest-routedem-tfa-range.git), or, if you prefer, you can clone this repo to your computer and then install it using the path to your local copy.
2. Once the plugin has been installed, you can run it from the Workbench, just as you would run any InVEST model.

## Data Needs
The inputs required by this model are identical to those of the [InVEST RouteDEM utility](https://storage.googleapis.com/releases.naturalcapitalproject.org/invest-userguide/latest/en/routedem.html), with the following exceptions:
1. This plugin always calculates flow direction, flow accumulation, and streams. As such, the RouteDEM boolean inputs Calculate Flow Direction, Calculate Flow Accumulation, and Calculate Streams have been removed.
2. The "Threshold Flow Accumulation" input has been replaced by "Threshold Flow Accumulation Range."

## Sample Data
A datastack JSON file is provided in this repo along with a sample DEM raster for example/testing purposes only.

## Testing
Tests rely on `pytest`, which is _not_ included in the project dependencies, since the model itself does not require it. To run the tests:
1. Activate a virtual environment and ensure `pytest` is installed (e.g., via `mamba install pytest` or `conda install pytest`).
2. From the root of this repository, run `pytest tests`.
