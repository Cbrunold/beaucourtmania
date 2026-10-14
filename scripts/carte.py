"""Maps of AD 134: cadastre on aerial photo (cartes/plan_propriete.png) and on LiDAR relief with zoning (cartes/relief_zonage.png)."""
import csv, json
import numpy as np
import rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from shapely.geometry import shape
from common import BOX, cadastre, main_parcel, to_l93, wfs, MAIN

X0, Y0, X1, Y1 = BOX
EXT = (X0, X1, Y0, Y1)
main = main_parcel()["_l"]
roles = {r["id"]: r["role"] for r in csv.DictReader(open("data/cadastre/parcelles.csv"))}
owners = {r["parcelle"]: r["proprietaire"] for r in csv.DictReader(open("data/cadastre/proprietaires_personnes_morales.csv"))}


def outline(ax, g, **kw):
    for p in getattr(g, "geoms", [g]):
        if p.geom_type == "Polygon":
            ax.plot(*p.exterior.xy, **kw)
        elif p.geom_type == "LineString":
            ax.plot(*p.xy, **kw)


def base(ax, title):
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.set_xlabel("X Lambert-93 (m)"); ax.set_ylabel("Y Lambert-93 (m)")
    ax.set_title(title, fontsize=11)
    ax.annotate("N ↑", xy=(0.97, 0.96), xycoords="axes fraction", fontsize=13, weight="bold", ha="right", color="white")
    ax.plot([X0 + 15, X0 + 65], [Y0 + 12, Y0 + 12], color="white", lw=4)
    ax.text(X0 + 40, Y0 + 16, "50 m", color="white", ha="center", weight="bold")


# --- 1. Aerial photo + cadastre + owners + walls + forest
fig, ax = plt.subplots(figsize=(12, 13), dpi=130)
ax.imshow(plt.imread("data/histoire/ortho_ORTHOPHOTOS.jpg"), extent=EXT)
for f in cadastre("parcelles"):
    pid, g = f["properties"]["id"], f["_l"]
    if not g.intersects(main.envelope.buffer(60)):
        continue
    if pid == MAIN:
        continue
    lot = roles.get(pid, "").startswith("lotissement")
    outline(ax, g, color="#7fd3ff" if lot else "white", lw=0.8)
    c = g.representative_point()
    if X0 < c.x < X1 and Y0 < c.y < Y1 and g.area > 150:
        lab = f'{f["properties"]["section"]} {f["properties"]["numero"]}'
        if pid in owners and g.area > 600:
            lab += "\n" + owners[pid][:22]
        ax.text(c.x, c.y, lab, fontsize=6.5, color="white", ha="center", va="center")
for p, g in wfs("wfs_BDTOPO_V3_foret_publique.json"):
    outline(ax, g, color="#3ddc84", lw=2, ls="--")
for p, g in wfs("wfs_BDTOPO_V3_construction_lineaire.json"):
    if g.distance(main) < 5:
        outline(ax, g, color="#ff4fd8", lw=3.5)
outline(ax, main, color="#ffd23f", lw=3)
c = main.representative_point()
ax.text(644395, 6842590, "AD 134\n28 202 m²\npropriété Beaucourt", color="#ffd23f", weight="bold", fontsize=11, ha="center",
        bbox=dict(fc="black", alpha=0.45, ec="none"))
ax.plot([], [], color="#ffd23f", lw=3, label="AD 134 (maison, jardin, allée, bois)")
ax.plot([], [], color="#7fd3ff", lw=1.5, label="lotissement détaché de la propriété (2019-2021)")
ax.plot([], [], color="#ff4fd8", lw=3.5, label="murs (IGN BD TOPO)")
ax.plot([], [], color="#3ddc84", lw=2, ls="--", label="Forêt départementale de Saulx-les-Chartreux")
ax.legend(loc="lower right", fontsize=8.5, framealpha=0.85)
base(ax, "23 rue des Pavillons, 91140 Villejust : cadastre (PCI Etalab 2026-09) sur photo aérienne IGN")
plt.tight_layout(); plt.savefig("cartes/plan_propriete.png"); plt.close()

# --- 2. LiDAR relief + contour lines + PLU zoning + trees
with rasterio.open("data/lidar/lidarhd_MNT_50cm.tif") as r:
    mnt = r.read(1).astype(float)
with rasterio.open("data/lidar/lidarhd_MNH_50cm.tif") as r:
    mnh = r.read(1).astype(float)
mnt[mnt < -1000] = np.nan; mnh[mnh < -1000] = np.nan
fig, ax = plt.subplots(figsize=(12, 13), dpi=130)
hs = LightSource(azdeg=315, altdeg=35).hillshade(np.nan_to_num(mnt, nan=np.nanmin(mnt)), vert_exag=4, dx=0.5, dy=0.5)
ax.imshow(hs, cmap="gray", extent=EXT)
im = ax.imshow(mnt, cmap="terrain", extent=EXT, alpha=0.45)
fig.colorbar(im, ax=ax, shrink=0.5, label="Altitude du sol (m NGF-IGN69, LiDAR HD 2023)")
xs = np.linspace(X0, X1, mnt.shape[1]); ys = np.linspace(Y1, Y0, mnt.shape[0])
cs = ax.contour(xs, ys, mnt, levels=np.arange(146, 162, 1), colors="black", linewidths=0.4)
ax.clabel(cs, fmt="%d", fontsize=6)
ax.imshow(np.where(mnh > 5, mnh, np.nan), cmap="Greens", extent=EXT, alpha=0.35, vmin=0, vmax=30)
styles = {"zone-urba": None, "prescription-surf": None}
for kind, col in (("zone-urba", "#ff8c00"), ("prescription-surf", "#00a86b")):
    for f in json.load(open(f"data/raw/gpu_AD134_{kind}.json"))["features"]:
        g = to_l93(shape(f["geometry"]))
        if g.intersection(main).area < 50:
            continue
        lab = f["properties"]["libelle"]
        ls = "-" if kind == "zone-urba" else (":" if "isi" in lab else "--")
        outline(ax, g.intersection(main.buffer(40)), color=col if "isi" not in lab else "#1f77ff", lw=1.8, ls=ls)
outline(ax, main, color="#ffd23f", lw=3)
trees = list(csv.DictReader(open("data/vegetation/arbres_lidar_AD134.csv")))
ax.scatter([float(t["x_l93"]) for t in trees], [float(t["y_l93"]) for t in trees],
           s=[float(t["hauteur_m"]) * 3 for t in trees], c="#0b6623", edgecolors="white", linewidths=0.4, zorder=5)
ax.plot([], [], color="#ff8c00", lw=1.8, label="limites de zones PLU (N / UHb)")
ax.plot([], [], color="#00a86b", lw=1.8, ls="--", label="Espace boisé classé (L.113-1 CU)")
ax.plot([], [], color="#1f77ff", lw=1.8, ls=":", label="bande de 50 m de lisière (SDRIF)")
ax.scatter([], [], s=60, c="#0b6623", edgecolors="white", label=f"{len(trees)} arbres détectés (taille ∝ hauteur)")
ax.legend(loc="lower right", fontsize=8.5, framealpha=0.85)
base(ax, "AD 134 : relief LiDAR HD, courbes de niveau 1 m, arbres et zonage du PLU (30/06/2025)")
plt.tight_layout(); plt.savefig("cartes/relief_zonage.png"); plt.close()
