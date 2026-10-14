"""AD 134 (the family property) and every parcel touching it, including the estate cut out of it.

Source: Etalab cadastre (PCI vecteur, DGFiP) in data/raw/. Outputs into data/cadastre/:
parcelles.csv/.geojson, batiments.csv/.geojson, sommets_AD134_lambert93.csv.
"""
import json
from shapely.geometry import mapping
from common import cadastre, write_csv, MAIN

TOL = 0.5  # metres: shared edges in the PCI are not always bit-identical
OUT = "data/cadastre"

parcels = cadastre("parcelles")
bats = cadastre("batiments")
by_id = {f["properties"]["id"]: f for f in parcels}
main = by_id[MAIN]["_l"]
hull = main.convex_hull

rows, feats = [], []
for f in parcels:
    p, g = f["properties"], f["_l"]
    pid = p["id"]
    touches = g.distance(main) <= TOL
    enclosed = hull.contains(g.representative_point())
    if pid != MAIN and not (touches or enclosed):
        continue
    if pid == MAIN:
        role = "propriété Beaucourt (maison, jardin, allée, bois)"
    elif p["created"] >= "2019-01-01":
        role = "lotissement (détaché de la propriété, créé le " + p["created"] + ")"
    else:
        role = "parcelle voisine"
    blds = [b for b in bats if b["_l"].intersection(g).area > 0.5 * b["_l"].area]
    r = {"id": pid, "section": p["section"], "numero": p["numero"], "role": role,
         "contenance_cadastrale_m2": p["contenance"], "surface_calculee_m2": round(g.area, 1),
         "perimetre_m": round(g.length, 1),
         "limite_commune_avec_AD134_m": round(g.buffer(TOL).intersection(main.boundary).length, 1) if pid != MAIN else "",
         "nb_batiments": len(blds), "emprise_bati_m2": round(sum(b["_l"].area for b in blds), 1),
         "cree_au_cadastre": p["created"], "maj_cadastre": p["updated"]}
    rows.append(r)
    feats.append({"type": "Feature", "geometry": f["geometry"], "properties": r})

rows.sort(key=lambda r: (r["id"] != MAIN, r["role"], r["id"]))
write_csv(f"{OUT}/parcelles.csv", rows)
json.dump({"type": "FeatureCollection", "features": feats}, open(f"{OUT}/parcelles.geojson", "w"), ensure_ascii=False, indent=1)

# Buildings on the property and on the estate
ids = {r["id"] for r in rows}
brows, bfeats = [], []
for b in bats:
    on = [i for i in ids if b["_l"].intersection(by_id[i]["_l"]).area > 0.5 * b["_l"].area]
    if not on:
        continue
    r = {"parcelle": on[0], "type": {"01": "bâti dur", "02": "bâti léger"}.get(b["properties"].get("type"), ""),
         "emprise_m2": round(b["_l"].area, 1), "perimetre_m": round(b["_l"].length, 1),
         "centre_x_l93": round(b["_l"].centroid.x, 1), "centre_y_l93": round(b["_l"].centroid.y, 1),
         "cree_au_cadastre": b["properties"].get("created")}
    brows.append(r)
    bfeats.append({"type": "Feature", "geometry": b["geometry"], "properties": r})
write_csv(f"{OUT}/batiments.csv", brows)
json.dump({"type": "FeatureCollection", "features": bfeats}, open(f"{OUT}/batiments.geojson", "w"), ensure_ascii=False, indent=1)

# Exact delimitation of AD 134: every vertex in Lambert-93 and the length of each side
import numpy as np
from common import _tr
inv = __import__("pyproj").Transformer.from_crs(2154, 4326, always_xy=True)
vrows = []
for k, poly in enumerate(getattr(main, "geoms", [main])):
    c = list(poly.exterior.coords)
    for i in range(len(c) - 1):
        (x, y), (x2, y2) = c[i], c[i + 1]
        lon, lat = inv.transform(x, y)
        vrows.append({"polygone": k, "ordre": i, "x_l93": round(x, 2), "y_l93": round(y, 2),
                      "lon": round(lon, 7), "lat": round(lat, 7), "cote_vers_suivant_m": round(((x2 - x) ** 2 + (y2 - y) ** 2) ** 0.5, 2)})
write_csv(f"{OUT}/sommets_AD134_lambert93.csv", vrows)

lot = [r for r in rows if r["role"].startswith("lotissement")]
print(f"AD 134 : {by_id[MAIN]['properties']['contenance']} m², {len(vrows)} sommets, périmètre {main.length:.0f} m")
print(f"Lotissement : {len(lot)} parcelles, {sum(r['contenance_cadastrale_m2'] for r in lot)} m², "
      f"{sum(r['nb_batiments'] for r in lot)} bâtiments, {sum(r['emprise_bati_m2'] for r in lot):.0f} m² d'emprise")
for b in brows:
    if b["parcelle"] == MAIN:
        print("bâtiment sur AD 134:", b)
