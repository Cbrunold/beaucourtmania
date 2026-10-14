"""Sales (DVF géolocalisées, Etalab) on AD 134 and on the estate cut out of it, 2021-2025.

Output: data/marche/dvf_propriete_et_lotissement.csv, dvf_commune_maisons_prix_m2.csv
"""
import csv, glob
from statistics import median
from common import write_csv

ids = {r["id"]: r["role"] for r in csv.DictReader(open("data/cadastre/parcelles.csv"))}
rows, maisons = [], {}
for fn in sorted(glob.glob("data/raw/dvf-91666-*.csv")):
    for r in csv.DictReader(open(fn)):
        if r["id_parcelle"] in ids:
            rows.append({"date": r["date_mutation"], "nature": r["nature_mutation"], "parcelle": r["id_parcelle"],
                         "role": ids[r["id_parcelle"]], "valeur_fonciere_eur": r["valeur_fonciere"],
                         "type_local": r["type_local"], "surface_bati_m2": r["surface_reelle_bati"],
                         "pieces": r["nombre_pieces_principales"], "surface_terrain_m2": r["surface_terrain"],
                         "nature_culture": r["nature_culture"], "id_mutation": r["id_mutation"]})
        if r["type_local"] == "Maison" and r["nature_mutation"] == "Vente" and r["surface_reelle_bati"] and r["valeur_fonciere"]:
            maisons.setdefault(r["id_mutation"], (r["date_mutation"][:4], float(r["valeur_fonciere"]), float(r["surface_reelle_bati"])))
write_csv("data/marche/dvf_propriete_et_lotissement.csv", rows)
by_year = {}
for y, v, s in maisons.values():
    if s > 0:
        by_year.setdefault(y, []).append(v / s)
write_csv("data/marche/dvf_commune_maisons_prix_m2.csv",
          [{"annee": y, "ventes_maisons": len(v), "prix_median_eur_m2": round(median(v))} for y, v in sorted(by_year.items())])
muts = {r["id_mutation"] for r in rows}
print(len(rows), "lignes DVF,", len(muts), "mutations sur la propriété et le lotissement")
for r in rows[:60]: print(r["date"], r["nature"], r["parcelle"][-6:], r["valeur_fonciere_eur"], r["type_local"], r["surface_bati_m2"], r["surface_terrain_m2"])
