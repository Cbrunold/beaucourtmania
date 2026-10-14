"""Legal-entity owners (personnes morales) of AD 134, of the estate and of the forest next to it.

Source: DGFiP « Fichiers des locaux et des parcelles des personnes morales », millésime 2025, aggregated as
« Unité foncière des personnes morales » on data.gouv.fr (unite-fonciere-2025-91-agg.parquet, 36 MB, not committed).
Owners who are private persons are never published: a parcel absent from this file belongs to private individuals.
Usage: python3 scripts/proprietaires.py data/raw/unite-fonciere-2025-91-agg.parquet
"""
import csv, sys
import pyarrow.parquet as pq
from shapely.geometry import box
from common import cadastre, write_csv, BOX

cols = ["idparc", "nom_proprio", "siren_proprio", "Type_proprietaire_complet", "Forme juridique de la personne morale",
        "groupe_personne_morale", "Nature culture"]
t = pq.read_table(sys.argv[1], columns=cols).to_pylist()
area = box(*BOX).buffer(100)  # the study box plus 100 m: catches the forest across the wall
ids = {}
for insee in ("91666", "91587"):  # Villejust, and Saulx-les-Chartreux just east of the wall
    ids.update({f["properties"]["id"]: f["properties"]["contenance"] for f in cadastre("parcelles", insee) if f["_l"].intersects(area)})
main = next(f["_l"] for f in cadastre("parcelles") if f["properties"]["id"] == "91666000AD0134")
shared = {f["properties"]["id"]: round(f["_l"].buffer(1.5).intersection(main.boundary).length)
          for insee in ("91666", "91587") for f in cadastre("parcelles", insee) if f["_l"].distance(main) < 2}
study = {r["id"]: r["role"] for r in csv.DictReader(open("data/cadastre/parcelles.csv"))}
rows = []
for r in t:
    for pid in (r["idparc"] or "").split("/"):
        if pid in ids:
            rows.append({"parcelle": pid, "role_etude": study.get(pid, "environs (forêt, voisinage)"), "contenance_m2": ids[pid],
                         "proprietaire": r["nom_proprio"], "siren": r["siren_proprio"], "type": r["Type_proprietaire_complet"],
                         "forme_juridique": r["Forme juridique de la personne morale"], "groupe": r["groupe_personne_morale"],
                         "limite_commune_avec_AD134_m": shared.get(pid, ""), "nature_culture": r["Nature culture"]})
rows.sort(key=lambda r: (r["proprietaire"], r["parcelle"]))
write_csv("data/cadastre/proprietaires_personnes_morales.csv", rows)
owned = {r["parcelle"] for r in rows}
print("AD 134 :", "personne morale" if "91666000AD0134" in owned else "absente du fichier → propriétaire(s) personne(s) physique(s)")
tot = {}
for r in rows:
    k = (r["proprietaire"], r["type"], r["groupe"])
    tot.setdefault(k, [0, 0]); tot[k][0] += 1; tot[k][1] += r["contenance_m2"]
for k, (n, s) in sorted(tot.items(), key=lambda x: -x[1][1]):
    print(f"{n:3d} parcelles {s:8d} m²  {k}")
