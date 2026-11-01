from .provider import TerasyEvalProvider


class TerasyEvalPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        from qgis.core import QgsApplication

        self.provider = TerasyEvalProvider()
        QgsApplication.processingRegistry().addProvider(
            self.provider
        )

    def unload(self):
        from qgis.core import QgsApplication

        if self.provider:
            QgsApplication.processingRegistry().removeProvider(
                self.provider
            )
            self.provider = None
