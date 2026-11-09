import math
import os
import tempfile

import numpy as np
from osgeo import gdal
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsProject,
    QgsRasterLayer,
)
from ..model_config import extract_model_bundle, read_model_bundle, load_bundle_model


HRADISKA = (
    "Hradisko_Sitno",
    "Hradisko_Sasovske_Podhradie",
    "Hradisko_Ladzany",
)
HRADISKO_LABELS = ("Sitno", "Šášovské Podhradie", "Ladzany")


class InferenciaTerasyAlgorithm(QgsProcessingAlgorithm):
    VSTUP = "VSTUP"
    BALIK = "BALIK"
    HRADISKO = "HRADISKO"
    PRAH = "PRAH"
    VYSTUP = "VYSTUP"

    def name(self):
        return "inferencia_terasy"

    def displayName(self):
        return "Vyhľadanie terás modelom (inferencia) / Model terrace search (inference)"

    def shortHelpString(self):
        return (
            "SK: Vyberte vstupný raster z projektu QGIS a ZIP balík modelu. Balík určuje "
            "model, počet a typ pásiem aj predvolený prah. Pri modeloch s váhami pre "
            "jednotlivé lokality vyberte hradisko. Výsledkom je raster správne "
            "zarovnaný so vstupom (0 = pozadie, 1 = terasa). Prah možno upraviť.\n\n"
            "EN: Select an input raster from the QGIS project and a model ZIP bundle. "
            "The bundle defines the model, band count and type, and default threshold. "
            "For models with site-specific weights, select the hillfort. The output "
            "raster matches the input grid (0 = background, 1 = terrace). "
            "The threshold can be adjusted."
        )

    def createInstance(self):
        return InferenciaTerasyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.VSTUP,
            "Vstupný raster v projekte QGIS / Input raster in the QGIS project",
        ))
        self.addParameter(
            QgsProcessingParameterFile(
                self.BALIK,
                "Balík modelu ZIP (konfigurácia + model + skript) / Model ZIP bundle (config + model + script)",
                behavior=QgsProcessingParameterFile.File,
                fileFilter="ZIP (*.zip)",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.HRADISKO,
                "Hradisko (pre modely s lokalitnými váhami) / Hillfort (for site-specific models)",
                options=list(HRADISKO_LABELS),
                defaultValue=None,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.PRAH,
                "Prah pravdepodobnosti (predvolený z balíka) / Probability threshold (bundle default)",
                type=QgsProcessingParameterNumber.Double,
                minValue=0.0,
                maxValue=1.0,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.VYSTUP,
                "Výstupná maska terás GeoTIFF / Terrace mask output GeoTIFF",
                fileFilter="GeoTIFF (*.tif)",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source_layer = self.parameterAsRasterLayer(parameters, self.VSTUP, context)
        bundle_path = self.parameterAsFile(parameters, self.BALIK, context)
        site_index = self.parameterAsEnum(parameters, self.HRADISKO, context)
        threshold_override = parameters.get(self.PRAH)
        output_path = self.parameterAsFileOutput(parameters, self.VYSTUP, context)

        if source_layer is None or not source_layer.isValid():
            raise QgsProcessingException("SK: Vstupný raster nie je platný. / EN: The input raster is invalid.")
        if not bundle_path or not os.path.isfile(bundle_path):
            raise QgsProcessingException("SK: Balík ZIP sa nenašiel. / EN: The model ZIP bundle was not found.")
        try:
            model_config = read_model_bundle(bundle_path)
        except (OSError, ValueError) as exc:
            raise QgsProcessingException(f"SK: Balík modelu nie je platný. / EN: Invalid model bundle. {exc}") from exc

        input_config = model_config["input"]
        inference_config = model_config["inference"]
        site_checkpoints = model_config.get("site_checkpoints")
        selected_site = None
        if site_checkpoints is not None:
            if site_index < 0 or site_index >= len(HRADISKA):
                raise QgsProcessingException(
                    "SK: Vyberte hradisko pre tento model. / "
                    "EN: Select a hillfort for this model."
                )
            selected_site = HRADISKA[site_index]
            if selected_site not in site_checkpoints:
                raise QgsProcessingException(
                    f"SK: Balík neobsahuje váhy pre {selected_site}. / "
                    f"EN: The bundle does not contain weights for {selected_site}."
                )

        required_channels = input_config["channels"]
        source_path = source_layer.source().split("|")[0]
        source = gdal.Open(source_path, gdal.GA_ReadOnly)
        if source is None or source.RasterCount != required_channels:
            raise QgsProcessingException(
                f"SK: Balík očakáva {required_channels} pásiem ({input_config['description']}), "
                f"vstup ich obsahuje {source.RasterCount if source else 0}. / "
                f"EN: The bundle expects {required_channels} bands ({input_config['description']}), "
                f"but the input contains {source.RasterCount if source else 0}."
            )
        if any(index > source.RasterCount for index in input_config["bands"]):
            raise QgsProcessingException(
                "SK: Konfigurácia vyberá pásmo, ktoré vstupný raster neobsahuje. / "
                "EN: The configuration selects a band that is not present in the input raster."
            )
        threshold = (
            float(inference_config.get("thresholds_by_site", {}).get(
                selected_site, inference_config["threshold"]
            ))
            if threshold_override in (None, "")
            else self.parameterAsDouble(parameters, self.PRAH, context)
        )
        if not output_path.lower().endswith((".tif", ".tiff")):
            output_path += ".tif"

        try:
            import torch
        except ImportError as exc:
            raise QgsProcessingException(
                "SK: Inferencia vyžaduje PyTorch v Pythone QGIS. / EN: Inference requires PyTorch in the QGIS Python environment."
            ) from exc
        try:
            import segmentation_models_pytorch as smp
        except ImportError:
            smp = None

        model_name = model_config.get("name", os.path.basename(bundle_path))
        feedback.pushInfo(f"SK / EN: Načítavam model / Loading model: {model_name}")
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        try:
            with tempfile.TemporaryDirectory(prefix="terrace_model_") as model_directory:
                model_config, checkpoint_path = extract_model_bundle(bundle_path, model_directory)
                if selected_site is not None and model_config.get("site_checkpoints") is not None:
                    model_config["selected_site"] = selected_site
                runner_path = os.path.join(model_directory, model_config["inference_script"])
                model, runner = load_bundle_model(
                    model_config, runner_path, checkpoint_path, torch, smp, device
                )
        except (OSError, ValueError, RuntimeError) as exc:
            raise QgsProcessingException(
                f"SK: Model v balíku sa nepodarilo načítať. / EN: Could not load the bundled model. {exc}"
            ) from exc
        feedback.pushInfo(f"SK / EN: Výpočtové zariadenie / Processing device: {device}")

        width, height = source.RasterXSize, source.RasterYSize
        patch = inference_config["patch_size"]
        stride = inference_config["stride"]
        batch_size = inference_config["batch_size"]
        padded_width = max(patch, patch + math.ceil(max(0, width - patch) / stride) * stride)
        padded_height = max(patch, patch + math.ceil(max(0, height - patch) / stride) * stride)
        x_starts = list(range(0, padded_width - patch + 1, stride))
        y_starts = list(range(0, padded_height - patch + 1, stride))

        driver = gdal.GetDriverByName("GTiff")
        output = driver.Create(
            output_path,
            width,
            height,
            1,
            gdal.GDT_Byte,
            options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"],
        )
        if output is None:
            raise QgsProcessingException(
                f"SK: Výstupnú masku sa nepodarilo vytvoriť: {output_path} / "
                f"EN: Could not create the output mask: {output_path}"
            )
        output.SetGeoTransform(source.GetGeoTransform())
        output.SetProjection(source.GetProjection())
        output_band = output.GetRasterBand(1)
        output_band.SetNoDataValue(255)

        accumulator = np.zeros((patch, padded_width), dtype=np.float32)
        counts = np.zeros((patch, padded_width), dtype=np.uint8)

        def read_patch(x, y):
            read_width, read_height = min(patch, width - x), min(patch, height - y)
            pad_mode = "reflect" if read_width > 1 and read_height > 1 else "edge"
            band_indexes = input_config["bands"]
            bands = np.stack([
                source.GetRasterBand(band_index).ReadAsArray(x, y, read_width, read_height)
                for band_index in band_indexes
            ]).astype(np.float32)
            nodata_values = [source.GetRasterBand(index).GetNoDataValue() for index in band_indexes]
            tile = runner.preprocess_patch(model_config, bands, nodata_values)
            if tile.shape != bands.shape or not np.isfinite(tile).all():
                raise QgsProcessingException(
                    "SK: Predspracovanie modelu vrátilo neplatný rasterový výrez. / "
                    "EN: Model preprocessing returned an invalid raster patch."
                )
            return np.pad(
                tile,
                ((0, 0), (0, patch - read_height), (0, patch - read_width)),
                mode=pad_mode,
            )

        try:
            with torch.no_grad():
                for y_index, y in enumerate(y_starts):
                    if feedback.isCanceled():
                        break
                    for batch_start in range(0, len(x_starts), batch_size):
                        xs = x_starts[batch_start:batch_start + batch_size]
                        batch = np.stack([read_patch(x, y) for x in xs])
                        tensor = torch.from_numpy(batch).to(device)
                        probabilities = torch.sigmoid(model(tensor)).float().cpu().numpy()[:, 0]
                        for x, probability in zip(xs, probabilities):
                            accumulator[:, x:x + patch] += probability
                            counts[:, x:x + patch] += 1

                    if y_index < len(y_starts) - 1:
                        rows_to_write = min(stride, height - y)
                    else:
                        rows_to_write = min(patch, height - y)
                    if rows_to_write > 0:
                        probability_strip = accumulator[:rows_to_write, :width] / np.maximum(
                            counts[:rows_to_write, :width], 1
                        )
                        output_values = (probability_strip > threshold).astype(np.uint8)
                        output_band.WriteArray(output_values, 0, y)

                    if y_index < len(y_starts) - 1:
                        accumulator[:patch - stride] = accumulator[stride:]
                        accumulator[patch - stride:] = 0
                        counts[:patch - stride] = counts[stride:]
                        counts[patch - stride:] = 0
                    feedback.setProgress(int((y_index + 1) * 100 / len(y_starts)))
        finally:
            output_band.FlushCache()
            output.FlushCache()
            output = None
            source = None

        postprocess_mask = getattr(runner, "postprocess_mask", None)
        if callable(postprocess_mask):
            feedback.pushInfo("SK / EN: Upravujem masku podľa filtra balíka / Applying bundle mask filter")
            try:
                postprocess_mask(model_config, source_path, output_path, feedback)
            except Exception as exc:
                raise QgsProcessingException(
                    f"SK: Dodatočná úprava masky zlyhala: {exc} / "
                    f"EN: Bundle post-processing failed: {exc}"
                ) from exc

        if feedback.isCanceled():
            raise QgsProcessingException(
                "SK: Výpočet bol zrušený; výstup môže byť neúplný. / "
                "EN: Processing was canceled; the output may be incomplete."
            )
        result_layer = QgsRasterLayer(
            output_path,
            f"{source_layer.name()} – detekované terasy / detected_terraces",
        )
        if result_layer.isValid():
            QgsProject.instance().addMapLayer(result_layer)
        return {self.VYSTUP: output_path}