from qgis.core import QgsProcessingProvider
from .algorithms.terasy_eval_algorithm import (
    TerasyEvalAlgorithm
)
from .algorithms.inferencia_algorithm import InferenciaTerasyAlgorithm


class TerasyEvalProvider(QgsProcessingProvider):

    def id(self):
        return "terrace_detection"

    def name(self):
        return "Detekcia terás / Terrace detection"

    def loadAlgorithms(self):
        self.addAlgorithm(InferenciaTerasyAlgorithm())
        self.addAlgorithm(TerasyEvalAlgorithm())
