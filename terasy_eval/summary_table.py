"""Write attribute-only result tables to GeoPackage with GDAL/OGR."""

import os

from osgeo import ogr


def write_gpkg_table(path, table_name, rows):
    if not rows:
        raise ValueError("At least one result row is required.")

    driver = ogr.GetDriverByName("GPKG")
    if driver is None:
        raise RuntimeError("The GDAL GeoPackage driver is unavailable.")

    dataset = ogr.Open(path, 1) if os.path.exists(path) else driver.CreateDataSource(path)
    if dataset is None:
        raise OSError(f"Could not open or create {path}.")

    try:
        existing_index = next(
            (
                index
                for index in range(dataset.GetLayerCount())
                if dataset.GetLayer(index).GetName() == table_name
            ),
            None,
        )
        if existing_index is not None and dataset.DeleteLayer(existing_index) != 0:
            raise OSError(f"Could not replace the existing table '{table_name}'.")

        layer = dataset.CreateLayer(
            table_name,
            geom_type=ogr.wkbNone,
            options=["ASPATIAL_VARIANT=GPKG_ATTRIBUTES"],
        )
        if layer is None:
            raise OSError(f"Could not create the attribute table '{table_name}'.")

        field_types = {}
        field_names = list(rows[0])
        for name in field_names:
            sample = next((row.get(name) for row in rows if row.get(name) is not None), "")
            field_type = (
                ogr.OFTInteger64 if isinstance(sample, int)
                else ogr.OFTReal if isinstance(sample, float)
                else ogr.OFTString
            )
            if layer.CreateField(ogr.FieldDefn(name, field_type)) != 0:
                raise OSError(f"Could not create field '{name}'.")
            field_types[name] = field_type

        for row in rows:
            feature = ogr.Feature(layer.GetLayerDefn())
            for name in field_names:
                value = row.get(name)
                if value is None:
                    continue
                field_type = field_types[name]
                if field_type == ogr.OFTInteger64:
                    feature.SetField(name, int(value))
                elif field_type == ogr.OFTReal:
                    feature.SetField(name, float(value))
                else:
                    feature.SetField(name, str(value))
            if layer.CreateFeature(feature) != 0:
                raise OSError(f"Could not write result row for '{row.get('model', '')}'.")
            feature = None

        layer.SyncToDisk()
        dataset.FlushCache()
    finally:
        dataset = None