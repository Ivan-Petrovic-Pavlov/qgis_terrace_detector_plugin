
"""Standalone terrace-object evaluator.

A reference terrace is counted once, even when several disconnected prediction
components cover the same reference line. Coverage is measured by the share of
the reference line lying within the matching tolerance of the assigned
prediction polygons.
"""
import os

import geopandas as gpd
import numpy as np
from scipy import ndimage
from shapely.geometry import box, shape
from shapely.ops import unary_union


LOKALITY = [
    "Hradisko_Ladzany",
    "Hradisko_Sasovske_Podhradie",
    "Hradisko_Sitno",
    "Hradisko_Tribec",
]
PARTIAL_MIN_COVERAGE = 0.01


def nacitaj_raster(path):
    try:
        from osgeo import gdal
        ds = gdal.Open(path)
        if ds is None:
            raise FileNotFoundError(path)
        band = ds.GetRasterBand(1)
        array = band.ReadAsArray()
        nodata = band.GetNoDataValue()
        if nodata is not None:
            array = np.where(array == nodata, 0, array)
        return array, ds.GetGeoTransform(), ds.GetProjection()
    except ImportError:
        import rasterio
        with rasterio.open(path) as src:
            array = src.read(1)
            if src.nodata is not None:
                array = np.where(array == src.nodata, 0, array)
            return array, src.transform.to_gdal(), src.crs.to_wkt() if src.crs else ""


def _over_parametre(gt, array_shape):
    if abs(gt[2]) > 1e-9 or abs(gt[4]) > 1e-9:
        raise ValueError("Rotated rasters are not supported; use a north-up raster.")
    pixel_x, pixel_y = abs(float(gt[1])), abs(float(gt[5]))
    if pixel_x <= 0 or pixel_y <= 0 or not np.isclose(pixel_x, pixel_y, rtol=1e-6):
        raise ValueError("The evaluator requires square raster pixels.")
    if len(array_shape) != 2:
        raise ValueError("The prediction raster must contain exactly one 2D band.")
    return pixel_x


def rozsah(gt, array_shape):
    height, width = array_shape
    x0, y0 = gt[0], gt[3]
    return x0, y0 + height * gt[5], x0 + width * gt[1], y0


def nacitaj_terasy(terasy_shp, gt, array_shape, crs_wkt):
    terasy = gpd.read_file(terasy_shp)
    if terasy.empty:
        terasy["gt_id"] = np.array([], dtype=int)
        return terasy
    if terasy.crs is None:
        raise ValueError("The reference terrace layer has no CRS.")
    if crs_wkt:
        terasy = terasy.to_crs(crs_wkt)
    terasy = terasy[terasy.geometry.notna() & ~terasy.geometry.is_empty].copy()
    terasy = terasy[terasy.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    terasy["gt_id"] = np.arange(len(terasy), dtype=int)
    raster_bounds = box(*rozsah(gt, array_shape))
    terasy = terasy[terasy.intersects(raster_bounds)].copy()
    terasy["geometry"] = terasy.geometry.intersection(raster_bounds)
    terasy = terasy[~terasy.geometry.is_empty & (terasy.geometry.length > 0)].copy()
    return terasy.reset_index(drop=True)


def lokalita_z_nazvu(path):
    name = os.path.splitext(os.path.basename(path))[0]
    for locality in LOKALITY:
        if locality in name:
            return locality
    for suffix in ("_prediction", "_predikcia", "_pred", "_prob"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.replace("04A_", "").replace("_VIS_ISO", "").replace("_DEM25cm", "")


def _obrysy(labels, gt, crs_wkt):
    labels = labels.astype(np.int32, copy=False)
    try:
        import rasterio.features
        from affine import Affine
        parts = {}
        shapes = rasterio.features.shapes(
            labels, mask=labels > 0, connectivity=8,
            transform=Affine.from_gdal(*gt),
        )
        for geom, value in shapes:
            parts.setdefault(int(value), []).append(shape(geom))
    except ImportError:
        from osgeo import gdal, ogr, osr
        ds = gdal.GetDriverByName("MEM").Create(
            "", labels.shape[1], labels.shape[0], 1, gdal.GDT_Int32
        )
        ds.SetGeoTransform(gt)
        if crs_wkt:
            ds.SetProjection(crs_wkt)
        ds.GetRasterBand(1).WriteArray(labels)
        srs = osr.SpatialReference(wkt=crs_wkt) if crs_wkt else None
        vector = ogr.GetDriverByName("Memory").CreateDataSource("")
        layer = vector.CreateLayer("detections", srs=srs)
        layer.CreateField(ogr.FieldDefn("value", ogr.OFTInteger))
        band = ds.GetRasterBand(1)
        gdal.Polygonize(band, band, layer, 0, ["8CONNECTED=8"])
        from shapely import wkb
        parts = {}
        for feature in layer:
            value = int(feature.GetField(0))
            if value > 0:
                parts.setdefault(value, []).append(
                    wkb.loads(bytes(feature.GetGeometryRef().ExportToWkb()))
                )
    return {key: unary_union(geometries) for key, geometries in parts.items()}


def _spocitaj(mask, gt, terasy, tolerancia_m, min_pokrytie,
              min_plocha_m2, crs_wkt=None):
    pixel_size = abs(float(gt[1]))
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=np.uint8))
    if count:
        ids = np.arange(1, count + 1)
        pixel_counts = ndimage.sum(
            np.ones(labels.shape, dtype=np.uint8), labels, ids
        )
        areas = pixel_counts * pixel_size ** 2
        keep = ids[areas >= min_plocha_m2]
        labels[~np.isin(labels, keep)] = 0
        # Relabel after filtering so polygon IDs are contiguous and stable.
        labels, count = ndimage.label(labels > 0, structure=np.ones((3, 3), dtype=np.uint8))
    ids = np.arange(1, count + 1)
    areas = (
        ndimage.sum(np.ones(labels.shape, dtype=np.uint8), labels, ids) * pixel_size ** 2
        if count else np.array([], dtype=float)
    )
    component_geometries = _obrysy(labels, gt, crs_wkt) if count else {}


    # Assign prediction components to ALL reference terraces within
    # the matching tolerance. One component may detect multiple terraces.
    assigned = {int(row.gt_id): [] for row in terasy.itertuples()}
    unmatched = []

    for component_id in ids:
        geom = component_geometries[int(component_id)]
        matched = False

        for row in terasy.itertuples():
            distance = geom.distance(row.geometry)

            if distance <= tolerancia_m:
                assigned[int(row.gt_id)].append(geom)
                matched = True

        if not matched:
            unmatched.append((int(component_id), geom))


    ref_rows = []
    detection_rows = []
    for row in terasy.itertuples():
        gt_id = int(row.gt_id)
        pieces = assigned.get(gt_id, [])
        if pieces:
            model_area = unary_union(pieces)
            covered_length = row.geometry.intersection(
                model_area.buffer(tolerancia_m)
            ).length
            coverage = min(1.0, max(0.0, covered_length / row.geometry.length))
            status = "TP" if coverage >= min_pokrytie else (
                "Partial" if coverage > PARTIAL_MIN_COVERAGE else "FN"
            )
            if status in ("TP", "Partial"):
                detection_rows.append({
                    "det_id": gt_id,
                    "gt_id": gt_id,
                    "plocha_m2": round(sum(p.area for p in pieces), 2),
                    "pokrytie": round(coverage, 4),
                    "stav": status,
                    "geometry": model_area,
                })
        else:
            coverage = 0.0
            status = "FN"
        ref_rows.append({
            "gt_id": gt_id,
            "dlzka_m": round(row.geometry.length, 2),
            "pokrytie": round(coverage, 4),
            "stav": status,
            "geometry": row.geometry,
        })

    # Components not associated with any reference terrace are false
    # detections. Components assigned to the same terrace are one model
    # detection, regardless of how many disconnected pieces they contain.
    next_id = len(terasy)
    for component_id, geom in unmatched:
        detection_rows.append({
            "det_id": next_id + component_id,
            "gt_id": -1,
            "plocha_m2": round(geom.area, 2),
            "pokrytie": 0.0,
            "stav": "FP",
            "geometry": geom,
        })

    reference = gpd.GeoDataFrame(ref_rows, geometry="geometry", crs=terasy.crs)
    detections = gpd.GeoDataFrame(
        detection_rows,
        columns=["det_id", "gt_id", "plocha_m2", "pokrytie", "stav", "geometry"],
        geometry="geometry",
        crs=terasy.crs,
    )
    return reference, detections


def vyhodnot(predikcia_tif, terasy_shp, tolerancia_m=1.0,
             min_pokrytie=0.5, min_plocha_m2=1.0,
             vystup_gpkg=None, prah=0.5):
    if tolerancia_m < 0:
        raise ValueError("Matching tolerance must be >= 0.")
    if not (PARTIAL_MIN_COVERAGE < min_pokrytie <= 1):
        raise ValueError("Minimum coverage threshold must be > 0.01 and <= 1.")
    if min_plocha_m2 < 0:
        raise ValueError("Minimum detection area must be >= 0.")

    prediction, gt, crs_wkt = nacitaj_raster(predikcia_tif)
    pixel_size = _over_parametre(gt, prediction.shape)
    if not crs_wkt:
        raise ValueError("The prediction raster has no CRS.")
    is_probability = np.issubdtype(prediction.dtype, np.floating)
    mask = np.isfinite(prediction) & (prediction > prah) if is_probability else prediction > 0
    terasy = nacitaj_terasy(terasy_shp, gt, prediction.shape, crs_wkt)

    # Pixel-area calculations and all distance parameters are in map units.
    # The QGIS processing algorithm additionally checks that map units are metres.
    locality = lokalita_z_nazvu(predikcia_tif)
    reference, detections = _spocitaj(
        mask, gt, terasy, tolerancia_m, min_pokrytie, min_plocha_m2, crs_wkt
    )

    tp = int((reference["stav"] == "TP").sum())
    partial = int((reference["stav"] == "Partial").sum())
    fn = int((reference["stav"] == "FN").sum())
    fp = int((detections["stav"] == "FP").sum())
    detected_terraces = tp + partial
    detection_count = len(detections)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / len(reference) if len(reference) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    extended_recall = detected_terraces / len(reference) if len(reference) else 0.0

    if vystup_gpkg:
        if os.path.exists(vystup_gpkg):
            os.remove(vystup_gpkg)
        reference.to_file(vystup_gpkg, layer="gt_terasy", driver="GPKG")
        detections.to_file(vystup_gpkg, layer="detekcie", driver="GPKG")

    return {
        "lokalita": locality,
        "tolerancia_m": tolerancia_m,
        "pocet_gt": len(reference),
        "pocet_oblasti_modelu": detection_count,
        "detekovane_terasy": detected_terraces,
        "TP": tp,
        "Partial": partial,
        "FN": fn,
        "FP": fp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "partial_recall": round(extended_recall, 4),
        "f1": round(f1, 4),
        "prah": prah if is_probability else (
            "Already applied when creating the binary mask"
        ),
        "min_plocha_m2": min_plocha_m2,
        "min_pokrytie": min_pokrytie,
        "partial_min_pokrytie": PARTIAL_MIN_COVERAGE,
    }
