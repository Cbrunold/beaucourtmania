"""Shared helpers: study parcels, reprojection to Lambert-93 (EPSG:2154), CSV writing."""
import csv, gzip, json, os
import numpy as np
from pyproj import Transformer
from shapely import transform
from shapely.geometry import shape

RAW = "data/raw"
INSEE = "91666"
MAIN = "91666000AD0134"  # 23 rue des Pavillons: house, garden, access drive, wood (28 202 m²)
BOX = (644150, 6842400, 644500, 6842780)  # study box in Lambert-93, same as scripts/fetch.sh

_tr = {e: Transformer.from_crs(e, 2154, always_xy=True) for e in (4326, 3857)}


def to_l93(g, epsg=4326):
    if epsg == 2154:
        return g
    t = _tr[epsg]
    return transform(g, lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))


def wfs(name):
    """A WFS GeoJSON from data/raw as [(properties, l93 geometry)], whatever CRS the service answered in."""
    d = json.load(open(f"{RAW}/{name}"))
    crs = (d.get("crs") or {}).get("properties", {}).get("name", "4326")
    epsg = 2154 if "2154" in crs else 3857 if "3857" in crs else 4326
    return [(f["properties"], to_l93(shape(f["geometry"]), epsg)) for f in d["features"] if f["geometry"]]


def cadastre(layer, insee=INSEE):
    feats = json.load(gzip.open(f"{RAW}/cadastre-{insee}-{layer}.json.gz"))["features"]
    for f in feats:
        f["_l"] = to_l93(shape(f["geometry"]))
    return feats


def main_parcel():
    return next(f for f in cadastre("parcelles") if f["properties"]["id"] == MAIN)


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
