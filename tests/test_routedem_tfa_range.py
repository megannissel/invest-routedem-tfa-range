"""Tests for InVEST Plugin: RouteDEM with TFA Range Input."""
import collections
import os
import shutil
import tempfile
import unittest

import numpy
from osgeo import gdal
from osgeo import osr

gdal.UseExceptions()


class RouteDEMTFARangeTests(unittest.TestCase):
    """Tests for RouteDEM with Pygeoprocessing 1.x routing API."""

    def setUp(self):
        """Overriding setUp function to create temp workspace directory."""
        # this lets us delete the workspace after its done no matter the
        # the rest result
        self.workspace_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Overriding tearDown function to remove temporary directory."""
        shutil.rmtree(self.workspace_dir)

    @staticmethod
    def _make_dem(target_path):
        # makes a 10x9 DEM with a valley in the middle that flows to row 0.
        elevation = numpy.arange(1.1, 2, step=0.1).reshape((9, 1))
        valley = numpy.concatenate((
            numpy.flipud(numpy.arange(5)),
            numpy.arange(1, 5)))
        valley_with_sink = numpy.array([5, 4, 3, 2, 1.3, 1.3, 3, 4, 5])

        dem_array = numpy.vstack((
            valley_with_sink,
            numpy.tile(valley, (9, 1)) + elevation))
        nodata_value = -1

        srs = osr.SpatialReference()
        srs.ImportFromEPSG(32731)
        srs_wkt = srs.ExportToWkt()

        driver = gdal.GetDriverByName('GTiff')
        dem_raster = driver.Create(
            target_path, dem_array.shape[1], dem_array.shape[0],
            2, gdal.GDT_Float32, options=(
                'TILED=YES', 'BIGTIFF=YES', 'COMPRESS=LZW',
                'BLOCKXSIZE=256', 'BLOCKYSIZE=256'))
        dem_raster.SetProjection(srs_wkt)
        ones_band = dem_raster.GetRasterBand(1)
        ones_band.SetNoDataValue(nodata_value)
        ones_band.WriteArray(numpy.ones(dem_array.shape))

        dem_band = dem_raster.GetRasterBand(2)
        dem_band.SetNoDataValue(nodata_value)
        dem_band.WriteArray(dem_array)
        dem_geotransform = [2, 2, 0, -2, 0, -2]
        dem_raster.SetGeoTransform(dem_geotransform)
        dem_raster = None

    def test_routedem_expected_outputs_d8(self):
        """RouteDEM: check expected outputs d8."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        args = {
            'workspace_dir': self.workspace_dir,
            'algorithm': 'd8',
            'dem_path': os.path.join(self.workspace_dir, 'dem.tif'),
            'dem_band_index': 2,
            'results_suffix': 'foo',
            'calculate_flow_direction': True,
            'calculate_flow_accumulation': True,
            'calculate_stream_threshold': True,
            'calculate_downslope_distance': True,
            'calculate_slope': True,
            'calculate_stream_order': True,
            'calculate_subwatersheds': True,
            'threshold_flow_accumulation_range': '2:5:2',
        }

        RouteDEMTFARangeTests._make_dem(args['dem_path'])
        routedem.MODEL_SPEC.execute(args, check_outputs=True)

        for expected_file in (
                'downslope_distance_tfa_2_foo.tif',
                'downslope_distance_tfa_4_foo.tif',
                'filled_foo.tif',
                'flow_accumulation_foo.tif',
                'flow_direction_foo.tif',
                'slope_foo.tif',
                'stream_mask_tfa_2_foo.tif',
                'stream_mask_tfa_4_foo.tif',
                'strahler_stream_order_tfa_2_foo.gpkg',
                'strahler_stream_order_tfa_4_foo.gpkg',
                'subwatersheds_tfa_2_foo.gpkg',
                'subwatersheds_tfa_4_foo.gpkg'):
            self.assertTrue(
                os.path.exists(
                    os.path.join(args['workspace_dir'], expected_file)),
                'File not found: %s' % expected_file)

    def test_routedem_expected_outputs_mfd(self):
        """RouteDEM: check expected outputs mfd."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        args = {
            'workspace_dir': self.workspace_dir,
            'algorithm': 'mfd',
            'dem_path': os.path.join(self.workspace_dir, 'dem.tif'),
            'dem_band_index': 2,
            'results_suffix': 'foo',
            'calculate_flow_direction': True,
            'calculate_flow_accumulation': True,
            'calculate_stream_threshold': True,
            'calculate_downslope_distance': True,
            'calculate_slope': False,
            'calculate_stream_order': True,  # make sure file not created
            'calculate_subwatersheds': True,  # make sure file not created
            'threshold_flow_accumulation_range': '2:5:2',
        }
        RouteDEMTFARangeTests._make_dem(args['dem_path'])
        routedem.MODEL_SPEC.execute(args, check_outputs=True)

        for expected_file in (
                'downslope_distance_tfa_2_foo.tif',
                'downslope_distance_tfa_4_foo.tif',
                'filled_foo.tif',
                'flow_accumulation_foo.tif',
                'flow_direction_foo.tif',
                'stream_mask_tfa_2_foo.tif',
                'stream_mask_tfa_4_foo.tif'):
            self.assertTrue(
                os.path.exists(
                    os.path.join(args['workspace_dir'], expected_file)),
                'File not found: %s' % expected_file)

        for tfa in [2, 4]:
            self.assertFalse(os.path.exists(os.path.join(
                args['workspace_dir'], 'strahler_stream_order_tfa_{tfa}_foo.gpkg')))
            self.assertFalse(os.path.exists(os.path.join(
                args['workspace_dir'], 'subwatersheds_tfa_{tfa}_foo.gpkg')))

    def test_routedem_default_band(self):
        """RouteDEM: default to band 1 when not specified."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem

        # Intentionally leaving out the dem_band_index parameter,
        # should default to band 1.
        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'dem.tif'),
            'results_suffix': 'foo',
            'algorithm': 'd8',
            'threshold_flow_accumulation_range': '2:4:1'
        }
        RouteDEMTFARangeTests._make_dem(args['dem_path'])
        routedem.execute(args)

        filled_raster_path = os.path.join(
            args['workspace_dir'], 'filled_foo.tif')
        self.assertTrue(
            os.path.exists(filled_raster_path),
            'Filled DEM not created.')

        # The first band has only values of 1, no hydrological pits.
        # So, the filled band should match the source band.
        expected_filled_array = gdal.OpenEx(args['dem_path']).ReadAsArray()[0]
        filled_array = gdal.OpenEx(filled_raster_path).ReadAsArray()
        numpy.testing.assert_allclose(
            expected_filled_array,
            filled_array,
            rtol=0, atol=1e-6)

    def test_routedem_pitfilling(self):
        """RouteDEM: assert pitfilling when no other options given."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'dem.tif'),
            'dem_band_index': 2,
            'results_suffix': 'foo',
            'algorithm': 'd8',
            'threshold_flow_accumulation_range': '2:4:1'
        }
        RouteDEMTFARangeTests._make_dem(args['dem_path'])
        routedem.execute(args)

        filled_raster_path = os.path.join(
            args['workspace_dir'], 'filled_foo.tif')
        self.assertTrue(
            os.path.exists(filled_raster_path),
            'Filled DEM not created.')

        # The one sink in the array should have been filled to 1.3.
        expected_filled_array = gdal.OpenEx(args['dem_path']).ReadAsArray()[1]
        expected_filled_array[expected_filled_array < 1.3] = 1.3

        # Filled rasters are copies of only the desired band of the input DEM,
        # and then with pixels filled.
        filled_array = gdal.OpenEx(filled_raster_path).ReadAsArray()
        numpy.testing.assert_allclose(
            expected_filled_array,
            filled_array,
            rtol=0, atol=1e-6)

    def test_routedem_slope(self):
        """RouteDEM: assert slope option."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'dem.tif'),
            'dem_band_index': 2,
            'results_suffix': 'foo',
            'calculate_slope': True,
            'algorithm': 'd8',
            'threshold_flow_accumulation_range': '2:4:1'
        }
        RouteDEMTFARangeTests._make_dem(args['dem_path'])
        routedem.execute(args)

        for path in ('filled_foo.tif', 'slope_foo.tif'):
            self.assertTrue(os.path.exists(
                os.path.join(args['workspace_dir'], path)),
                'File not found: %s' % path)

        slope_array = gdal.OpenEx(
            os.path.join(args['workspace_dir'], 'slope_foo.tif')).ReadAsArray()
        # These were determined by inspection of the output array.
        expected_unique_values = numpy.array(
            [4.999998,  4.9999995, 5.000001, 5.0000043, 7.126098,
             13.235317, 45.017357, 48.226353, 48.75, 49.56845,
             50.249374, 50.24938, 50.249382, 55.17727, 63.18101],
            dtype=numpy.float32).reshape((15,))
        numpy.testing.assert_allclose(
            expected_unique_values,
            numpy.unique(slope_array),
            rtol=0, atol=1e-6)
        numpy.testing.assert_allclose(
            numpy.sum(slope_array), 4088.7358, rtol=0, atol=1e-4)

    def test_routedem_d8(self):
        """RouteDEM: test d8 routing."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        args = {
            'workspace_dir': self.workspace_dir,
            'algorithm': 'd8',
            'dem_path': os.path.join(self.workspace_dir, 'dem.tif'),
            'dem_band_index': 2,
            'results_suffix': 'foo',
            'calculate_flow_direction': True,
            'calculate_flow_accumulation': True,
            'calculate_stream_threshold': True,
            'calculate_downslope_distance': True,
            'calculate_slope': True,
            'calculate_stream_order': True,
            'calculate_subwatersheds': True,
            'threshold_flow_accumulation_range': '2:5:2',
        }

        RouteDEMTFARangeTests._make_dem(args['dem_path'])
        routedem.execute(args)

        # Check Flow Accumulation
        expected_flow_accum = numpy.empty((10, 9), dtype=numpy.float64)
        expected_flow_accum[:, 0:4] = numpy.arange(1, 5)
        expected_flow_accum[:, 5:9] = numpy.flipud(numpy.arange(1, 5))
        expected_flow_accum[:, 4] = numpy.array(
            [82, 77, 72, 63, 54, 45, 36, 27, 18, 9])
        expected_flow_accum[1, 5] = 1
        expected_flow_accum[0, 5] = 8

        numpy.testing.assert_allclose(
            expected_flow_accum,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'],
                'flow_accumulation_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        # Check Flow Direction
        expected_flow_direction = numpy.empty((10, 9), dtype=numpy.uint8)
        expected_flow_direction[:, 0:4] = 0
        expected_flow_direction[:, 5:9] = 4
        expected_flow_direction[:, 4] = 2
        expected_flow_direction[0:2, 5] = 2
        expected_flow_direction[1, 6] = 3

        numpy.testing.assert_allclose(
            expected_flow_direction,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'],
                'flow_direction_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        # Check Stream Masks
        expected_stream_mask_2 = numpy.zeros((10, 9), dtype=numpy.uint8)
        expected_stream_mask_2[:, 2:7] = 1
        expected_stream_mask_2[1, 5] = 0
        numpy.testing.assert_allclose(
            expected_stream_mask_2,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'], 'stream_mask_tfa_2_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        expected_stream_mask_4 = numpy.zeros((10, 9), dtype=numpy.uint8)
        expected_stream_mask_4[:, 4] = 1
        expected_stream_mask_4[0, 5] = 1
        numpy.testing.assert_allclose(
            expected_stream_mask_4,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'], 'stream_mask_tfa_4_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        # Check Downslope Distance
        expected_downslope_distance_2 = numpy.zeros(
            (10, 9), dtype=numpy.float64)
        expected_downslope_distance_2[:, 0:3] = numpy.flipud(numpy.arange(3))
        expected_downslope_distance_2[:, 7:] = numpy.arange(1, 3)
        expected_downslope_distance_2[1, 5] = 1

        numpy.testing.assert_allclose(
            expected_downslope_distance_2,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'],
                'downslope_distance_tfa_2_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        expected_downslope_distance_4 = numpy.empty(
            (10, 9), dtype=numpy.float64)
        expected_downslope_distance_4[:, 0:5] = numpy.flipud(numpy.arange(5))
        expected_downslope_distance_4[2:, 5:] = numpy.arange(1, 5)
        expected_downslope_distance_4[0, 5:] = numpy.arange(4)
        expected_downslope_distance_4[1, 5] = 1
        expected_downslope_distance_4[1, 6:] = numpy.arange(1, 4) + 0.41421356

        numpy.testing.assert_allclose(
            expected_downslope_distance_4,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'],
                'downslope_distance_tfa_4_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        vector_outputs = [
            {
                'tfa': 2,
                'strahler_feature_count': 29,
                'strahler_features_per_order': {1: 20, 2:9},
                'subwatershed_feature_count': 27,
                'subwatershed_features_by_area': {16: 17, 4: 8, 24: 1, 32: 1} 
            },
            {
                'tfa': 4,
                'strahler_feature_count': 27,
                'strahler_features_per_order': {1: 18, 2:9},
                'subwatershed_feature_count': 26,
                'subwatershed_features_by_area': {16: 17, 4: 8, 24: 1}
            }
        ]
        for expected_outputs in vector_outputs:
            # Check Strahler Stream Order
            try:
                vector = gdal.OpenEx(os.path.join(
                    args['workspace_dir'],
                    f"strahler_stream_order_tfa_{expected_outputs['tfa']}_foo.gpkg"))
                layer = vector.GetLayer()
                self.assertEqual(expected_outputs['strahler_feature_count'],
                                 layer.GetFeatureCount())
                features_per_order = collections.defaultdict(int)
                for feature in layer:
                    order = feature.GetField('order')
                    features_per_order[order] += 1
                self.assertEqual(dict(features_per_order),
                                 expected_outputs['strahler_features_per_order'])
            finally:
                layer = None
                vector = None

            # Check Subwatersheds
            try:
                vector = gdal.OpenEx(os.path.join(
                    args['workspace_dir'],
                    f"subwatersheds_tfa_{expected_outputs['tfa']}_foo.gpkg"))
                layer = vector.GetLayer()
                self.assertEqual(expected_outputs['subwatershed_feature_count'],
                                 layer.GetFeatureCount())
                features_by_area = collections.defaultdict(int)
                for feature in layer:
                    geometry = feature.GetGeometryRef()
                    area = geometry.GetArea()
                    features_by_area[area] += 1
                self.assertEqual(dict(features_by_area),
                                 expected_outputs['subwatershed_features_by_area'])
            finally:
                layer = None
                vector = None

    def test_routedem_mfd(self):
        """RouteDEM: test mfd routing."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        args = {
            'workspace_dir': self.workspace_dir,
            'algorithm': 'mfd',
            'dem_path': os.path.join(self.workspace_dir, 'dem.tif'),
            'dem_band_index': 2,
            'results_suffix': 'foo',
            'calculate_flow_direction': True,
            'calculate_flow_accumulation': True,
            'calculate_stream_threshold': True,
            'calculate_downslope_distance': True,
            'calculate_slope': False,
            'calculate_stream_order': True,  # make sure file not created
            'calculate_subwatersheds': True,  # make sure file not created
            'threshold_flow_accumulation_range': '2:5:2',
        }

        RouteDEMTFARangeTests._make_dem(args['dem_path'])
        routedem.execute(args)

        expected_stream_mask_2 = numpy.zeros((10, 9), dtype=numpy.uint8)
        expected_stream_mask_2[:9, 1:8] = 1
        expected_stream_mask_2[9, 2:7] = 1
        numpy.testing.assert_allclose(
            expected_stream_mask_2,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'], 'stream_mask_tfa_2_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        expected_stream_mask_4 = numpy.zeros((10, 9), dtype=numpy.uint8)
        expected_stream_mask_4[:9, 3:6] = 1
        expected_stream_mask_4[9, 4] = 1
        numpy.testing.assert_allclose(
            expected_stream_mask_4,
            gdal.OpenEx(os.path.join(
                args['workspace_dir'], 'stream_mask_tfa_4_foo.tif')).ReadAsArray(),
            rtol=0, atol=1e-6)

        # Raster sums are from manually-inspected outputs.
        for filename, expected_sum in (
                ('flow_accumulation_foo.tif', 678.94551294),
                ('flow_direction_foo.tif', 40968303668.0),
                ('downslope_distance_tfa_2_foo.tif', 30.05775078),
                ('downslope_distance_tfa_4_foo.tif', 162.28624753707527)):
            raster_path = os.path.join(args['workspace_dir'], filename)
            raster = gdal.OpenEx(raster_path)
            if raster is None:
                self.fail('Could not open raster %s' % filename)

            self.assertEqual(raster.RasterYSize, expected_stream_mask_2.shape[0])
            self.assertEqual(raster.RasterXSize, expected_stream_mask_2.shape[1])

            raster_sum = numpy.sum(raster.ReadAsArray(), dtype=numpy.float64)
            numpy.testing.assert_allclose(
                raster_sum, expected_sum, rtol=0, atol=1e-6)

    def test_validation_required_args(self):
        """RouteDEM: test required args in validation."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        args = {}
        required_keys = [
            'workspace_dir', 'dem_path', 'algorithm',
            'threshold_flow_accumulation_range']

        validation_warnings = routedem.validate(args)
        invalid_keys = validation.get_invalid_keys(validation_warnings)
        for key in required_keys:
            self.assertTrue(key in invalid_keys)

    def test_validation_required_args_none(self):
        """RouteDEM: test validation of present but None args."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        required_keys = [
            'workspace_dir', 'dem_path', 'algorithm',
            'threshold_flow_accumulation_range']
        args = dict((k, None) for k in required_keys)

        validation_errors = routedem.validate(args)
        invalid_keys = validation.get_invalid_keys(validation_errors)
        self.assertEqual(invalid_keys, set(required_keys))

    def test_validation_required_args_empty(self):
        """RouteDEM: test validation of a present but empty args."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        required_keys = [
            'workspace_dir', 'dem_path', 'algorithm',
            'threshold_flow_accumulation_range']
        args = dict((k, '') for k in required_keys)

        validation_errors = routedem.validate(args)
        invalid_keys = validation.get_invalid_keys(validation_errors)
        self.assertEqual(invalid_keys, set(required_keys))

    def test_validation_invalid_raster(self):
        """RouteDEM: test validation of an invalid DEM."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'badraster.tif'),
        }

        with open(args['dem_path'], 'w') as bad_raster:
            bad_raster.write('This is an invalid raster format.')

        validation_errors = routedem.validate(args)
        invalid_keys = validation.get_invalid_keys(validation_errors)
        self.assertTrue('dem_path' in invalid_keys)

    def test_validation_band_index_type(self):
        """RouteDEM: test validation of an invalid band index."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'notafile.txt'),
            'dem_band_index': range(1, 5),
        }

        validation_errors = routedem.validate(args)
        invalid_keys = validation.get_invalid_keys(validation_errors)
        self.assertEqual(invalid_keys, set(['algorithm', 'dem_path',
                                            'dem_band_index',
                                            'threshold_flow_accumulation_range']))

    def test_validation_band_index_negative_value(self):
        """RouteDEM: test validation of a negative band index."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'notafile.txt'),
            'dem_band_index': -5,
        }

        validation_errors = routedem.validate(args)
        invalid_keys = validation.get_invalid_keys(validation_errors)
        self.assertEqual(invalid_keys, set(['dem_path', 'dem_band_index',
                                            'algorithm',
                                            'threshold_flow_accumulation_range']))

    def test_validation_band_index_value_too_large(self):
        """RouteDEM: test validation of a too-large band index."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'raster.tif'),
            'dem_band_index': 5,
        }

        # Has two bands, so band index 5 is too large.
        RouteDEMTFARangeTests._make_dem(args['dem_path'])

        validation_errors = routedem.validate(args)
        invalid_keys = validation.get_invalid_keys(validation_errors)

        self.assertEqual(invalid_keys, set(['algorithm', 'dem_band_index',
                                            'threshold_flow_accumulation_range']))

    def test_validation_tfa_range_invalid_string(self):
        """RouteDEM: test validation of TFA range invalid string input."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'raster.tif'),
            'dem_band_index': 1,
            'algorithm': 'd8',
        }

        RouteDEMTFARangeTests._make_dem(args['dem_path'])

        for invalid_range_string in ['2:5', '3:4:0']:
            args['threshold_flow_accumulation_range'] = invalid_range_string

            validation_errors = routedem.validate(args)
            invalid_keys = validation.get_invalid_keys(validation_errors)
            self.assertEqual(invalid_keys, set(['threshold_flow_accumulation_range']))

    def test_validation_tfa_range_empty_list(self):
        """RouteDEM: test validation of TFA range empty list."""
        from invest_routedem_tfa_range import invest_routedem_tfa_range as routedem
        from natcap.invest import validation

        args = {
            'workspace_dir': self.workspace_dir,
            'dem_path': os.path.join(self.workspace_dir, 'raster.tif'),
            'dem_band_index': 1,
            'algorithm': 'd8',
            'threshold_flow_accumulation_range': '5:1:2'
        }

        RouteDEMTFARangeTests._make_dem(args['dem_path'])

        validation_errors = routedem.validate(args)
        self.assertEqual(len(validation_errors), 1)
        self.assertIn('threshold_flow_accumulation_range', validation_errors[0][0])
        self.assertEqual(routedem.INVALID_RANGE_MSG, validation_errors[0][1])
        invalid_keys = validation.get_invalid_keys(validation_errors)
