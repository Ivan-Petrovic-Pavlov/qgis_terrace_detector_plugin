import os
import tempfile
from datetime import datetime

from qgis.core import (
    QgsFeature,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingException,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsProject,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSingleSymbolRenderer,
    QgsUnitTypes,
)
from ..summary_table import write_gpkg_table
from ..evaluation_loader import bundled_evaluator_path, load_evaluator

class TerasyEvalAlgorithm(QgsProcessingAlgorithm):

    PREDIKCIE = "PREDIKCIE"
    TERASY = "TERASY"
    TOLERANCIA = "TOLERANCIA"
    POKRYTIE = "POKRYTIE"
    MIN_PLOCHA = "MIN_PLOCHA"
    EVALUATOR_MODE = "EVALUATOR_MODE"
    EVALUATOR_FILE = "EVALUATOR_FILE"
    VYSTUP = "VYSTUP"
    METRIC_LABELS = {
        "lokalita": "Lokalita / Site",
        "tolerancia_m": "Tolerancia / Tolerance (m)",
        "pocet_gt": "Počet referenčných terás / Reference terrace count",
        "pocet_detekcii": "Počet nálezov / Detection count",
        "TP": "Správne zistené terasy / Correctly detected terraces (TP)",
        "FN": "Nenájdené terasy / Missed terraces (FN)",
        "FP": "Falošné nálezy / False detections (FP)",
        "spravne_detekcie": "Správne nálezy / Correct detections",
        "precision": "Presnosť nálezov / Detection precision",
        "recall": "Úplnosť záchytu / Recall",
        "f1": "Súhrnná miera F1 / F1 score",
        "prah": "Prah už aplikovaný na binárnu masku / Threshold already applied to binary mask",
        "min_plocha_m2": "Minimálna plocha nálezu / Minimum detection area (m²)",
    }
    TABLE_FIELD_LABELS = {
        "model": "Model / Model",
        "raster": "Maska modelu / Model mask",
        "vystup": "Priestorové výstupy / Spatial outputs",
        "datum": "Čas vyhodnotenia / Evaluation time",
        "lokalita": "Lokalita / Site",
        "tolerancia_m": "Tolerancia porovnania (m) / Matching tolerance (m)",
        "pocet_gt": "Počet ručne zakreslených terás / Manually mapped terrace count",
        "pocet_detekcii": "Počet nálezov modelu / Model detection count",
        "TP": "Správne zistené terasy / Correctly detected terraces (TP)",
        "FN": "Nenájdené referenčné terasy / Missed reference terraces (FN)",
        "FP": "Falošné nálezy modelu / False model detections (FP)",
        "spravne_detekcie": "Správne nálezy / Correct detections",
        "precision": "Presnosť nálezov / Detection precision",
        "recall": "Úplnosť záchytu / Recall",
        "f1": "Súhrnná miera F1 / F1 score",
        "prah": "Prahovanie už aplikované pri tvorbe masky / Threshold applied when creating mask",
        "min_plocha_m2": "Minimálna plocha nálezu (m²) / Minimum detection area (m²)",
    }

    def name(self):
        return "vyhodnotenie_teras"

    def displayName(self):
        return "Terasy – vyhodnotenie / Terrace evaluation"

    def shortHelpString(self):
        return (
            "SK: Vyberte jednu alebo viac masiek modelu a spoločnú vrstvu ručne zakreslených "
            "terás. Každá maska sa vyhodnotí samostatne; vektor sa oreže na jej rozsah. "
            "Pre každý model sa v QGIS vytvorí skupina: správne zistené terasy (TP), "
            "nenájdené referenčné terasy (FN) a falošné nálezy modelu (FP). Porovnávacia "
            "tabuľka obsahuje samostatný riadok a metriky pre každý model.\n\n"
            "EN: Select one or more model masks and the shared manually mapped terrace "
            "layer. Each mask is evaluated separately; the vector is clipped to its extent. "
            "QGIS receives a group per model: correctly detected terraces (TP), missed "
            "reference terraces (FN), and false model detections (FP). The comparison "
            "table contains one metrics row per model. A custom Python evaluation script "
            "can be selected; the bundled evaluator is the default."
        )

    def createInstance(self):
        return TerasyEvalAlgorithm()

    @staticmethod
    def default_evaluator_path():
        return bundled_evaluator_path()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.PREDIKCIE,
            "Masky terás z modelov v QGIS (vyberte jednu alebo viac) / Model terrace masks in QGIS (select one or more)",
            layerType=QgsProcessing.TypeRaster,
        ))

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.TERASY,
                "Referenčné terasy: ručne zakreslené línie / Reference terraces: manually mapped lines",
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.TOLERANCIA,
                "Tolerancia pri porovnaní (m) / Matching tolerance (m)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.POKRYTIE,
                "Minimálna časť línie, ktorá musí byť nájdená / Minimum share of line that must be detected",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                minValue=0.0,
                maxValue=1.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_PLOCHA,
                "Odfiltrovať nálezy menšie ako (m²) / Filter detections smaller than (m²)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.0,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.EVALUATOR_MODE,
                "Skript vyhodnotenia / Evaluation script",
                options=[
                    "Vstavaný skript / Built-in script",
                    "Vlastný Python skript / Custom Python script",
                ],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.EVALUATOR_FILE,
                "Vlastný skript vyhodnotenia (.py) / Custom evaluation script (.py)",
                behavior=QgsProcessingParameterFile.File,
                fileFilter="Python (*.py)",
                optional=True,
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.VYSTUP,
                "Uložiť porovnávaciu tabuľku (GeoPackage, voliteľné) / Save comparison table (GeoPackage, optional)",
                fileFilter="GeoPackage (*.gpkg)",
                optional=True,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        predictions = self.parameterAsLayerList(parameters, self.PREDIKCIE, context)
        if not predictions:
            raise QgsProcessingException(
                "SK: Vyberte aspoň jednu masku modelu. / EN: Select at least one model mask."
            )
        tolerancia = self.parameterAsDouble(
            parameters,
            self.TOLERANCIA,
            context
        )

        pokrytie = self.parameterAsDouble(
            parameters,
            self.POKRYTIE,
            context
        )
        min_plocha = self.parameterAsDouble(parameters, self.MIN_PLOCHA, context)
        evaluator_mode = self.parameterAsEnum(parameters, self.EVALUATOR_MODE, context)
        if evaluator_mode == 0:
            evaluator_path = self.default_evaluator_path()
        else:
            evaluator_path = self.parameterAsFile(parameters, self.EVALUATOR_FILE, context)
            if not evaluator_path:
                raise QgsProcessingException(
                    "SK: Vyberte vlastný .py skript alebo zvoľte vstavaný skript. / "
                    "EN: Select a custom .py script or choose the built-in script."
                )
        try:
            evaluator = load_evaluator(evaluator_path)
        except (OSError, ValueError, ImportError) as exc:
            raise QgsProcessingException(
                f"SK: Vyhodnocovací skript sa nedá načítať: {exc} / "
                f"EN: Could not load the evaluation script: {exc}"
            ) from exc

        gpkg = self.parameterAsFileOutput(
            parameters,
            self.VYSTUP,
            context
        )
        if not gpkg:
            gpkg = QgsProcessingUtils.generateTempFilename("terrace_comparison.gpkg")
        if not gpkg.lower().endswith(".gpkg"):
            gpkg += ".gpkg"
        output_dir = os.path.dirname(os.path.abspath(gpkg))
        os.makedirs(output_dir, exist_ok=True)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # Use the selected QGIS layer directly; parameterAsString is empty for layer objects.
        terasy_layer = self.parameterAsVectorLayer(
            parameters,
            self.TERASY,
            context
        )

        if terasy_layer is None or not terasy_layer.isValid():
            raise QgsProcessingException(
                "SK: Vektorovú vrstvu terás sa nepodarilo načítať. / EN: Could not load the terrace vector layer."
            )

        temporary_vector_dir = tempfile.TemporaryDirectory(prefix="terrace_reference_")
        terasy_path = os.path.join(temporary_vector_dir.name, "reference_terraces.gpkg")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = "terasy"
        options.fileEncoding = "UTF-8"
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            terasy_layer,
            terasy_path,
            context.transformContext(),
            options,
        )
        if result[0] != QgsVectorFileWriter.NoError:
            raise QgsProcessingException(
                f"SK: Vektorovú vrstvu sa nepodarilo pripraviť: {result[3]} / "
                f"EN: Could not prepare the vector layer: {result[3]}"
            )

        rows = []
        for index, raster in enumerate(predictions, start=1):
            if feedback.isCanceled():
                break
            if raster is None or not raster.isValid():
                feedback.reportError("SK: Preskakujem neplatnú masku. / EN: Skipping an invalid mask.")
                continue
            if raster.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
                raise QgsProcessingException(
                    f"SK: Maska {raster.name()} musí používať projektovaný CRS v metroch. / "
                    f"EN: Mask {raster.name()} must use a projected CRS in metres."
                )

            raster_path = raster.source().split("|")[0]
            if not os.path.isfile(raster_path):
                raise QgsProcessingException(
                    f"SK: Maska sa nenašla: {raster_path} / EN: Mask not found: {raster_path}"
                )
            safe_name = "_".join(
                part for part in "".join(
                    character if character.isalnum() else " " for character in raster.name()
                ).split() if part
            )[:48] or "model"
            model_gpkg = os.path.join(
                output_dir,
                f"{os.path.splitext(os.path.basename(gpkg))[0]}_{run_id}_{index}_{safe_name}.gpkg",
            )
            feedback.pushInfo(f"SK / EN: Vyhodnocujem model / Evaluating model: {raster.name()}")
            try:
                metrics = evaluator(
                    predikcia_tif=raster_path,
                    terasy_shp=terasy_path,
                    tolerancia_m=tolerancia,
                    min_pokrytie=pokrytie,
                    min_plocha_m2=min_plocha,
                    vystup_gpkg=model_gpkg,
                )
            except Exception as exc:
                raise QgsProcessingException(
                    f"SK: Vyhodnotenie modelu {raster.name()} zlyhalo: {exc} / "
                    f"EN: Evaluation failed for model {raster.name()}: {exc}"
                ) from exc

            row = {
                "model": raster.name(),
                "raster": raster_path,
                "vystup": model_gpkg,
                "datum": datetime.now().isoformat(timespec="seconds"),
                **metrics,
            }
            rows.append(row)
            self.pridaj_vystupne_vrstvy(model_gpkg, raster.name(), feedback)
            feedback.pushInfo("SK / EN: Metriky modelu / Model metrics:")
            for key, value in metrics.items():
                feedback.pushInfo(f"{self.METRIC_LABELS.get(key, key)}: {value}")

        if not rows:
            raise QgsProcessingException(
                "SK: Nepodarilo sa vyhodnotiť žiadnu masku. / EN: No model mask was evaluated."
            )

        self.uloz_suhrn(gpkg, rows)
        summary = QgsVectorLayer(
            f"{gpkg}|layername=vysledky",
            "Porovnávacia tabuľka výsledkov / Model comparison results",
            "ogr",
        )
        if not summary.isValid() or summary.featureCount() != len(rows):
            raise QgsProcessingException(
                "SK: Porovnávaciu tabuľku sa nepodarilo načítať so všetkými riadkami. / "
                "EN: Could not load the comparison table with all rows."
            )
        for field_name, alias in self.TABLE_FIELD_LABELS.items():
            field_index = summary.fields().indexFromName(field_name)
            if field_index >= 0:
                summary.setFieldAlias(field_index, alias)
        summary.setDisplayExpression('"model"')
        QgsProject.instance().addMapLayer(summary)
        feedback.pushInfo(f"SK / EN: Porovnávacia tabuľka / Comparison table: {gpkg}")
        return {self.VYSTUP: gpkg}

    @staticmethod
    def uloz_suhrn(gpkg, rows):
        try:
            write_gpkg_table(gpkg, "vysledky", rows)
        except Exception as exc:
            raise QgsProcessingException(
                f"SK: Porovnávaciu tabuľku sa nepodarilo uložiť do {gpkg}: {exc} / "
                f"EN: Could not save the comparison table to {gpkg}: {exc}"
            ) from exc

    @staticmethod
    def pridaj_vystupne_vrstvy(gpkg, model_name, feedback):
        root = QgsProject.instance().layerTreeRoot()
        group = root.addGroup(f"Výsledky modelu / Model results: {model_name}")
        outputs = (
            ("gt_terasy", "TP", "Referenčné terasy nájdené modelom (TP) / Reference terraces detected by model (TP)", "#2ca02c", True),
            ("gt_terasy", "FN", "Referenčné terasy nenájdené modelom (FN) / Reference terraces missed by model (FN)", "#1f77b4", True),
            ("detekcie", "TP", "Správne nálezy modelu (TP) / Correct model detections (TP)", "#2ca02c", False),
            ("detekcie", "FP", "Falošné nálezy modelu (FP) / False model detections (FP)", "#d62728", False),
        )
        for table_name, status, display_name, color, is_line in outputs:
            layer = QgsVectorLayer(f"{gpkg}|layername={table_name}", display_name, "ogr")
            if not layer.isValid() or not layer.setSubsetString(f'"stav" = \'{status}\''):
                feedback.reportError(
                    f"SK: Výstupnú vrstvu sa nepodarilo načítať: {display_name} / "
                    f"EN: Could not load output layer: {display_name}"
                )
                continue
            if is_line:
                symbol = QgsLineSymbol.createSimple({"line_color": color, "line_width": "0.9"})
            else:
                symbol = QgsFillSymbol.createSimple({
                    "color": color,
                    "outline_color": color,
                    "outline_width": "0.2",
                })
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()
            QgsProject.instance().addMapLayer(layer, False)
            group.addLayer(layer)
