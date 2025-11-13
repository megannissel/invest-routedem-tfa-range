"""
An adaptation of the InVEST RouteDEM utility that computes a range of TFAs in a single run.

RouteDEM is a utility for exposing the natcap.invest routing package to UI.
"""
import logging
import os

import pygeoprocessing
import pygeoprocessing.routing
import taskgraph

from natcap.invest import gettext
from natcap.invest import spec
from natcap.invest import utils
from natcap.invest import validation
from natcap.invest.file_registry import FileRegistry
from natcap.invest.unit_registry import u

LOGGER = logging.getLogger(__name__)

INVALID_BAND_INDEX_MSG = gettext('Must be between 1 and {maximum}')
INVALID_RANGE_MSG = gettext('Provided range contains zero items')

MODEL_SPEC = spec.ModelSpec(
    model_id="invest_routedem_tfa_range",
    model_title=gettext("RouteDEM with TFA range"),
    userguide="routedem.html",
    validate_spatial_overlap=True,
    different_projections_ok=False,
    aliases=(),
    module_name=__name__,
    input_field_order=[
        ["workspace_dir", "results_suffix"],
        ["dem_path", "dem_band_index"],
        ["calculate_slope"],
        ["algorithm"],
        ["threshold_flow_accumulation_range", "calculate_downslope_distance",
         "calculate_stream_order", "calculate_subwatersheds"]
    ],
    inputs=[
        spec.WORKSPACE,
        spec.SUFFIX,
        spec.N_WORKERS,
        spec.DEM.model_copy(update=dict(id="dem_path")),
        spec.IntegerInput(
            id="dem_band_index",
            name=gettext("band index"),
            about=gettext("Index of the raster band to use, for multi-band rasters."),
            required=False,
            units=u.none,
            expression="value >= 1"
        ),
        spec.OptionStringInput(
            id="algorithm",
            name=gettext("routing algorithm"),
            about=gettext("The routing algorithm to use."),
            options=[
                spec.Option(
                    key="D8",
                    about=(
                        "All water on a pixel flows into the most downhill of its 8"
                        " surrounding pixels")),
                spec.Option(
                    key="MFD",
                    about=(
                        "Flow off a pixel is modeled fractionally so that water is split"
                        " among multiple downslope pixels"))
            ]
        ),
        spec.StringInput(
            id="threshold_flow_accumulation_range",
            name=gettext("threshold flow accumulation value range"),
            about=gettext(
                "A range for the number of upslope pixels that must flow into a pixel"
                " before it is classified as a stream. Must be of the form"
                " start_value:stop_value:step_value"
            ),
            display_name="start_value:stop_value:step_value",
            regexp="^[0-9]+:[0-9]+:[1-9][0-9]*$"
        ),
        spec.BooleanInput(
            id="calculate_downslope_distance",
            name=gettext("calculate distance to stream"),
            about=gettext(
                "Calculate flow distance from each pixel to a stream as defined in the"
                " Calculate Streams output."
            ),
            required=False,
        ),
        spec.BooleanInput(
            id="calculate_slope",
            name=gettext("calculate slope"),
            about=gettext("Calculate percent slope from the provided DEM."),
            required=False
        ),
        spec.BooleanInput(
            id="calculate_stream_order",
            name=gettext("calculate strahler stream orders (D8 only)"),
            about=gettext("Calculate the Strahler Stream order."),
            required=False,
            allowed="algorithm == 'D8'"
        ),
        spec.BooleanInput(
            id="calculate_subwatersheds",
            name=gettext("calculate subwatersheds (D8 only)"),
            about=gettext("Determine subwatersheds from the stream order."),
            required=False,
            allowed="calculate_stream_order and algorithm == 'D8'"
        )
    ],
    outputs=[
        spec.TASKGRAPH_CACHE,
        spec.FILLED_DEM.model_copy(update=dict(
            id="filled",
            path="filled.tif")),
        spec.FLOW_ACCUMULATION,
        spec.FLOW_DIRECTION,
        spec.SLOPE.model_copy(update=dict(
            created_if='calculate_slope')),
        spec.STREAM.model_copy(update=dict(
            id="stream_mask_[TFA]",
            path="stream_mask_tfa_[TFA].tif")),
        spec.VectorOutput(
            id="strahler_stream_order_[TFA]",
            path="strahler_stream_order_tfa_[TFA].gpkg",
            about=gettext(
                "A vector of line segments indicating the Strahler stream order and other"
                " properties of each stream segment."
            ),
            created_if="algorithm == 'd8' and calculate_stream_order",
            geometry_types={"LINESTRING"},
            fields=[
                spec.NumberOutput(
                    id="order", about=gettext("The Strahler stream order."), units=u.none
                ),
                spec.NumberOutput(
                    id="river_id",
                    about=gettext(
                        "A unique identifier used by all stream segments that connect to"
                        " the same outlet."
                    ),
                    units=u.none
                ),
                spec.NumberOutput(
                    id="drop_distance",
                    about=gettext(
                        "The drop distance in DEM elevation units from the upstream to"
                        " downstream component of this stream segment."
                    ),
                    units=u.none
                ),
                spec.NumberOutput(
                    id="outlet",
                    about=gettext("1 if this segment is an outlet, 0 if it is not."),
                    units=u.none
                ),
                spec.NumberOutput(
                    id="us_fa",
                    about=gettext(
                        "The flow accumulation value at the upstream end of the stream"
                        " segment."
                    ),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="ds_fa",
                    about=gettext(
                        "The flow accumulation value at the downstream end of the stream"
                        " segment."
                    ),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="thresh_fa",
                    about=gettext(
                        "The final threshold flow accumulation value used to determine"
                        " the river segments."
                    ),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="upstream_d8_dir",
                    about=gettext("The direction of flow immediately upstream."),
                    units=u.none
                ),
                spec.NumberOutput(
                    id="ds_x",
                    about=gettext(
                        "The DEM X coordinate for the outlet in pixels from the origin."
                    ),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="ds_y",
                    about=gettext(
                        "The DEM Y coordinate for the outlet in pixels from the origin."
                    ),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="ds_x_1",
                    about=gettext(
                        "The DEM X coordinate that is 1 pixel upstream from the outlet."
                    ),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="ds_y_1",
                    about=gettext(
                        "The DEM Y coordinate that is 1 pixel upstream from the outlet."
                    ),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="us_x",
                    about=gettext("The DEM X coordinate for the upstream inlet."),
                    units=u.pixel
                ),
                spec.NumberOutput(
                    id="us_y",
                    about=gettext("The DEM Y coordinate for the upstream inlet."),
                    units=u.pixel
                )
            ]
        ),
        spec.VectorOutput(
            id="subwatersheds_[TFA]",
            path="subwatersheds_tfa_[TFA].gpkg",
            about=gettext(
                "A GeoPackage with polygon features representing subwatersheds.  A new"
                " subwatershed is created for each tributary of a stream and is"
                " influenced greatly by your choice of Threshold Flow Accumulation value."
            ),
            created_if="algorithm == 'd8' and calculate_subwatersheds",
            geometry_types={"POLYGON"},
            fields=[
                spec.NumberOutput(
                    id="stream_id",
                    about=gettext(
                        "A unique stream id, matching the one in the Strahler stream"
                        " order vector."
                    ),
                    units=u.none
                ),
                spec.NumberOutput(
                    id="terminated_early",
                    about=gettext(
                        "Indicates whether generation of this subwatershed terminated"
                        " early (1) or completed as expected (0). If you encounter a (1),"
                        " please let us know via the forums,"
                        " community.naturalcapitalproject.org."
                    ),
                    units=u.none
                ),
                spec.NumberOutput(
                    id="outlet_x",
                    about=gettext(
                        "The X coordinate in pixels from the origin of the outlet of the"
                        " watershed. This can be useful when determining other properties"
                        " of the watershed when indexing with the underlying raster data."
                    ),
                    units=u.none
                ),
                spec.NumberOutput(
                    id="outlet_y",
                    about=gettext(
                        "The X coordinate in pixels from the origin of the outlet of the"
                        " watershed. This can be useful when determining other properties"
                        " of the watershed when indexing with the underlying raster data."
                    ),
                    units=u.none
                )
            ]
        ),
        spec.SingleBandRasterOutput(
            id="downslope_distance_[TFA]",
            path="downslope_distance_tfa_[TFA].tif",
            about=gettext("Flow distance from each pixel to a stream."),
            data_type=float,
            units=u.pixel
        )
    ]
)


_ROUTING_FUNCS = {
    'd8': {
        'flow_accumulation': pygeoprocessing.routing.flow_accumulation_d8,
        'flow_direction': pygeoprocessing.routing.flow_dir_d8,
        'threshold_flow': pygeoprocessing.routing.extract_streams_d8,
        'distance_to_channel': pygeoprocessing.routing.distance_to_channel_d8,
    },
    'mfd': {
        'flow_accumulation': pygeoprocessing.routing.flow_accumulation_mfd,
        'flow_direction': pygeoprocessing.routing.flow_dir_mfd,
        'threshold_flow': pygeoprocessing.routing.extract_streams_mfd,
        'distance_to_channel': pygeoprocessing.routing.distance_to_channel_mfd,
    }
}


def execute(args):
    """RouteDEM: Hydrological routing.

    This model exposes the pygeoprocessing D8 and Multiple Flow Direction
    routing functionality as an InVEST model.

    This tool will always fill pits on the input DEM.

    Args:
        args['workspace_dir'] (string): output directory for intermediate,
            temporary, and final files
        args['results_suffix'] (string): (optional) string to append to any
            output file names
        args['dem_path'] (string): path to a digital elevation raster
        args['dem_band_index'] (int): Optional. The band index to operate on.
            If not provided, band index 1 is assumed.
        args['algorithm'] (string): The routing algorithm to use.  Must be
            one of 'D8' or 'MFD' (case-insensitive). Required when calculating
            flow direction, flow accumulation, stream threshold, and downslope
            distance.
        args['threshold_flow_accumulation_range'] (string): A range for the number
            of upslope cells that must flow into a cell before it is classified
            as a stream. Must be of the form ``start_value:stop_value:step_value``.
        args['calculate_downslope_distance'] (bool): If True, and a stream
            threshold is calculated, model will calculate a downslope
            distance raster in units of pixels.
        args['calculate_slope'] (bool): If True, model will calculate a
            slope raster from the DEM.
        args['calculate_stream_order']: If True, model will create a vector of
            the Strahler stream order.
        args['calculate_subwatersheds']: If True, the model will create a
            vector of subwatersheds.
        args['n_workers'] (int): The ``n_workers`` parameter to pass to
            the task graph.  The default is ``-1`` if not provided.

    Returns:
        File registry dictionary mapping MODEL_SPEC output ids to absolute paths
    """
    args, file_registry, graph = MODEL_SPEC.setup(args)

    routing_funcs = _ROUTING_FUNCS[args['algorithm']]

    band_index = args['dem_band_index'] if args['dem_band_index'] else 1

    LOGGER.info('Using DEM band index %s', band_index)

    dem_raster_path_band = (args['dem_path'], band_index)

    # Calculate slope. This is intentionally on the original DEM, not
    # on the pitfilled DEM. If the user really wants the slop of the filled
    # DEM, they can pass it back through RouteDEM.
    if args['calculate_slope']:
        graph.add_task(
            pygeoprocessing.calculate_slope,
            args=(dem_raster_path_band, file_registry['slope']),
            task_name='calculate_slope',
            target_path_list=[file_registry['slope']])

    filled_pits_task = graph.add_task(
        pygeoprocessing.routing.fill_pits,
        args=(dem_raster_path_band,
              file_registry['filled'],
              args['workspace_dir']),
        task_name='fill_pits',
        target_path_list=[file_registry['filled']])

    LOGGER.info("calculating flow direction")
    flow_direction_task = graph.add_task(
        routing_funcs['flow_direction'],
        args=((file_registry['filled'], 1),  # PGP>1.9.0 creates 1-band fills
              file_registry['flow_direction'],
              args['workspace_dir']),
        target_path_list=[file_registry['flow_direction']],
        dependent_task_list=[filled_pits_task],
        task_name=f'flow_dir_{args["algorithm"]}')

    LOGGER.info("calculating flow accumulation")
    flow_accum_task = graph.add_task(
        routing_funcs['flow_accumulation'],
        args=((file_registry['flow_direction'], 1), file_registry['flow_accumulation']),
        target_path_list=[file_registry['flow_accumulation']],
        task_name=f'flow_accumulation_{args["algorithm"]}',
        dependent_task_list=[flow_direction_task])

    flow_threshold_range = _convert_to_range(args['threshold_flow_accumulation_range'])
    flow_threshold_values = list(flow_threshold_range)
    LOGGER.info(f"flow threshold values: {flow_threshold_values}")

    for flow_threshold in flow_threshold_values:
        LOGGER.info(f"calculating for flow threshold value {flow_threshold}")
        stream_extraction_kwargs = {
            'flow_accum_raster_path_band': (file_registry['flow_accumulation'], 1),
            'flow_threshold': flow_threshold,
            'target_stream_raster_path': file_registry['stream_mask_[TFA]', flow_threshold],
        }
        if args['algorithm'] == 'mfd':
            stream_extraction_kwargs['flow_dir_mfd_path_band'] = (
                file_registry['flow_direction'], 1)
        stream_threshold_task = graph.add_task(
            routing_funcs['threshold_flow'],
            kwargs=stream_extraction_kwargs,
            target_path_list=[file_registry['stream_mask_[TFA]', flow_threshold]],
            dependent_task_list=[flow_accum_task],
            task_name=f'stream_thresholding_{args["algorithm"]}_{flow_threshold}')

        if args['calculate_downslope_distance']:
            graph.add_task(
                routing_funcs['distance_to_channel'],
                args=((file_registry['flow_direction'], 1),
                      (file_registry['stream_mask_[TFA]', flow_threshold], 1),
                      file_registry['downslope_distance_[TFA]', flow_threshold]),
                target_path_list=[file_registry['downslope_distance_[TFA]', flow_threshold]],
                task_name=f'downslope_distance_{args["algorithm"]}_{flow_threshold}',
                dependent_task_list=[stream_threshold_task])

        if args['calculate_stream_order'] and args['algorithm'] == 'd8':
            stream_order_task = graph.add_task(
                pygeoprocessing.routing.extract_strahler_streams_d8,
                kwargs={
                    "flow_dir_d8_raster_path_band":
                        (file_registry['flow_direction'], 1),
                    "flow_accum_raster_path_band":
                        (file_registry['flow_accumulation'], 1),
                    "dem_raster_path_band":
                        (file_registry['filled'], 1),
                    "target_stream_vector_path":
                        file_registry['strahler_stream_order_[TFA]', flow_threshold],
                    "min_flow_accum_threshold": flow_threshold,
                    "river_order": 5,  # the default
                },
                target_path_list=[
                    file_registry['strahler_stream_order_[TFA]', flow_threshold]
                ],
                task_name=f'Calculate D8 stream order_{flow_threshold}',
                dependent_task_list=[
                    filled_pits_task,
                    flow_direction_task,
                    flow_accum_task
                ])

            if args['calculate_subwatersheds']:
                graph.add_task(
                    pygeoprocessing.routing.calculate_subwatershed_boundary,
                    kwargs={
                        'd8_flow_dir_raster_path_band':
                            (file_registry['flow_direction'], 1),
                        'strahler_stream_vector_path':
                            file_registry['strahler_stream_order_[TFA]', flow_threshold],
                        'target_watershed_boundary_vector_path':
                            file_registry['subwatersheds_[TFA]', flow_threshold],
                        'outlet_at_confluence': False,  # The default
                    },
                    target_path_list=[file_registry['subwatersheds_[TFA]', flow_threshold]],
                    task_name=(
                        f'Calculate subwatersheds from stream order_{flow_threshold}'),
                    dependent_task_list=[flow_direction_task,
                                         stream_order_task])

    graph.close()
    graph.join()
    return file_registry.registry


def _convert_to_range(range_str):
    split_str = range_str.split(':')
    _range = range(
        int(split_str[0]), int(split_str[1]), int(split_str[2]))
    return _range


@validation.invest_validator
def validate(args, limit_to=None):
    """Validate args to ensure they conform to ``execute``'s contract.

    Args:
        args (dict): dictionary of key(str)/value pairs where keys and
            values are specified in ``execute`` docstring.
        limit_to (str): (optional) if not None indicates that validation
            should only occur on the args[limit_to] value. The intent that
            individual key validation could be significantly less expensive
            than validating the entire ``args`` dictionary.

    Returns:
        list of ([invalid key_a, invalid key_b, ...], 'warning/error message')
            tuples. Where an entry indicates that the invalid keys caused
            the error message in the second part of the tuple. This should
            be an empty list if validation succeeds.
    """
    validation_warnings = validation.validate(args, MODEL_SPEC)

    invalid_keys = validation.get_invalid_keys(validation_warnings)
    sufficient_keys = validation.get_sufficient_keys(args)

    if ('dem_band_index' not in invalid_keys and
            'dem_band_index' in sufficient_keys and
            'dem_path' not in invalid_keys and
            'dem_path' in sufficient_keys):
        raster_info = pygeoprocessing.get_raster_info(args['dem_path'])
        if int(args['dem_band_index']) > raster_info['n_bands']:
            validation_warnings.append((
                ['dem_band_index'],
                INVALID_BAND_INDEX_MSG.format(maximum=raster_info['n_bands'])))

    if 'threshold_flow_accumulation_range' not in invalid_keys:
        _range = _convert_to_range(args['threshold_flow_accumulation_range'])
        if not list(_range):
            validation_warnings.append((
                ['threshold_flow_accumulation_range'], INVALID_RANGE_MSG))

    return validation_warnings
