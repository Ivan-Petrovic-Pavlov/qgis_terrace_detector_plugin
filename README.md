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

## Štruktúra projektu / Project structure

Projekt je organizovaný do niekoľkých hlavných adresárov, ktoré oddeľujú implementáciu QGIS pluginu, ukážkové dáta, testy a pomocné nástroje.

The project is organized into several main directories separating the QGIS plugin implementation, example data, tests, and supporting utilities.

## Štruktúra projektu / Project structure

Projekt je organizovaný do niekoľkých hlavných adresárov, ktoré oddeľujú implementáciu QGIS pluginu, predtrénované modely, ukážkové modelové balíky, testy a pomocné nástroje.

The project is organized into several main directories separating the QGIS plugin implementation, trained models, example model bundles, tests, and supporting utilities.

text

```text
qgis_terrace_detector_plugin/
│
├── terasy_eval/
│   ├── algorithms/
│   │   └── terasy_eval_algorithm.py
│   ├── vyhodnot.py
│   ├── evaluation_loader.py
│   ├── model_config.py
│   └── model_runner.py
│
├── models/
│   ├── EffB3 VIS_ISO ensemble with post-processing.zip
│   └── EffB3 VIS_ISO ensemble without post-processing.zip
│
├── examples/
│   └── models/
│       └── fpn_resnet34_dem.zip
│
├── tests/
│   └── ...
│
├── create_model_bundle.py
│
├── README.md
├── INSTALACIA.md
└── VYVOJARI.md
```

### Popis adresárov a súborov / Directory and file description

- **`terasy_eval/`** – hlavný zdrojový kód QGIS pluginu. Obsahuje implementáciu nástrojov na detekciu a vyhodnocovanie archeologických terás.
  - **`algorithms/`** – implementácia algoritmov dostupných prostredníctvom QGIS Processing Toolbox.
    - `terasy_eval_algorithm.py` – hlavný Processing algoritmus zabezpečujúci spustenie detekcie a vyhodnotenia terás.
  - `vyhodnot.py` – predvolený evaluátor na porovnávanie modelových detekcií s referenčnými dátami.
  - `evaluation_loader.py` – zabezpečuje načítanie vstavaného alebo používateľského evaluátora.
  - `model_config.py` – načítanie a validácia konfigurácie modelového balíka.
  - `model_runner.py` – zabezpečuje vykonávanie modelovej inferencie vrátane spracovania vstupných rastrových dát.
- **`models/`** – adresár obsahujúci modelové balíky určené na použitie v plugine. Obsahuje predtrénované modely architektúry EfficientNet-B3 (EffB3) pre dáta VIS\_ISO v dvoch variantoch:
  - `EffB3 VIS_ISO ensemble with post-processing.zip` – ensemble model s následným post-processingom detekcií.
  - `EffB3 VIS_ISO ensemble without post-processing.zip` – ensemble model bez následného post-processingu.
- **`examples/`** – ukážkové modelové balíky určené na demonštráciu a testovanie funkcionality pluginu.
  - **`models/`** – obsahuje ukážkové modelové balíky, napríklad `fpn_resnet34_dem.zip`, využívajúci architektúru FPN s backbone ResNet34 pre DEM vrstvu.
- **`tests/`** – automatizované testy určené na overovanie správnosti jednotlivých komponentov pluginu, konfigurácie modelov, načítania evaluátorov a súvisiacich funkcionalít.
- **`create_model_bundle.py`** – pomocný skript na vytváranie modelových ZIP balíkov obsahujúcich konfiguráciu, modelové váhy a potrebné komponenty na vykonávanie inferencie.
- **`README.md`** – hlavná dokumentácia projektu s opisom funkcionality pluginu a základnými informáciami o jeho používaní.
- **`INSTALACIA.md`** – používateľská príručka opisujúca postup inštalácie a konfigurácie pluginu v prostredí QGIS.
- **`VYVOJARI.md`** – technická dokumentácia určená vývojárom. Opisuje architektúru pluginu, rozhranie evaluátora, konfiguráciu modelov a tvorbu vlastných modelových balíkov.


- **`terasy_eval/`** – the main source code of the QGIS plugin. It contains the implementation of tools for detecting and evaluating archaeological terraces.
  - **`algorithms/`** – implementation of algorithms available through the QGIS Processing Toolbox.
    - `terasy_eval_algorithm.py` – the main Processing algorithm responsible for running terrace detection and evaluation.
  - `vyhodnot.py` – the default evaluator used to compare model predictions with reference data.
  - `evaluation_loader.py` – handles loading the built-in or user-defined evaluator.
  - `model_config.py` – handles loading and validation of model bundle configurations.
  - `model_runner.py` – handles model inference, including the processing of input raster data.
- **`models/`** – directory containing model bundles intended for use with the plugin. It includes pretrained EfficientNet-B3 (EffB3) ensemble models for VIS_ISO data in two variants:
  - `EffB3 VIS_ISO ensemble with post-processing.zip` – an ensemble model with post-processing applied to the detections.
  - `EffB3 VIS_ISO ensemble without post-processing.zip` – an ensemble model without post-processing.
- **`examples/`** – example model bundles intended to demonstrate and test the plugin's functionality.
- **`models/`** – contains example model bundles, such as `fpn_resnet34_dem.zip`, which uses an FPN architecture with a ResNet34 backbone for DEM data.
- **`tests/`** – automated tests designed to verify the correctness of individual plugin components, model configurations, evaluator loading, and related functionality.
- **`create_model_bundle.py`** – a utility script for creating model ZIP bundles containing the configuration, model weights, and required components for running inference.
- **`README.md`** – the main project documentation, providing an overview of the plugin's functionality and basic usage information.
- **`INSTALACIA.md`** – the user guide describing the installation and configuration of the plugin in QGIS.
- **`VYVOJARI.md`** – technical documentation intended for developers. It describes the plugin architecture, evaluator interface, model configuration, and the creation of custom model bundles.
