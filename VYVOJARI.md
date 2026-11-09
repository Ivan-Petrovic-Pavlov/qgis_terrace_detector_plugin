# Príručka pre vývojárov / Developer guide

Tento dokument vysvetľuje rozhranie vlastného evaluátora a modelového ZIP balíka. / This document describes the custom evaluator interface and model ZIP bundle.

## Štruktúra pluginu / Plugin structure

- `terasy_eval/algorithms/terasy_eval_algorithm.py` – Processing nástroj na vyhodnotenie jednej alebo viacerých masiek.
- `terasy_eval/vyhodnot.py` – predvolený objektový evaluátor.
- `terasy_eval/evaluation_loader.py` – načítanie vstavaného alebo používateľského Python skriptu.
- `terasy_eval/model_config.py` a `terasy_eval/model_runner.py` – validácia a runner ukážkového modelového ZIP-u.
- `create_model_bundle.py` – vytvorenie ZIP-u s konfiguráciou, checkpointom a runnerom.
- `tests/` – testy konfigurácie, načítania evaluátora a GeoPackage tabuľky.

## Vlastný evaluátor / Custom evaluator

V QGIS voľba **Skript vyhodnotenia / Evaluation script** ponúka vstavaný alebo vlastný `.py` skript. Vstavaný skript je predvolená voľba; cesta k nemu sa zisťuje relatívne k nainštalovanému pluginu. Pri vlastnej voľbe sa použije cesta vybraná v samostatnom poli.

The **Evaluation script** selector offers the bundled evaluator or a custom `.py` file. The bundled evaluator is the default and is located relative to the installed plugin. For a custom evaluator, the path from the adjacent file parameter is used.

### Funkčné rozhranie / Function signature

Skript musí definovať volateľnú funkciu `vyhodnot`. Plugin ju zavolá s týmito pomenovanými argumentmi:

```python
def vyhodnot(
    predikcia_tif,
    terasy_shp,
    tolerancia_m=1.0,
    min_pokrytie=0.5,
    min_plocha_m2=1.0,
    vystup_gpkg=None,
):
    ...
```

The function is called once per selected model mask. `predikcia_tif` is the current mask path. `terasy_shp` is a temporary GeoPackage created from the selected QGIS reference layer. The other values come from the Processing parameters.

### Výsledky a výstup / Return value and output

Funkcia musí vrátiť slovník metrík so serializovateľnými hodnotami (text, celé čísla, desatinné čísla alebo `None`). Názvy kľúčov sa použijú ako stĺpce v porovnávacej tabuľke. Odporúčané kľúče vstavaného evaluátora sú `lokalita`, `tolerancia_m`, `pocet_gt`, `pocet_detekcii`, `TP`, `FN`, `FP`, `spravne_detekcie`, `precision`, `recall`, `f1`, `prah` a `min_plocha_m2`.

Return a dictionary of serializable metrics (strings, integers, floats, or `None`). The dictionary keys become columns in the shared comparison table. The bundled evaluator's keys are listed above.

Ak `vystup_gpkg` nie je `None`, vytvorte v ňom tieto vrstvy:

- `gt_terasy`: geometrie referenčných terás s poľom `stav`; používajte `TP` pre nájdené a `FN` pre nenájdené referenčné terasy.
- `detekcie`: geometrie nálezov modelu s poľom `stav`; používajte `TP` pre správne nálezy a `FP` pre falošné nálezy.

The plugin loads these layers, filters each status into its own QGIS layer, and groups the four results under the model name. Keep the table names and `stav` values stable. The selected reference vector can cover a larger area than the mask; the evaluator is responsible for considering only the mask extent.

Názvy vrstiev a hodnoty stavov sú súčasťou rozhrania pluginu. Ak ich zmeníte, treba upraviť aj `pridaj_vystupne_vrstvy()` v algoritme. / Layer names and status values are part of the plugin interface. If they change, update `pridaj_vystupne_vrstvy()` in the algorithm as well.

## Vytvorenie modelového balíka / Creating a model bundle

Balík je ZIP obsahujúci:

```text
config.json
model.pth
model_runner.py
README.txt
```

`checkpoint` a `inference_script` v konfigurácii musia byť názvy súborov v koreňovom priečinku ZIP-u, nie vnorené cesty.

### Konfigurácia / Configuration

Začnite súborom [`examples/models/fpn_resnet34_dem_config.json`](examples/models/fpn_resnet34_dem_config.json). Vyplňte `schema_version`, `name`, `checkpoint`, `inference_script` a tieto sekcie:

- `model`: názov architektúry a backbone-u. Pri predvolenom runneri ide o názvy dostupné v `segmentation_models_pytorch`.
- `input.type`: popisný typ vstupu, napr. `dem`, `iso` alebo `iso_dem`.
- `input.channels`: počet pásiem, ktoré model očakáva.
- `input.bands`: indexy pásiem rastra používané v modeli; indexovanie začína číslom 1. Ich počet musí byť rovnaký ako `channels`.
- `input.preprocessing`: názov stratégie implementovanej runnerom.
- `input.preprocessing_options`: voľby konkrétneho predspracovania.
- `inference.threshold`: predvolený prah v rozsahu 0 až 1; používateľ ho môže v QGIS zmeniť.
- `inference.thresholds_by_site`: voliteľné predvolené prahy podľa lokality; vyžaduje `site_checkpoints`.
- `inference.patch_size`, `stride`, `batch_size`: veľkosť výrezov, krok a počet výrezov v dávke.
- `site_checkpoints`: voliteľná mapa názvov lokalít na názvy checkpointov v ZIP-e. Ak je vyplnená, QGIS vyžaduje výber hradiska a sprístupní ho runneru ako `config["selected_site"]`.
- `training`: voliteľné údaje o tréningu, lokalitách a výbere modelu.

The config is validated before inference. The selected raster must have at least the declared number of bands, and every band index must exist. `stride` cannot exceed `patch_size`.

Pri balíku s `site_checkpoints` sa v inferenčnom nástroji zobrazí výber hradiska. Runner podľa `config["selected_site"]` načíta príslušný checkpoint. Voliteľné `inference.thresholds_by_site` určuje predvolený prah danej lokality; používateľ ho stále môže prepísať parametrom prahu. / Bundles with `site_checkpoints` expose a hillfort selector in the inference tool. The runner loads the matching checkpoint using `config["selected_site"]`. Optional `inference.thresholds_by_site` sets the site's default threshold, which can still be overridden.

### Rozhranie runnera / Runner interface

`model_runner.py` musí poskytovať dve funkcie:

```python
def load_model(config, checkpoint_path, torch, segmentation_models, device):
    """Construct, load, and return a model in eval mode."""


def preprocess_patch(config, bands, nodata_values):
    """Return finite float32 data with shape [channels, height, width]."""
```

`load_model` vráti PyTorch model v režime `eval()`. Plugin mu posiela dávku tvaru `[batch, channels, height, width]`; model musí vracať binárne logits tvaru `[batch, 1, height, width]`. Plugin aplikuje sigmoid a nakonfigurovaný prah. Výstupná maska má hodnoty 0/1 a preberá geometriu vstupného rastra.

`preprocess_patch` receives selected raster bands as a float array shaped `[channels, height, width]` and a list of per-band NoData values. It must return finite `float32` values with the same shape. It may implement any normalization appropriate to the checkpoint.

Vstavaný runner obsahuje stratégie `dem_per_patch`, `imagenet_rgb`, `imagenet_rgb_dem_per_patch` a `identity`. Pre iný spôsob predspracovania upravte alebo vymeňte `model_runner.py` a vložte ho do ZIP-u. / The bundled runner implements those four strategies. For other preprocessing, update or replace `model_runner.py` and include it in the ZIP.

Modelové ZIP-y môžu obsahovať spustiteľný Python kód. Používajte iba balíky z dôveryhodného zdroja a do runnera nedávajte tajné údaje. / Model ZIPs contain executable Python code. Only use trusted bundles and do not put secrets in a runner.

### Zabalenie / Build the ZIP

Z koreňového priečinka projektu spustite:

```bash
python create_model_bundle.py /path/to/checkpoint.pth /path/to/config.json examples/models/my_model.zip
```

Skript overí konfiguráciu a vytvorí ZIP s checkpointom, konfiguráciou, runnerom a stručným popisom. Veľké modelové ZIP-y sú v tomto projekte určené pre Git LFS. / The builder validates the config and creates a ZIP containing the checkpoint, config, runner, and short description. Large model ZIPs are tracked with Git LFS.

### Kontrola / Validation

```bash
python -m compileall terasy_eval tests create_model_bundle.py
PYTHONPATH=. python -m unittest discover -s tests -v
```

Potom otvorte QGIS a otestujte balík na malom rastri so známym CRS, rozmermi a počtom pásiem. Skontrolujte, že výstup má rovnakú mriežku ako vstup a že zmena prahu mení binárnu masku podľa očakávania. / Then test in QGIS with a small raster of known CRS, dimensions, and band count. Confirm that the output grid matches the input and threshold changes affect the binary mask as expected.
