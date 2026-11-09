import importlib.util
import json
import os
import shutil
import zipfile


def validate_model_config(config):
    if not isinstance(config, dict) or type(config.get("schema_version")) is not int or config["schema_version"] != 1:
        raise ValueError("Nepodporovaný alebo chýbajúci formát config.json / Unsupported config format.")

    model = config.get("model", {})
    inputs = config.get("input", {})
    inference = config.get("inference", {})
    if not all(isinstance(item, dict) for item in (model, inputs, inference)):
        raise ValueError("Sekcie model, input a inference musia byť objekty / Model, input and inference sections must be objects.")
    input_type = inputs.get("type")
    channels = inputs.get("channels")
    if not isinstance(input_type, str) or not input_type.strip():
        raise ValueError("Typ vstupu musí byť vyplnený / Input type must be specified.")
    if type(channels) is not int or channels < 1:
        raise ValueError("Počet vstupných pásiem musí byť kladné celé číslo / Input band count must be a positive integer.")
    band_indexes = inputs.setdefault("bands", list(range(1, channels + 1)))
    if (
        not isinstance(band_indexes, list)
        or len(band_indexes) != channels
        or any(type(index) is not int or index < 1 for index in band_indexes)
        or len(set(band_indexes)) != len(band_indexes)
    ):
        raise ValueError("Zoznam vstupných pásiem nezodpovedá ich počtu / Input band indexes do not match the channel count.")
    if not isinstance(inputs.get("preprocessing"), str) or not inputs["preprocessing"].strip():
        raise ValueError("Balík musí určiť predspracovanie vstupu / Bundle must define input preprocessing.")
    if not isinstance(inputs.get("preprocessing_options", {}), dict):
        raise ValueError("Voľby predspracovania musia byť objekt / Preprocessing options must be an object.")

    threshold = inference.get("threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise ValueError("Prah v konfigurácii musí byť v rozsahu 0 až 1 / Threshold must be between 0 and 1.")

    for key, default in (("patch_size", 256), ("stride", 128), ("batch_size", 8)):
        value = inference.get(key, default)
        if type(value) is not int or value < 1:
            raise ValueError(f"Neplatná hodnota '{key}' v konfigurácii / Invalid '{key}' value.")
        inference[key] = value
    if inference["stride"] > inference["patch_size"]:
        raise ValueError("Krok výrezov nesmie byť väčší ako výrez / Inference stride cannot exceed patch size.")
    for key in ("checkpoint", "inference_script"):
        filename = config.get(key)
        if not isinstance(filename, str) or not filename or os.path.basename(filename) != filename:
            raise ValueError(f"Neplatný názov súboru '{key}' v konfigurácii / Invalid '{key}' filename.")
    additional_checkpoints = config.get("additional_checkpoints", [])
    if not isinstance(additional_checkpoints, list) or any(
        not isinstance(filename, str) or not filename or os.path.basename(filename) != filename
        for filename in additional_checkpoints
    ):
        raise ValueError("Neplatný zoznam doplnkových checkpointov / Invalid additional checkpoint list.")
    checkpoint_names = [config["checkpoint"], *additional_checkpoints]
    if len(set(checkpoint_names)) != len(checkpoint_names) or config["inference_script"] in checkpoint_names:
        raise ValueError("Názvy súborov v balíku sa nesmú opakovať / Bundle filenames must be unique.")

    site_checkpoints = config.get("site_checkpoints")
    if site_checkpoints is not None:
        if (
            not isinstance(site_checkpoints, dict)
            or not site_checkpoints
            or any(
                not isinstance(site, str)
                or not site.strip()
                or checkpoint not in checkpoint_names
                for site, checkpoint in site_checkpoints.items()
            )
        ):
            raise ValueError("Neplatné váhy pre jednotlivé lokality / Invalid site-specific checkpoints.")

    thresholds_by_site = inference.get("thresholds_by_site", {})
    if not isinstance(thresholds_by_site, dict) or any(
        site_checkpoints is None
        or site not in site_checkpoints
        or isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not 0 <= threshold <= 1
        for site, threshold in thresholds_by_site.items()
    ):
        raise ValueError("Neplatné prahy pre jednotlivé lokality / Invalid site-specific thresholds.")

    return config


def read_model_bundle(bundle_path):
    try:
        with zipfile.ZipFile(bundle_path) as bundle:
            config = json.loads(bundle.read("config.json").decode("utf-8"))
            validate_model_config(config)
            names = set(bundle.namelist())
            required_files = [
                config["checkpoint"],
                *config.get("additional_checkpoints", []),
                config["inference_script"],
            ]
            for required_file in required_files:
                if required_file not in names:
                    raise ValueError(f"V ZIP balíku chýba {required_file} / Missing {required_file} in model ZIP.")
    except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Balík modelu sa nedá načítať / Could not read model bundle: {exc}") from exc
    return config


def extract_model_bundle(bundle_path, destination):
    config = read_model_bundle(bundle_path)
    with zipfile.ZipFile(bundle_path) as bundle:
        filenames = [
            config["checkpoint"],
            *config.get("additional_checkpoints", []),
            config["inference_script"],
        ]
        for filename in filenames:
            destination_path = os.path.join(destination, filename)
            with bundle.open(filename) as source, open(destination_path, "wb") as target:
                shutil.copyfileobj(source, target)
    return config, os.path.join(destination, config["checkpoint"])


def load_bundle_model(config, runner_path, checkpoint_path, torch, segmentation_models, device):
    spec = importlib.util.spec_from_file_location("terasy_model_runner", runner_path)
    if spec is None or spec.loader is None:
        raise ValueError("Inferenčný skript sa nedá načítať / Could not load inference script.")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    load_model = getattr(runner, "load_model", None)
    if not callable(load_model):
        raise ValueError("Inferenčný skript musí poskytovať load_model() / Inference script must define load_model().")
    preprocess_patch = getattr(runner, "preprocess_patch", None)
    if not callable(preprocess_patch):
        raise ValueError("Inferenčný skript musí poskytovať preprocess_patch() / Inference script must define preprocess_patch().")
    model = load_model(config, checkpoint_path, torch, segmentation_models, device)
    return model, runner