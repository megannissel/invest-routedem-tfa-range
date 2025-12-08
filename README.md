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
2. The "Threshold Flow Accumulation" input has been replaced by "Threshold Flow Accumulation Range," allowing the model to compute outputs for a range of TFAs in a single run.

### Threshold Flow Accumulation Range
The Threshold Flow Accumulation (TFA) is a stream delineation algorithm parameter that specifies the number of upstream pixels that must flow into a pixel before it is classified as a stream. In this plugin, this input takes the form ``start_value:stop_value:step_value``, where:
- ``start_value``: An integer specifying at which value to start.
- ``stop_value``: An integer specifying at which value to stop (not inclusive).
- ``step_value``: An integer specifying the incrementation from the ``start_value`` up to the ``stop_value``.

If you wanted the model to calculate results for Threshold Flow Accumulation values of 1000 pixels, 1500 pixels, and 2000 pixels, you would enter ``1000:2001:500``. Note that the ``stop_value`` here is '2001'; since ``stop_value`` is not included; if you entered ``1000:2000:500``, the model would only calculate results for 1000 pixels and 1500 pixels.

For more information on choosing Threshold Flow Accumulation values, see the InVEST Data Sources documentation on [Threshold Flow Accumulation](https://storage.googleapis.com/releases.naturalcapitalproject.org/invest-userguide/latest/en/data_sources.html#threshold-flow-accumulation).

## Sample Data
A datastack JSON file is provided in this repo along with a sample DEM raster for example/testing purposes only.

## Testing
Tests rely on `pytest`, which is _not_ included in the project dependencies, since the model itself does not require it. To run the tests:
1. Activate a virtual environment and ensure `pytest` is installed (e.g., via `mamba install pytest` or `conda install pytest`).
2. From the root of this repository, run `pytest tests`.
