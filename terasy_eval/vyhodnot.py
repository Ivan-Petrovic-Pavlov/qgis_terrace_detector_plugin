"""Standalone copy of the terrace-object evaluator bundled with the QGIS plugin."""
import os

import numpy as np
import geopandas as gpd
from scipy import ndimage
from shapely.geometry import box, shape
from shapely.ops import unary_union


LOKALITY = ["Hradisko_Ladzany", "Hradisko_Sasovske_Podhradie", "Hradisko_Sitno", "Hradisko_Tribec"]


def nacitaj_raster(path):
    try:
        from osgeo import gdal
        ds = gdal.Open(path)
        if ds is None:
            raise FileNotFoundError(path)
        return ds.GetRasterBand(1).ReadAsArray(), ds.GetGeoTransform(), ds.GetProjection()
    except ImportError:
        import rasterio
        with rasterio.open(path) as src:
            return src.read(1), src.transform.to_gdal(), src.crs.to_wkt()


def rozsah(gt, array_shape):
    height, width = array_shape
    x0, y0 = gt[0], gt[3]
    return x0, y0 + height * gt[5], x0 + width * gt[1], y0


def nacitaj_terasy(terasy_shp, gt, array_shape, crs_wkt):
    terasy = gpd.read_file(terasy_shp)
    terasy["gt_id"] = np.arange(len(terasy))
    if crs_wkt and terasy.crs is not None:
        terasy = terasy.to_crs(crs_wkt)
    raster_bounds = box(*rozsah(gt, array_shape))
    terasy = terasy[terasy.intersects(raster_bounds)].copy()
    terasy["geometry"] = terasy.geometry.intersection(raster_bounds)
    return terasy[~terasy.geometry.is_empty].reset_index(drop=True)


def lokalita_z_nazvu(path):
    name = os.path.splitext(os.path.basename(path))[0]
    for locality in LOKALITY:
        if locality in name:
            return locality
    for suffix in ("_prediction", "_predikcia", "_pred", "_prob"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.replace("04A_", "").replace("_VIS_ISO", "").replace("_DEM25cm", "")


def _body_na_ciare(geometry, step):
    parts = getattr(geometry, "geoms", [geometry])
    points = []
    for part in parts:
        if part.length == 0:
            continue
        distances = np.append(np.arange(0.0, part.length, step), part.length)
        points.extend((point.x, point.y) for point in (part.interpolate(distance) for distance in distances))
    return np.array(points).reshape(-1, 2)


def _na_pixely(xy, gt, array_shape):
    columns = np.floor((xy[:, 0] - gt[0]) / gt[1]).astype(int)
    rows = np.floor((xy[:, 1] - gt[3]) / gt[5]).astype(int)
    inside = (rows >= 0) & (rows < array_shape[0]) & (columns >= 0) & (columns < array_shape[1])
    return rows[inside], columns[inside]


def _rasterizuj_ciary(terasy, gt, array_shape):
    mask = np.zeros(array_shape, bool)
    for geometry in terasy.geometry:
        rows, columns = _na_pixely(_body_na_ciare(geometry, abs(gt[1]) / 4), gt, array_shape)
        mask[rows, columns] = True
    return mask


def _obrysy(labels, gt, crs_wkt):
    labels = labels.astype(np.int32)
    try:
        import rasterio.features
        from affine import Affine
        shapes = rasterio.features.shapes(labels, mask=labels > 0, connectivity=8,
                                          transform=Affine.from_gdal(*gt))
        parts = {}
        for geometry, value in shapes:
            parts.setdefault(int(value), []).append(shape(geometry))
    except ImportError:
        from osgeo import gdal, ogr, osr
        dataset = gdal.GetDriverByName("MEM").Create("", labels.shape[1], labels.shape[0], 1, gdal.GDT_Int32)
        dataset.SetGeoTransform(gt)
        dataset.SetProjection(crs_wkt)
        dataset.GetRasterBand(1).WriteArray(labels)
        spatial_ref = osr.SpatialReference(wkt=crs_wkt) if crs_wkt else None
        vector = ogr.GetDriverByName("Memory").CreateDataSource("")
        layer = vector.CreateLayer("d", srs=spatial_ref)
        layer.CreateField(ogr.FieldDefn("v", ogr.OFTInteger))
        band = dataset.GetRasterBand(1)
        gdal.Polygonize(band, band, layer, 0, ["8CONNECTED=8"])
        from shapely import wkb
        parts = {}
        for feature in layer:
            parts.setdefault(feature.GetField(0), []).append(
                wkb.loads(bytes(feature.GetGeometryRef().ExportToWkb()))
            )
    return {key: unary_union(geometries) for key, geometries in parts.items()}


def _spocitaj(mask, gt, terasy, tolerancia_m, min_pokrytie, min_plocha_m2, crs_wkt=None):
    pixel_size = abs(gt[1])
    labels, count = ndimage.label(mask, structure=np.ones((3, 3)))
    ids = np.arange(1, count + 1)
    areas = ndimage.sum(np.ones_like(labels, dtype=np.uint8), labels, ids) * pixel_size * pixel_size if count else np.array([])
    small_ids = ids[areas < min_plocha_m2]
    if len(small_ids):
        labels[np.isin(labels, small_ids)] = 0
    ids = ids[areas >= min_plocha_m2]
    areas = areas[areas >= min_plocha_m2]
    detected_mask = labels > 0

    if detected_mask.any():
        distance_to_detection = ndimage.distance_transform_edt(~detected_mask) * pixel_size
    else:
        distance_to_detection = np.full(mask.shape, np.inf)

    reference = terasy[["gt_id", "geometry"]].copy()
    reference["dlzka_m"] = reference.length
    coverage = []
    for geometry in reference.geometry:
        rows, columns = _na_pixely(_body_na_ciare(geometry, pixel_size), gt, mask.shape)
        coverage.append(float((distance_to_detection[rows, columns] <= tolerancia_m).mean()) if len(rows) else 0.0)
    reference["pokrytie"] = coverage
    reference["stav"] = np.where(reference["pokrytie"] >= min_pokrytie, "TP", "FN")
    del distance_to_detection

    if len(ids):
        lines = _rasterizuj_ciary(terasy, gt, mask.shape)
        close_to_line = ndimage.distance_transform_edt(~lines) * pixel_size <= tolerancia_m if lines.any() else np.zeros(mask.shape, bool)
        detection_coverage = ndimage.mean(close_to_line, labels, ids)
        outlines = _obrysy(labels, gt, crs_wkt)
        detections = gpd.GeoDataFrame({
            "det_id": ids.astype(int),
            "plocha_m2": np.round(areas, 2),
            "pokrytie": np.round(detection_coverage, 4),
            "stav": np.where(detection_coverage >= min_pokrytie, "TP", "FP"),
        }, geometry=[outlines[index] for index in ids], crs=terasy.crs)
    else:
        detections = gpd.GeoDataFrame({"det_id": [], "plocha_m2": [], "pokrytie": [], "stav": []},
                                      geometry=[], crs=terasy.crs)
    reference["pokrytie"] = reference["pokrytie"].round(4)
    reference["dlzka_m"] = reference["dlzka_m"].round(2)
    return reference, detections


def vyhodnot(predikcia_tif, terasy_shp, tolerancia_m=1.0, min_pokrytie=0.5,
             min_plocha_m2=1.0, vystup_gpkg=None, prah=0.5):
    prediction, gt, crs_wkt = nacitaj_raster(predikcia_tif)
    is_probability = np.issubdtype(prediction.dtype, np.floating)
    mask = prediction > prah if is_probability else prediction > 0
    terasy = nacitaj_terasy(terasy_shp, gt, prediction.shape, crs_wkt)
    locality = lokalita_z_nazvu(predikcia_tif)
    reference, detections = _spocitaj(mask, gt, terasy, tolerancia_m, min_pokrytie,
                                      min_plocha_m2, crs_wkt)

    tp = int((reference["stav"] == "TP").sum())
    fn = int((reference["stav"] == "FN").sum())
    fp = int((detections["stav"] == "FP").sum())
    detection_count = len(detections)
    correct_detections = detection_count - fp
    precision = correct_detections / detection_count if detection_count else 0.0
    recall = tp / len(reference) if len(reference) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    if vystup_gpkg:
        if os.path.exists(vystup_gpkg):
            os.remove(vystup_gpkg)
        reference.assign(lokalita=locality).to_file(vystup_gpkg, layer="gt_terasy", driver="GPKG")
        detections.assign(lokalita=locality).to_file(vystup_gpkg, layer="detekcie", driver="GPKG")

    return {
        "lokalita": locality,
        "tolerancia_m": tolerancia_m,
        "pocet_gt": len(reference),
        "pocet_detekcii": detection_count,
        "TP": tp,
        "FN": fn,
        "FP": fp,
        "spravne_detekcie": correct_detections,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "prah": prah if is_probability else (
            "Už aplikovaný pri vytvorení binárnej masky / Already applied when creating the binary mask"
        ),
        "min_plocha_m2": min_plocha_m2,
    }
