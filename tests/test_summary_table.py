import tempfile
import unittest
from pathlib import Path

from osgeo import ogr

from terasy_eval.summary_table import write_gpkg_table


class SummaryTableTests(unittest.TestCase):
    def test_creates_and_replaces_rows_without_removing_other_layers(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = str(Path(temporary_directory) / "results.gpkg")
            rows = [
                {"model": "model-a", "TP": 4, "precision": 0.8, "prah": "already applied"},
                {"model": "model-b", "TP": 6, "precision": 0.9, "prah": "already applied"},
            ]
            write_gpkg_table(path, "vysledky", rows)

            dataset = ogr.Open(path, 1)
            keep_layer = dataset.CreateLayer("keep", geom_type=ogr.wkbNone)
            keep_layer.CreateField(ogr.FieldDefn("note", ogr.OFTString))
            dataset = None

            updated_rows = [{**rows[0], "TP": 7}]
            write_gpkg_table(path, "vysledky", updated_rows)

            dataset = ogr.Open(path, 0)
            self.assertIsNotNone(dataset.GetLayerByName("keep"))
            results = dataset.GetLayerByName("vysledky")
            self.assertEqual(results.GetFeatureCount(), 1)
            feature = results.GetNextFeature()
            self.assertEqual(feature.GetField("TP"), 7)
            self.assertEqual(feature.GetField("precision"), 0.8)
            self.assertEqual(feature.GetField("prah"), "already applied")
            dataset = None


if __name__ == "__main__":
    unittest.main()