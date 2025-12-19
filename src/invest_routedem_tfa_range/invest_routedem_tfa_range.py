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
from natcap.invest import routedem
from natcap.invest import spec
from natcap.invest import utils
from natcap.invest import validation
from natcap.invest.file_registry import FileRegistry
from natcap.invest.unit_registry import u

LOGGER = logging.getLogger(__name__)

INVALID_RANGE_MSG = gettext('Provided range contains zero items')

MODEL_SPEC = spec.ModelSpec(
    model_id="invest_routedem_tfa_range",
    model_title=gettext("RouteDEM with TFA Range"),
    userguide="https://github.com/natcap/invest-routedem-tfa-range/blob/main/README.md",
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
        routedem.MODEL_SPEC.get_input("dem_path"),
        routedem.MODEL_SPEC.get_input("dem_band_index"),
        routedem.MODEL_SPEC.get_input("algorithm"),
        spec.StringInput(
            id="threshold_flow_accumulation_range",
            name=gettext("threshold flow accumulation value range"),
            about=gettext(
                "A range for the number of upslope pixels that must flow into a pixel"
                " before it is classified as a stream. Must be of the form"
                " ``start_value:stop_value:step_value``. The model will calculate results"
                " for each value in this range. For example, with a range input of"
                " ``1000:2000:500``, the model will calculate results for threshold"
                " flow accumulation values of 1000 and 1500. Please note that the stop"
                " value is not inclusive."
            ),
            display_name="start_value:stop_value:step_value",
            regexp="^[0-9]+:[0-9]+:[1-9][0-9]*$"
        ),
        routedem.MODEL_SPEC.get_input("calculate_downslope_distance").model_copy(
            update=dict(allowed=True)
        ),
        routedem.MODEL_SPEC.get_input("calculate_slope"),
        routedem.MODEL_SPEC.get_input("calculate_stream_order").model_copy(
            update=dict(allowed="algorithm == 'D8'")
        ),
        routedem.MODEL_SPEC.get_input("calculate_subwatersheds"),
    ],
    outputs=[
        spec.TASKGRAPH_CACHE,
        routedem.MODEL_SPEC.get_output("filled"),
        spec.FLOW_ACCUMULATION,
        spec.FLOW_DIRECTION,
        spec.SLOPE.model_copy(update=dict(
            created_if='calculate_slope')),
        spec.STREAM.model_copy(update=dict(
            id="stream_[TFA]",
            path="stream_tfa_[TFA].tif")),
        routedem.MODEL_SPEC.get_output("strahler_stream_order").model_copy(update=dict(
            id="strahler_stream_order_[TFA]",
            path="strahler_stream_order_tfa_[TFA].gpkg",
            created_if="algorithm == 'd8' and calculate_stream_order"
        )),
        routedem.MODEL_SPEC.get_output("subwatersheds").model_copy(update=dict(
            id="subwatersheds_[TFA]",
            path="subwatersheds_tfa_[TFA].gpkg",
            created_if="algorithm == 'd8' and calculate_subwatersheds"
        )),
        routedem.MODEL_SPEC.get_output("downslope_distance").model_copy(update=dict(
            id="downslope_distance_[TFA]",
            path="downslope_distance_tfa_[TFA].tif",
            created_if="calculate_downslope_distance"
        ))
    ]
)


def execute(args):
    """RouteDEM (hydrological routing) with Threshold Flow Accumulation Range.

    This plugin provides a modified version of the InVEST RouteDEM utility.
    RouteDEM exposes the pygeoprocessing D8 and Multiple Flow Direction routing
    functionality as an InVEST model. This version includes a "Threshold Flow
    Accumulation Range" input, which allows it to compute outputs for a range of
    TFAs in a single run.

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

    routing_funcs = routedem._ROUTING_FUNCS[args['algorithm']]

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
            'target_stream_raster_path': file_registry['stream_[TFA]', flow_threshold],
        }
        if args['algorithm'] == 'mfd':
            stream_extraction_kwargs['flow_dir_mfd_path_band'] = (
                file_registry['flow_direction'], 1)
        stream_threshold_task = graph.add_task(
            routing_funcs['threshold_flow'],
            kwargs=stream_extraction_kwargs,
            target_path_list=[file_registry['stream_[TFA]', flow_threshold]],
            dependent_task_list=[flow_accum_task],
            task_name=f'stream_thresholding_{args["algorithm"]}_{flow_threshold}')

        if args['calculate_downslope_distance']:
            graph.add_task(
                routing_funcs['distance_to_channel'],
                args=((file_registry['flow_direction'], 1),
                      (file_registry['stream_[TFA]', flow_threshold], 1),
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
                routedem.INVALID_BAND_INDEX_MSG.format(maximum=raster_info['n_bands'])))

    if 'threshold_flow_accumulation_range' not in invalid_keys:
        _range = _convert_to_range(args['threshold_flow_accumulation_range'])
        if not list(_range):
            validation_warnings.append((
                ['threshold_flow_accumulation_range'], INVALID_RANGE_MSG))

    return validation_warnings
