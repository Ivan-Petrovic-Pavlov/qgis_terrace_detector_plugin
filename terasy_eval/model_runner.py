import numpy as np


def load_model(config, checkpoint_path, torch, segmentation_models, device):
    model_settings = config["model"]
    input_settings = config["input"]
    architecture = model_settings["architecture"]
    if segmentation_models is None:
        raise ImportError("This model bundle requires segmentation_models_pytorch.")
    model_factory = getattr(segmentation_models, architecture, None)
    if model_factory is None:
        raise ValueError(f"Unsupported model architecture: {architecture}")

    model = model_factory(
        encoder_name=model_settings["encoder"],
        encoder_weights=None,
        in_channels=input_settings["channels"],
        classes=1,
    )
    try:
        state = torch.load(checkpoint_path, map_location=device, weights_only=True)
    except TypeError:
        state = torch.load(checkpoint_path, map_location=device)
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]

    first_convolution = next(
        (
            weights
            for name, weights in state.items()
            if name.endswith(("encoder.conv1.weight", "encoder._conv_stem.weight"))
        ),
        None,
    )
    if first_convolution is not None and len(first_convolution.shape) == 4:
        checkpoint_channels = int(first_convolution.shape[1])
        if checkpoint_channels != input_settings["channels"]:
            raise ValueError(
                f"The checkpoint expects {checkpoint_channels} channels but the package "
                f"configuration declares {input_settings['channels']}."
            )

    try:
        model.load_state_dict(state)
    except RuntimeError as exc:
        raise ValueError(
            "Checkpoint weights do not match the model architecture, encoder, or input channels."
        ) from exc
    return model.to(device).eval()


def preprocess_patch(config, bands, nodata_values):
    input_settings = config["input"]
    options = input_settings.get("preprocessing_options", {})
    values = np.asarray(bands, dtype=np.float32).copy()
    strategy = input_settings["preprocessing"]

    if strategy == "dem_per_patch":
        nodata = nodata_values[0]
        valid = np.isfinite(values[0])
        if nodata is not None:
            valid &= values[0] != nodata
        mean = float(values[0][valid].mean()) if valid.any() else 0.0
        scale = float(options.get("scale_m", 5.0))
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("DEM preprocessing scale_m must be a positive finite number.")
        values[0] = np.where(valid, (values[0] - mean) / scale, 0.0)
    elif strategy == "imagenet_rgb":
        if values.shape[0] != 3:
            raise ValueError("imagenet_rgb requires exactly three input bands.")
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]
        values = (values / 255.0 - mean) / std
    elif strategy == "imagenet_rgb_dem_per_patch":
        if values.shape[0] != 4:
            raise ValueError("imagenet_rgb_dem_per_patch requires four input bands.")
        values[:3] = (values[:3] / 255.0 - np.array(
            [0.485, 0.456, 0.406], dtype=np.float32
        )[:, None, None]) / np.array(
            [0.229, 0.224, 0.225], dtype=np.float32
        )[:, None, None]
        dem_config = {"input": {
            "preprocessing": "dem_per_patch",
            "preprocessing_options": options,
        }}
        values[3:] = preprocess_patch(dem_config, values[3:], nodata_values[3:])
    elif strategy == "identity":
        for index, nodata in enumerate(nodata_values):
            invalid = ~np.isfinite(values[index])
            if nodata is not None:
                invalid |= values[index] == nodata
            values[index][invalid] = 0.0
    else:
        raise ValueError(f"Unsupported preprocessing strategy: {strategy}")

    return values.astype(np.float32, copy=False)
