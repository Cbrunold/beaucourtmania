#!/bin/bash
# Re-download every public source into data/raw/ (then run the python scripts, see README).
# Study: 23 rue des Pavillons, 91140 Villejust (INSEE 91666), parcel AD 134 and the estate cut out of it.
# The proxy in cloud sessions drops connections now and then: every download retries.
set -u
cd "$(dirname "$0")/../data/raw"
get(){ for i in 1 2 3 4 5 6; do curl -sS -m 300 -f -L "$1" -o "$2" && return 0; sleep $((i*3)); done; echo "ÉCHEC $1" >&2; }

INSEE=91666; DEP=91
LON=2.2430; LAT=48.6815                       # centre of AD 134 (house + garden)
X0=644150; Y0=6842400; X1=644500; Y1=6842780  # study box, Lambert-93 (350 x 380 m)
BB4326="48.6790,2.2380,48.6845,2.2480"        # same area in WGS84 (lat,lon order for WFS 2.0)
GEOM=$(python3 -c "import urllib.parse,json;print(urllib.parse.quote(json.dumps({'type':'Point','coordinates':[$LON,$LAT]})))")

# --- Adresse & cadastre (PCI vecteur DGFiP, Etalab, millésime 2026-09-01) ---
get "https://api-adresse.data.gouv.fr/search/?q=23+rue+des+pavillons+91140+villejust&limit=3" geocode.json
B=https://cadastre.s3.rbx.io.cloud.ovh.net/etalab-cadastre/2026-09-01/geojson/communes/$DEP/$INSEE
for l in parcelles batiments sections lieux_dits; do get "$B/cadastre-$INSEE-$l.json.gz" cadastre-$INSEE-$l.json.gz; done
# The east edge of AD 134 is the commune boundary: the forest beyond is in Saulx-les-Chartreux (91587)
for l in parcelles batiments; do get "${B%/*}/91587/cadastre-91587-$l.json.gz" cadastre-91587-$l.json.gz; done
# Parcellaire Express: bornes de limite de propriété (survey markers), when IGN has any
get "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=CADASTRALPARCELS.PARCELLAIRE_EXPRESS:borne_limite_propriete&OUTPUTFORMAT=application/json&BBOX=$BB4326,urn:ogc:def:crs:EPSG::4326" pci_bornes.json

# --- Transactions (DVF géolocalisées) : sales on the estate and the commune ---
for y in 2021 2022 2023 2024 2025; do get "https://files.data.gouv.fr/geo-dvf/latest/csv/$y/communes/$DEP/$INSEE.csv" dvf-$INSEE-$y.csv; done

# --- Urbanisme : PLU via Géoportail de l'Urbanisme (API Carto) ---
for k in zone-urba document prescription-surf prescription-lin info-surf assiette-sup-s; do get "https://apicarto.ign.fr/api/gpu/$k?geom=$GEOM" gpu_$k.json; done

# --- Risques (Géorisques) ---
get "https://www.georisques.gouv.fr/api/v1/gaspar/risques?code_insee=$INSEE" georisques_gaspar.json
get "https://www.georisques.gouv.fr/api/v1/gaspar/catnat?code_insee=$INSEE&page_size=100" georisques_catnat.json
get "https://www.georisques.gouv.fr/api/v1/rga?latlon=$LON,$LAT" georisques_rga.json
get "https://www.georisques.gouv.fr/api/v1/zonage_sismique?latlon=$LON,$LAT" georisques_sismique.json
get "https://www.georisques.gouv.fr/api/v1/radon?code_insee=$INSEE" georisques_radon.json
get "https://www.georisques.gouv.fr/api/v1/cavites?latlon=$LON,$LAT&rayon=1000" georisques_cavites.json
get "https://www.georisques.gouv.fr/api/v1/ssp?latlon=$LON,$LAT&rayon=1000" georisques_ssp.json

# --- Végétation, forêt publique, haies, murs (IGN BD TOPO / BD Forêt / ONF) ---
for T in BDTOPO_V3:zone_de_vegetation BDTOPO_V3:haie BDTOPO_V3:foret_publique BDTOPO_V3:construction_lineaire \
         BDTOPO_V3:troncon_de_route BDTOPO_V3:batiment LANDCOVER.FORESTINVENTORY.V2:formation_vegetale ONF.FORETS_PUBLIQUES:ONF_FORETS_PUBLIQUES; do
  get "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=$T&OUTPUTFORMAT=application/json&COUNT=2000&BBOX=$BB4326,urn:ogc:def:crs:EPSG::4326" "wfs_${T//[:.]/_}.json"
done

# --- LiDAR HD IGN : tile metadata, then the 50 cm rasters for the study box ---
get "https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=IGNF_LIDAR-HD_METADONNEE:metadata&OUTPUTFORMAT=application/json&COUNT=5&BBOX=$BB4326,urn:ogc:def:crs:EPSG::4326" lidar_meta.json
W=$(( (X1-X0)*2 )); H=$(( (Y1-Y0)*2 ))
for L in MNT MNS MNH; do
  get "https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=IGNF_LIDAR-HD_${L}_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93&STYLES=&CRS=EPSG:2154&BBOX=$X0,$Y0,$X1,$Y1&WIDTH=$W&HEIGHT=$H&FORMAT=image/geotiff" ../lidar/lidarhd_${L}_50cm.tif
done
# The point cloud tile (≈220 MB, not committed): url in lidar_meta.json, then scripts/lidar_points.py

# --- Photos aériennes : today, infrared (vegetation health) and history back to 1950 ---
for L in ORTHOIMAGERY.ORTHOPHOTOS ORTHOIMAGERY.ORTHOPHOTOS.IRC ORTHOIMAGERY.ORTHOPHOTOS2000-2005 ORTHOIMAGERY.ORTHOPHOTOS.IRC.2018 ORTHOIMAGERY.ORTHOPHOTOS.IRC.2021; do
  get "https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=$L&STYLES=&CRS=EPSG:2154&BBOX=$X0,$Y0,$X1,$Y1&WIDTH=1400&HEIGHT=1520&FORMAT=image/jpeg" ../histoire/ortho_${L#ORTHOIMAGERY.}.jpg
done
for L in 1950-1965 1965-1980 1980-1995; do  # the historical layers only answer in PNG
  get "https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ORTHOIMAGERY.ORTHOPHOTOS.$L&STYLES=&CRS=EPSG:2154&BBOX=$X0,$Y0,$X1,$Y1&WIDTH=1400&HEIGHT=1520&FORMAT=image/png" ../histoire/ortho_ORTHOPHOTOS.$L.png
done

# --- Propriétaires personnes morales (DGFiP 2025, 36 MB, not committed) ---
get "https://static.data.gouv.fr/resources/unite-fonciere-des-personnes-morales-locaux-et-parcelles/20260526-130814/unite-fonciere-2025-91-agg.parquet" unite-fonciere-2025-91-agg.parquet
# --- PLU : règlement écrit et graphique, PADD, annexes (Géoportail de l'Urbanisme) ---
D=cd16edb8a13bc7d84f663406fe4b6f2d  # 91666_PLU_20250630
for n in reglement reglement_graphique padd procedure info_surf_03_00_ens info_lin_99_00_cloture; do
  get "https://www.geoportail-urbanisme.gouv.fr/api/document/$D/files/91666_${n}_20250630.pdf" ../urbanisme/91666_${n}_20250630.pdf
done

# --- Sols : carte des sols INRAE (1/1 000 000). The BRGM geological map 1/50 000 (geoservices.brgm.fr) is blocked
# from cloud sessions: open https://infoterre.brgm.fr at the address (feuille 219 Corbeil-Essonnes) from a normal browser.
get "https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=INRA.CARTE.SOLS&STYLES=&CRS=EPSG:2154&BBOX=$((X0-2000)),$((Y0-2000)),$((X1+2000)),$((Y1+2000))&WIDTH=1000&HEIGHT=1000&FORMAT=image/png" ../sols/carte_sols_inrae.png
