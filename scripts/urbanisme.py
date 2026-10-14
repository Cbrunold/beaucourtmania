"""PLU of Villejust (approved 30/06/2025) applied to AD 134: area of each zone and prescription, and Géorisques.

Source: Géoportail de l'Urbanisme (API Carto), queried with the AD 134 polygon by scripts/fetch.sh; Géorisques API.
Outputs: data/urbanisme/zonage_AD134.csv, prescriptions_AD134.csv, data/risques/risques.csv, arretes_catnat.csv.
"""
import json
from shapely.geometry import shape
from common import main_parcel, to_l93, write_csv, RAW

main = main_parcel()["_l"]


def cut(kind, label):
    rows = []
    for f in json.load(open(f"{RAW}/gpu_AD134_{kind}.json"))["features"]:
        g = to_l93(shape(f["geometry"]))
        p = f["properties"]
        inter = g.intersection(main)
        rows.append({"type": kind, "libelle": p.get("libelle"), "detail": p.get("libelong") or p.get("txt") or "",
                     "code": p.get("typezone") or p.get("typepsc") or p.get("typeinf") or "",
                     "surface_dans_AD134_m2": round(inter.area) if inter.area else "",
                     "longueur_dans_AD134_m": round(inter.length) if not inter.area else "",
                     "part_AD134_pct": round(100 * inter.area / main.area, 1) if inter.area else "",
                     "reglement": p.get("nomfic", "")})
    return rows

z = cut("zone-urba", "zone")
write_csv("data/urbanisme/zonage_AD134.csv", z)
pr = cut("prescription-surf", "") + cut("prescription-lin", "") + cut("info-surf", "") + cut("assiette-sup-s", "")
write_csv("data/urbanisme/prescriptions_AD134.csv", pr)

rows = [{"source": "Géorisques GASPAR (commune)", "risque": r["libelle_risque_long"], "niveau": "recensé"}
        for r in json.load(open(f"{RAW}/georisques_gaspar.json"))["data"][0]["risques_detail"]]
rows.append({"source": "Géorisques RGA (point AD 134)", "risque": "Retrait-gonflement des argiles",
             "niveau": json.load(open(f"{RAW}/georisques_rga.json"))["exposition"]})
s = next(x for x in json.load(open(f"{RAW}/georisques_sismique.json"))["data"] if x["code_insee"] == "91666")
rows.append({"source": "Géorisques zonage sismique", "risque": "Séisme", "niveau": s["zone_sismicite"]})
rows.append({"source": "Géorisques radon", "risque": "Radon",
             "niveau": "potentiel catégorie " + json.load(open(f"{RAW}/georisques_radon.json"))["data"][0]["classe_potentiel"]})
rows.append({"source": "Géorisques cavités (1 km)", "risque": "Cavités souterraines",
             "niveau": f'{json.load(open(f"{RAW}/georisques_cavites.json"))["results"]} recensée(s)'})
rows.append({"source": "Géorisques SSP (1 km)", "risque": "Sites et sols pollués",
             "niveau": f'{json.load(open(f"{RAW}/georisques_ssp.json")).get("results", "?")} recensé(s)'})
write_csv("data/risques/risques.csv", rows)
cat = json.load(open(f"{RAW}/georisques_catnat.json"))["data"]
cat.sort(key=lambda x: x["date_debut_evt"][-4:] + x["date_debut_evt"][3:5])
write_csv("data/risques/arretes_catnat.csv", [{"debut": x["date_debut_evt"], "fin": x["date_fin_evt"],
          "risque": x["libelle_risque_jo"], "publication_jo": x["date_publication_jo"]} for x in cat])
for r in z + pr + rows: print(r)
print(len(cat), "arrêtés CatNat")
