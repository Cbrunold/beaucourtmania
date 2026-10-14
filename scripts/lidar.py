"""Topography, land cover, trees and walls of AD 134 from IGN LiDAR HD (flown April-May 2023).

Inputs: 50 cm rasters MNT (ground), MNS (surface), MNH (height above ground) from scripts/fetch.sh, cadastre, BD TOPO walls.
Optional: python3 scripts/lidar.py <LHD_FXX_0644_6843.copc.laz> also clips the classified point cloud to the study box.
Outputs into data/lidar/ and data/vegetation/.
"""
import json, sys
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from scipy import ndimage
from shapely.geometry import mapping, shape, Point
from common import main_parcel, wfs, write_csv, BOX, to_l93

D = "data/lidar"
R = {k: rasterio.open(f"{D}/lidarhd_{k}_50cm.tif") for k in ("MNT", "MNS", "MNH")}
A = {k: np.where((r.read(1) == r.nodata) | (r.read(1) < -1000), np.nan, r.read(1)).astype(float) for k, r in R.items()}
T, SHP = R["MNT"].transform, A["MNT"].shape
PX = abs(T.a * T.e)  # 0.25 m²
gy, gx = np.gradient(A["MNT"], abs(T.e), T.a)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
aspect = (np.degrees(np.arctan2(-gx, gy)) + 360) % 360  # direction the slope faces, 0 = north


def mask(g):
    return ~geometry_mask([mapping(g)], out_shape=SHP, transform=T)


main = main_parcel()["_l"]
inside = mask(main)
bats = [to_l93(shape(f["geometry"])) for f in json.load(open("data/cadastre/batiments.geojson"))["features"]
        if f["properties"]["parcelle"] == "91666000AD0134"]
bati = np.zeros(SHP, bool)
for b in bats:
    bati |= mask(b)
h = A["MNH"]

# --- Land cover of AD 134 from heights: building (cadastre), canopy > 5 m, shrubs 2-5 m, low < 2 m
cov = {"bâti (cadastre)": inside & bati,
       "canopée arborée (> 5 m)": inside & ~bati & (h > 5),
       "arbustes / haies (2-5 m)": inside & ~bati & (h > 2) & (h <= 5),
       "pelouse, sol nu, allée (< 2 m)": inside & ~bati & (h <= 2)}
rows = [{"occupation": k, "surface_m2": round(m.sum() * PX), "part_pct": round(100 * m.sum() / inside.sum(), 1),
         "hauteur_mediane_m": round(float(np.nanmedian(h[m])), 1) if m.any() else ""} for k, m in cov.items()]
write_csv("data/vegetation/occupation_sol_AD134.csv", rows)

# --- Topography of AD 134 and of each land-cover class
t = A["MNT"]
def topo(name, m):
    return {"zone": name, "surface_m2": round(m.sum() * PX), "alt_min_m": round(np.nanmin(t[m]), 2),
            "alt_max_m": round(np.nanmax(t[m]), 2), "alt_moy_m": round(np.nanmean(t[m]), 2),
            "denivele_m": round(np.nanmax(t[m]) - np.nanmin(t[m]), 2),
            "pente_mediane_deg": round(np.nanmedian(slope[m]), 1), "pente_p90_deg": round(np.nanpercentile(slope[m], 90), 1),
            "exposition_mediane_deg": round(float(np.nanmedian(aspect[m])))}
trows = [topo("AD 134 entière", inside)] + [topo(k, m) for k, m in cov.items() if m.sum() > 40]
write_csv(f"{D}/topographie_AD134.csv", trows)

# --- Buildings on AD 134: height and volume
brows = []
for b in bats:
    m = mask(b.buffer(-0.5))
    if m.sum() < 4:
        continue
    sol = np.nanmedian(t[mask(b.buffer(2).difference(b))])
    hh = A["MNS"][m] - sol
    brows.append({"centre_x_l93": round(b.centroid.x, 1), "centre_y_l93": round(b.centroid.y, 1), "emprise_m2": round(b.area, 1),
                  "alt_sol_pied_m": round(float(sol), 2), "hauteur_mediane_m": round(float(np.nanmedian(hh)), 2),
                  "hauteur_max_m": round(float(np.nanmax(hh)), 2),
                  "volume_hors_sol_m3": round(float(np.nansum(np.clip(hh, 0, None)) * PX * b.area / b.buffer(-0.5).area)),
                  "niveaux_estimes": int(max(1, round(float(np.nanpercentile(hh, 75)) / 3.0)))})
write_csv(f"{D}/hauteurs_batiments_AD134.csv", brows)

# --- Individual trees: local maxima of the smoothed canopy height (window ~ 5 m), height > 5 m
hs = ndimage.gaussian_filter(np.nan_to_num(h), 1.0)
peaks = (hs == ndimage.maximum_filter(hs, size=9)) & (hs > 5) & ~bati
inv = __import__("pyproj").Transformer.from_crs(2154, 4326, always_xy=True)
trees = []
for r, c in zip(*np.nonzero(peaks)):
    x, y = rasterio.transform.xy(T, r, c)
    if not main.buffer(3).contains(Point(x, y)):
        continue
    # crown radius: distance at which the canopy falls below 60 % of the top, averaged over 8 directions
    top, rad = hs[r, c], []
    for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        k = 1
        while 0 <= r + k * dr < SHP[0] and 0 <= c + k * dc < SHP[1] and hs[r + k * dr, c + k * dc] > 0.6 * top and k < 30:
            k += 1
        rad.append(k * 0.5 * (2 ** 0.5 if dr and dc else 1))
    lon, lat = inv.transform(x, y)
    trees.append({"x_l93": round(x, 1), "y_l93": round(y, 1), "lon": round(lon, 7), "lat": round(lat, 7),
                  "hauteur_m": round(float(h[r, c]), 1), "rayon_couronne_m": round(float(np.mean(rad)), 1),
                  "alt_sol_m": round(float(t[r, c]), 2), "dans_AD134": main.contains(Point(x, y))})
trees.sort(key=lambda d: -d["hauteur_m"])
write_csv("data/vegetation/arbres_lidar_AD134.csv", trees)

# --- Walls (BD TOPO "Mur") along AD 134: ground profile every metre on both faces
wrows, prows = [], []
for k, (p, g) in enumerate(x for x in wfs("wfs_BDTOPO_V3_construction_lineaire.json") if x[1].distance(main) < 5):
    L = g.length
    alts = []
    for d in np.arange(0, L, 1.0):
        pt = g.interpolate(d)
        rr, cc = rasterio.transform.rowcol(T, pt.x, pt.y)
        hm = float(np.nanmax(A["MNS"][max(rr - 1, 0):rr + 2, max(cc - 1, 0):cc + 2]) - t[rr, cc])
        alts.append(float(t[rr, cc]))
        prows.append({"mur": k, "abscisse_m": round(d, 1), "x_l93": round(pt.x, 1), "y_l93": round(pt.y, 1),
                      "alt_sol_m": round(float(t[rr, cc]), 2), "hauteur_sursol_max_m": round(hm, 2)})
    wrows.append({"mur": k, "nature": p.get("nature"), "longueur_m": round(L, 1),
                  "alt_debut_m": round(alts[0], 2), "alt_fin_m": round(alts[-1], 2),
                  "denivele_le_long_m": round(max(alts) - min(alts), 2),
                  "sur_limite_AD134_m": round(g.intersection(main.boundary.buffer(2)).length, 1),
                  "bdtopo_cree": p.get("date_creation", "")[:10], "precision_m": p.get("precision_planimetrique")})
write_csv(f"{D}/murs_AD134.csv", wrows)
write_csv(f"{D}/murs_profil_1m.csv", prows)

# --- Optional: clip the classified point cloud (tile not committed, ~220 MB)
if len(sys.argv) > 1:
    import laspy
    CL = {1: "non classé", 2: "sol", 3: "végétation basse", 4: "végétation moyenne", 5: "végétation haute", 6: "bâtiment",
          9: "eau", 17: "pont", 64: "sursol pérenne", 65: "artefact", 66: "points virtuels", 67: "divers - bâti"}
    las = laspy.read(sys.argv[1])
    X0, Y0, X1, Y1 = BOX
    m = (las.x >= X0) & (las.x <= X1) & (las.y >= Y0) & (las.y <= Y1)
    hdr = las.header
    hdr.vlrs = laspy.vlrs.vlrlist.VLRList([v for v in hdr.vlrs if "copc" not in v.user_id.lower()])  # laspy cannot write COPC
    out = laspy.LasData(hdr)
    out.evlrs = []
    out.points = las.points[m]
    out.write(f"{D}/villejust_nuage_points.laz")
    cls, n = np.unique(np.asarray(out.classification), return_counts=True)
    write_csv(f"{D}/nuage_points_classes.csv", [{"classe": int(c), "libelle": CL.get(int(c), "?"), "nb_points": int(k)} for c, k in zip(cls, n)])
    print(f"nuage : {m.sum()} points, {m.sum() / ((X1 - X0) * (Y1 - Y0)):.1f} pts/m²")

for r in rows + trows + brows + wrows:
    print(r)
print(f"{len(trees)} arbres détectés ; plus haut {trees[0]['hauteur_m']} m ; "
      f"{sum(x['hauteur_m'] >= 20 for x in trees)} de plus de 20 m")
