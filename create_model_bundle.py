#!/usr/bin/env python3
import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path

from terasy_eval.model_config import validate_model_config


PLUGIN_DIR = Path(__file__).resolve().parent


def create_bundle(checkpoint_path, config_path, output_path, runner_path=None, assets=None):
    checkpoint_path = Path(checkpoint_path).resolve()
    config_path = Path(config_path).resolve()
    output_path = Path(output_path).resolve()
    runner_path = Path(runner_path).resolve() if runner_path else PLUGIN_DIR / "terasy_eval" / "model_runner.py"
    assets = {name: Path(path).resolve() for name, path in (assets or {}).items()}
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_model_config(config)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    if not runner_path.is_file():
        raise FileNotFoundError(f"Inference script not found: {runner_path}")
    checkpoint_paths = {config["checkpoint"]: checkpoint_path}
    for filename in config.get("additional_checkpoints", []):
        if filename not in assets:
            raise ValueError(f"Pass the additional checkpoint with --asset {filename}=PATH")
        if not assets[filename].is_file():
            raise FileNotFoundError(f"Checkpoint not found: {assets[filename]}")
        checkpoint_paths[filename] = assets[filename]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_path = tempfile.mkstemp(suffix=".zip", dir=output_path.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary_path, "w", allowZip64=True) as bundle:
            bundle.writestr("config.json", json.dumps(config, ensure_ascii=False, indent=2) + "\n")
            for filename, source_path in checkpoint_paths.items():
                checkpoint_info = zipfile.ZipInfo(filename)
                checkpoint_info.compress_type = zipfile.ZIP_STORED
                with source_path.open("rb") as checkpoint, bundle.open(checkpoint_info, "w") as target:
                    while True:
                        block = checkpoint.read(1024 * 1024)
                        if not block:
                            break
                        target.write(block)

            bundle.write(runner_path, config["inference_script"])
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
    parser.add_argument("--runner", help="Custom inference runner Python file")
    parser.add_argument(
        "--asset",
        action="append",
        default=[],
        metavar="ARCHIVE_NAME=PATH",
        help="Additional file to include (repeat for every additional checkpoint)",
    )
    args = parser.parse_args()
    assets = {}
    for item in args.asset:
        name, separator, path = item.partition("=")
        if not separator or not name or not path:
            parser.error(f"Invalid --asset '{item}'; use ARCHIVE_NAME=PATH")
        assets[name] = path
    create_bundle(args.checkpoint, args.config, args.output, args.runner, assets)
    print(f"Model bundle created: {args.output}")


if __name__ == "__main__":
    main()