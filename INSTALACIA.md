# Inštalácia pre používateľa / User installation guide

Tento návod je určený pre používateľa QGIS. Na bežné použitie netreba upravovať zdrojový kód ani modelovú konfiguráciu. / This guide is for QGIS users. Normal use does not require editing source code or model configuration.

## Čo potrebujete / What you need

- QGIS **3.20 alebo novší**. / QGIS **3.20 or later**.
- Tento priečinok pluginu, rozbalený v počítači. / This plugin folder, extracted on your computer.
- Pri vyhodnocovaní aj Python knižnice `NumPy`, `SciPy`, `GeoPandas` a `Shapely` dostupné priamo v QGIS. / Evaluation also requires `NumPy`, `SciPy`, `GeoPandas`, and `Shapely` in QGIS's own Python environment.
- Pri inferencii PyTorch a knižnice vyžadované konkrétnym modelom. Ukážkový model používa `segmentation_models_pytorch`. / Inference requires PyTorch and the libraries required by the selected model. The example uses `segmentation_models_pytorch`.

QGIS obsahuje vlastný Python. Inštalácia balíkov do iného systémového Pythonu alebo do virtuálneho prostredia projektu ich spravidla QGIS nesprístupní. / QGIS has its own Python environment. Installing packages into another system Python or a project virtual environment usually does not make them available to QGIS.

## Potrebné knižnice / Required libraries

Plugin sa môže nainštalovať aj bez knižníc pre vyhodnotenie a inferenciu, ale príslušný nástroj potom nepobeží. V QGIS otvorte **Zásuvné moduly → Python Console / Plugins → Python Console** a postupne overte:

```python
import numpy, scipy, geopandas, shapely
import torch, segmentation_models_pytorch
```

Prvé štyri knižnice sú potrebné na vyhodnotenie; `torch` a `segmentation_models_pytorch` sú potrebné pre ukážkovú inferenciu. Ak import zlyhá, knižnica nie je dostupná v Pythone QGIS. Požiadajte správcu počítača alebo postupujte podľa návodu pre konkrétny spôsob inštalácie QGIS (systémový balík, OSGeo4W, Flatpak a pod.). Neinštalujte ju naslepo do iného Pythonu.

The plugin can be installed without the evaluation and inference libraries, but those tools will not run until their dependencies are available. In the QGIS Python Console, check the imports above. If an import fails, ask your computer administrator or follow the dependency instructions for your specific QGIS installation (system package, OSGeo4W, Flatpak, etc.). Do not install packages into an unrelated Python environment.

## Linux

1. Otvorte priečinok `detekcia-teras-qgis-plugin` v správcovi súborov.
2. Kliknite pravým tlačidlom do priečinka a vyberte **Otvoriť v termináli**. Prípadne otvorte terminál a prejdite do tohto priečinka príkazom `cd`.
3. Spustite inštalátor:

```bash
bash ./nainstaluj.sh
```

4. Počkajte na správu o dokončení. Inštalátor skopíruje plugin do používateľského profilu QGIS.
5. Úplne zatvorte a znovu spustite QGIS.

Open the `detekcia-teras-qgis-plugin` folder in your file manager, open a terminal in that folder, and run `bash ./nainstaluj.sh`. When it reports completion, close and restart QGIS.

## Windows

1. V Prieskumníkovi súborov otvorte priečinok `detekcia-teras-qgis-plugin`.
2. Dvakrát kliknite na `nainstaluj.bat`. Ak sa zobrazí bezpečnostné potvrdenie, povoľte spustenie súboru.
3. Počkajte na správu **Plugin installation complete** a stlačte kláves na zatvorenie okna.
4. Úplne zatvorte a znovu spustite QGIS.

In File Explorer, open the plugin folder and double-click `nainstaluj.bat`. Allow it to run if Windows asks. After installation completes, restart QGIS.

## Zapnutie pluginu / Enable the plugin

1. V QGIS otvorte **Pluginy → Spravovať a inštalovať pluginy… / Plugins → Manage and Install Plugins…**.
2. V časti **Nainštalované / Installed** vyhľadajte a zapnite **Detekcia terás / Terrace detection**.
3. Otvorte **Spracovanie → Panel nástrojov / Processing → Toolbox**.
4. V skupine **Detekcia terás / Terrace detection** by mali byť nástroje inferencie a vyhodnotenia.

Ak plugin v zozname nevidíte, skontrolujte, či inštalátor vypísal úspešné dokončenie, a reštartujte QGIS. / If the plugin is not listed, confirm that the installer completed successfully and restart QGIS.

## Vyhľadanie terás / Search for terraces

1. Načítajte vstupný raster do projektu QGIS. Raster musí mať rovnaký počet pásiem a typ vstupu ako zvolený modelový balík. Pri ukážkovom balíku ide o jednopásmový DEM.
2. Otvorte **Vyhľadanie terás modelom (inferencia) / Model terrace search (inference)**.
3. Zvoľte vstupný raster z projektu a ZIP modelu. Ukážkový balík je v `examples/models/fpn_resnet34_dem.zip`.
4. Predvolený prah je nastavený v ZIP-e. Ak nemáte dôvod ho meniť, ponechajte ho bez zmeny.
5. Zadajte cestu výstupného GeoTIFF-u a spustite nástroj. Výsledná maska sa pridá do projektu.

Load the input raster into QGIS, open the inference tool, select the raster and model ZIP, then choose an output GeoTIFF. The example ZIP is `examples/models/fpn_resnet34_dem.zip` and expects a one-band DEM.

## Vyhodnotenie terás / Evaluate terraces

1. Načítajte do QGIS jednu alebo viac binárnych masiek vytvorených modelom.
2. Načítajte vektor ručne zakreslených referenčných terás. Môže pokrývať väčšie územie; nástroj použije iba časť v rozsahu každej masky.
3. Otvorte **Terasy – vyhodnotenie / Terrace evaluation** a vyberte masky aj spoločnú referenčnú vrstvu.
4. Vo voľbe **Skript vyhodnotenia / Evaluation script** ponechajte **Vstavaný skript / Built-in script**, ak nechcete použiť vlastný evaluátor.
5. Nastavte toleranciu a minimálnu plochu nálezu. Pri porovnávaní viacerých modelov použite rovnaké hodnoty.
6. Voliteľne zadajte cestu pre porovnávaciu tabuľku GeoPackage. Ak ju nevyplníte, vytvorí sa dočasná tabuľka.
7. Spustite nástroj. V paneli vrstiev pribudne skupina pre každý model a spoločná tabuľka metrík.

Load one or more binary model masks and the manually mapped reference vector. In the evaluation tool, choose the built-in evaluator, set matching tolerance and minimum detection area, optionally choose a GeoPackage destination, and run. QGIS adds one group of result layers per model and a comparison table.

## Ak niečo nefunguje / Troubleshooting

- **Plugin sa nezobrazuje:** reštartujte QGIS a skontrolujte, či je zapnutý v správcovi pluginov.
- **Chýbajúca knižnica:** knižnicu treba nainštalovať do Python prostredia používaného QGIS, nie iba do systémového Pythonu. Pri vyhodnocovaní sú potrebné NumPy, SciPy, GeoPandas a Shapely; pri inferencii PyTorch a závislosti modelu.
- **Nesprávny počet pásiem:** vybraný raster musí zodpovedať vstupu uvedenému v ZIP balíku.
- **Vlastný výstup sa stratil:** ak pri vyhodnotení nevyberiete GeoPackage cieľ, výsledky sú v dočasnom priečinku QGIS. Zadajte trvalú cestu, ak si ich chcete ponechať.

For missing dependencies, install them into the Python environment used by QGIS. A temporary GeoPackage may be removed by QGIS; choose a permanent output path to retain it.

## Ďalšie informácie / More information

Význam metrík, formát vlastného evaluátora a tvorba modelového ZIP balíka sú v [príručke pre vývojárov](VYVOJARI.md). Všeobecný opis pluginu je v [README](README.md). / Metric definitions, the custom evaluator interface, and model ZIP packaging are in the [developer guide](VYVOJARI.md). See the [README](README.md) for a general overview.
