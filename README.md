# Detekcia terás / Terrace detection

Samostatný QGIS plugin na vyhľadávanie archeologických terás v rasterových dátach a vyhodnotenie modelových nálezov voči ručne zakresleným terasám.

A standalone QGIS plugin for archaeological terrace search in raster data and evaluation of model detections against manually mapped terraces.

## Funkcie / Features

Plugin poskytuje dva nástroje v QGIS Processing Toolbox, v skupine **Detekcia terás / Terrace detection**:

- **Vyhľadanie terás modelom (inferencia) / Model terrace search (inference):** spustí modelový ZIP balík nad rasterom z projektu QGIS a vytvorí binárnu masku zarovnanú so vstupom.
- **Terasy – vyhodnotenie / Terrace evaluation:** vyhodnotí jednu alebo viac masiek voči spoločnému vektoru terás, vytvorí samostatné vrstvy TP/FN/FP pre každý model a porovnávaciu tabuľku metrík.

The plugin provides two Processing tools: model inference from a ZIP bundle and multi-model evaluation against one shared reference vector.

Ukážkový modelový ZIP pre jednopásmový DEM je v [`examples/models/fpn_resnet34_dem.zip`](examples/models/fpn_resnet34_dem.zip). Predvolený prah balíka je 0,2. Ukážkový výstup na Tribeči je v [`examples/tribec_fpn_dem_prediction.tif`](examples/tribec_fpn_dem_prediction.tif).

An example model ZIP for one-band DEM input is included. Its default threshold is 0.2. A sample Tribeč output is also available.

## Dokumentácia / Documentation

- [Inštalácia pre používateľa / User installation guide](INSTALACIA.md): inštalácia v Linuxe a Windows, zapnutie pluginu a bežný postup v QGIS.
- [Príručka pre vývojárov / Developer guide](VYVOJARI.md): vlastný evaluátor, konfigurácia modelu, inference runner a tvorba modelového ZIP-u.

## Požiadavky / Requirements

QGIS 3.20 alebo novší. Vyhodnotenie potrebuje GDAL, NumPy, SciPy, GeoPandas a Shapely v Python prostredí QGIS. Inferencia potrebuje PyTorch a prípadné ďalšie závislosti modelového balíka. / QGIS 3.20 or later. Evaluation requires GDAL, NumPy, SciPy, GeoPandas, and Shapely in QGIS Python. Inference requires PyTorch and any model-bundle dependencies.

Modelové ZIP-y sú sledované cez Git LFS. / Model ZIP bundles are tracked with Git LFS.
