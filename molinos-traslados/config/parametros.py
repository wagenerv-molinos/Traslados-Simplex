"""
parametros.py
Pesos de calibracion del modelo de traslados. Ajustar ACA, sin tocar la
logica en src/model.py. Solo importa el RATIO relativo entre parametros,
no el valor absoluto.
"""

SKUS = [56218, 56225, 56226]
NODOS = ["Pilar", "Chacabuco", "CDT"]

# LOCID de IBP (planning area MOLIBP) por nodo interno. Confirmado contra IBP el
# 2026-08-20 filtrando SCNID eq 'Baseline 2' (ver src/ibp_client.py).
LOC_IDS_IBP = {"Pilar": "2501", "Chacabuco": "2502", "CDT": "1018"}

# LOCID adicionales de IBP a sumar en el forecast de cada nodo (ver
# docs/checkpoint_proyecto.md). El forecast de CDT en LOCID='1018' (Lucchetti)
# todavia no contempla la totalidad de la demanda del centro - falta sumarle
# el de '8108' (Esteban Echeverria). A pedido del usuario, 2026-08-20.
LOC_IDS_IBP_FORECAST_EXTRA = {"CDT": ["8108"]}

ARCOS = [
    ("Pilar", "CDT"),
    ("Chacabuco", "CDT"),
    ("Chacabuco", "Pilar"),
]

BASE = 5
COSTO_ARCO = {
    ("Pilar", "CDT"): BASE,
    ("Chacabuco", "CDT"): BASE,
    ("Chacabuco", "Pilar"): 2 * BASE,
}

ALPHA = {"Pilar": 400, "Chacabuco": 400, "CDT": 100}
BETA = {"Pilar": 10, "Chacabuco": 10, "CDT": 20}
ALPHA_PEDIDO = 4000
DELTA = 0
CAP_N = {"Pilar": 1600, "Chacabuco": 1100}
CAMION_PALLETS = 25
LEAD_TIME = 1
CAJAS_POR_PALLET = 70

# Dias sobre los que se prorratea el pendiente confirmado (CONF, "sin armar" de
# Pendientes_AFO) como consumo diario extra. Reemplaza el neteo constante de
# CONF contra Ibase (ver docs/checkpoint_proyecto.md).
DIAS_PRORRATEO_CONF = 7
