#!/usr/bin/env python3
import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path

from terasy_eval.model_config import validate_model_config


PLUGIN_DIR = Path(__file__).resolve().parent


def create_bundle(checkpoint_path, config_path, output_path):
    checkpoint_path = Path(checkpoint_path).resolve()
    config_path = Path(config_path).resolve()
    output_path = Path(output_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_model_config(config)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_path = tempfile.mkstemp(suffix=".zip", dir=output_path.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary_path, "w", allowZip64=True) as bundle:
            bundle.writestr("config.json", json.dumps(config, ensure_ascii=False, indent=2) + "\n")
            checkpoint_info = zipfile.ZipInfo(config["checkpoint"])
            checkpoint_info.compress_type = zipfile.ZIP_STORED
            with checkpoint_path.open("rb") as checkpoint, bundle.open(checkpoint_info, "w") as target:
                while True:
                    block = checkpoint.read(1024 * 1024)
                    if not block:
                        break
                    target.write(block)

            bundle.write(
                PLUGIN_DIR / "terasy_eval" / "model_runner.py",
                config["inference_script"],
            )
            bundle.writestr(
                "README.txt",
                "Model bundle for the QGIS plugin Detekcia teras / Terrace detection.\n"
                "Balik modelu pre QGIS plugin Detekcia teras / Terrace detection.\n"
                "Select this ZIP in the inference tool. The input raster is selected from QGIS.\n"
                "Vyberte tento ZIP v nastroji inferencie. Vstupny raster vyberiete z QGIS.\n"
                "PyTorch and model libraries must be available in the QGIS Python.\n"
                "PyTorch a kniznica modelu musia byt dostupne v Pythone QGIS.\n",
            )
        os.replace(temporary_path, output_path)
        os.chmod(output_path, 0o644)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def main():
    parser = argparse.ArgumentParser(description="Create a QGIS terrace model ZIP bundle.")
    parser.add_argument("checkpoint", help="Path to the trained .pth file")
    parser.add_argument("config", help="Path to the model config JSON")
    parser.add_argument("output", help="Destination ZIP file")
    args = parser.parse_args()
    create_bundle(args.checkpoint, args.config, args.output)
    print(f"Model bundle created: {args.output}")


if __name__ == "__main__":
    main()