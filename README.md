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

## Outputs
- **filled.tif** (type: raster; units: meters): Map of elevation after any pits are filled.
- **flow_accumulation.tif** (type: raster): Map of flow accumulation.
- **flow_direction.tif** (type: raster): MFD flow direction. Note: the pixel values should not be interpreted directly. Each 32-bit number consists of 8 4-bit numbers. Each 4-bit number represents the proportion of flow into one of the eight neighboring pixels.
- **slope.tif** (type: raster): Percent slope, calculated from the pit-filled DEM. 100 is equivalent to a 45 degree slope.
- **stream_tfa_[TFA].tif** (type: raster): Stream network, created using flow direction and flow accumulation derived from the DEM and Threshold Flow Accumulation. Values of 1 represent streams, values of 0 are non-stream pixels.
- **strahler_stream_order_tfa_[TFA].gpkg** (type: vector): A vector of line segments indicating the Strahler stream order and other properties of each stream segment. Created if `algorithm == 'd8'` and `calculate_stream_order` is True. Fields:
  - **order**: The Strahler stream order.
  - **river_id**: A unique identifier used by all stream segments that connect to the same outlet.
  - **drop_distance**: The drop distance in DEM elevation units from the upstream to downstream component of this stream segment.
  - **outlet**: 1 if this segment is an outlet, 0 if it is not.
  - **us_fa** (units: pixel): The flow accumulation value at the upstream end of the stream segment.
  - **ds_fa** (units: pixel): The flow accumulation value at the downstream end of the stream segment.
  - **thresh_fa** (units: pixel): The final threshold flow accumulation value used to determine the river segments.
  - **upstream_d8_dir**: The direction of flow immediately upstream.
  - **ds_x** (units: pixel): The DEM X coordinate for the outlet in pixels from the origin.
  - **ds_y** (units: pixel): The DEM Y coordinate for the outlet in pixels from the origin.
  - **ds_x_1** (units: pixel): The DEM X coordinate that is 1 pixel upstream from the outlet.
  - **ds_y_1** (units: pixel): The DEM Y coordinate that is 1 pixel upstream from the outlet.
  - **us_x** (units: pixel): The DEM X coordinate for the upstream inlet.
  - **us_y** (units: pixel): The DEM Y coordinate for the upstream inlet.
- **subwatersheds_tfa_[TFA].gpkg** (type: vector): A GeoPackage with polygon features representing subwatersheds. A new subwatershed is created for each tributary of a stream and is influenced greatly by your choice of Threshold Flow Accumulation value. Created if `algorithm == 'd8'` and `calculate_subwatersheds` is True. Fields:
  - **stream_id**: A unique stream id, matching the one in the Strahler stream order vector.
  - **terminated_early**: Indicates whether generation of this subwatershed terminated early (1) or completed as expected (0). If you encounter a (1), please let us know via the forums, community.naturalcapitalproject.org.
  - **outlet_x**: The X coordinate in pixels from the origin of the outlet of the watershed. This can be useful when determining other properties of the watershed when indexing with the underlying raster data.
  - **outlet_y**: The X coordinate in pixels from the origin of the outlet of the watershed. This can be useful when determining other properties of the watershed when indexing with the underlying raster data.
- **downslope_distance_tfa_[TFA].tif** (type: raster; units: pixels): Flow distance from each pixel to a stream. Calculated if `calculate_downslope_distance` is True.

## Sample Data
A datastack JSON file is provided in this repo along with a sample DEM raster for example/testing purposes only.

## Testing
Tests rely on `pytest`, which is _not_ included in the project dependencies, since the model itself does not require it. To run the tests:
1. Activate a virtual environment and ensure `pytest` is installed (e.g., via `mamba install pytest` or `conda install pytest`).
2. From the root of this repository, run `pytest tests`.
