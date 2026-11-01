import tempfile
import unittest
from pathlib import Path

from terasy_eval.evaluation_loader import bundled_evaluator_path, load_evaluator


class EvaluationLoaderTests(unittest.TestCase):
    def test_bundled_default_script_exists(self):
        self.assertTrue(Path(bundled_evaluator_path()).is_file())

    def test_loads_callable_from_selected_python_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            script = Path(temporary_directory) / "custom_eval.py"
            script.write_text(
                "def vyhodnot(predikcia_tif, terasy_shp, **kwargs):\n"
                "    return {'model': predikcia_tif, 'reference': terasy_shp}\n",
                encoding="utf-8",
            )
            evaluator = load_evaluator(str(script))
            self.assertEqual(evaluator("mask.tif", "gt.gpkg"), {
                "model": "mask.tif",
                "reference": "gt.gpkg",
            })

    def test_rejects_script_without_vyhodnot(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            script = Path(temporary_directory) / "not_an_evaluator.py"
            script.write_text("VALUE = 1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "vyhodnot"):
                load_evaluator(str(script))


if __name__ == "__main__":
    unittest.main()