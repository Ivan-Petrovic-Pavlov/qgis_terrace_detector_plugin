import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from terasy_eval.model_config import read_model_bundle, validate_model_config
from terasy_eval.model_runner import preprocess_patch, resolve_checkpoint_path


class ModelConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schema_version": 1,
            "name": "Test bundle",
            "checkpoint": "model.pth",
            "inference_script": "model_runner.py",
            "model": {"architecture": "FPN", "encoder": "resnet34"},
            "input": {
                "type": "dem",
                "channels": 1,
                "description": "One-band DEM",
                "preprocessing": "dem_per_patch",
            },
            "inference": {"threshold": 0.2},
        }

    def test_accepts_configured_default_threshold(self):
        validated = validate_model_config(self.config)
        self.assertEqual(validated["inference"]["threshold"], 0.2)
        self.assertEqual(validated["inference"]["patch_size"], 256)

    def test_rejects_input_band_mismatch(self):
        self.config["input"]["bands"] = [1, 2, 3]
        with self.assertRaises(ValueError):
            validate_model_config(self.config)

    def test_dem_preprocessing_ignores_nodata_when_calculating_mean(self):
        bands = [[[10.0, 15.0], [20.0, -9999.0]]]
        config = {"input": {
            "preprocessing": "dem_per_patch",
            "preprocessing_options": {"scale_m": 5.0},
        }}
        result = preprocess_patch(config, bands, [-9999.0])
        self.assertEqual(result.shape, (1, 2, 2))
        self.assertEqual(result.tolist(), [[[-1.0, 0.0], [1.0, 0.0]]])

    def test_rejects_archive_path_traversal(self):
        self.config["checkpoint"] = "../model.pth"
        with self.assertRaises(ValueError):
            validate_model_config(self.config)

    def test_reads_a_complete_model_bundle(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            bundle_path = Path(temporary_directory) / "model.zip"
            with zipfile.ZipFile(bundle_path, "w") as bundle:
                bundle.writestr("config.json", json.dumps(self.config))
                bundle.writestr("model.pth", b"test weights")
                bundle.writestr("model_runner.py", "def load_model(*args): pass\n")
            self.assertEqual(read_model_bundle(bundle_path)["model"]["architecture"], "FPN")

    def test_accepts_site_specific_checkpoints_and_thresholds(self):
        self.config["checkpoint"] = "sitno.pth"
        self.config["additional_checkpoints"] = ["sasovske.pth", "ladzany.pth"]
        self.config["site_checkpoints"] = {
            "Hradisko_Sitno": "sitno.pth",
            "Hradisko_Sasovske_Podhradie": "sasovske.pth",
            "Hradisko_Ladzany": "ladzany.pth",
        }
        self.config["inference"]["thresholds_by_site"] = {
            "Hradisko_Sitno": 0.4,
            "Hradisko_Sasovske_Podhradie": 0.05,
            "Hradisko_Ladzany": 0.2,
        }
        self.assertEqual(
            validate_model_config(self.config)["site_checkpoints"]["Hradisko_Ladzany"],
            "ladzany.pth",
        )

    def test_rejects_site_checkpoint_not_in_bundle(self):
        self.config["site_checkpoints"] = {"Hradisko_Sitno": "missing.pth"}
        with self.assertRaises(ValueError):
            validate_model_config(self.config)

    def test_rejects_threshold_for_unknown_site(self):
        self.config["site_checkpoints"] = {"Hradisko_Sitno": "model.pth"}
        self.config["inference"]["thresholds_by_site"] = {"Hradisko_Ladzany": 0.2}
        with self.assertRaises(ValueError):
            validate_model_config(self.config)

    def test_runner_resolves_the_selected_site_checkpoint(self):
        config = {
            "site_checkpoints": {
                "Hradisko_Sitno": "sitno.pth",
                "Hradisko_Ladzany": "ladzany.pth",
            },
            "selected_site": "Hradisko_Ladzany",
        }
        checkpoint = resolve_checkpoint_path(config, "/tmp/model/sitno.pth")
        self.assertEqual(checkpoint, "/tmp/model/ladzany.pth")

    def test_runner_requires_a_site_for_site_specific_weights(self):
        config = {"site_checkpoints": {"Hradisko_Sitno": "sitno.pth"}}
        with self.assertRaises(ValueError):
            resolve_checkpoint_path(config, "/tmp/model/sitno.pth")


if __name__ == "__main__":
    unittest.main()
