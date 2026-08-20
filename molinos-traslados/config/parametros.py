"""
parametros.py
Pesos de calibracion del modelo de traslados. Ajustar ACA, sin tocar la
logica en src/model.py. Solo importa el RATIO relativo entre parametros,
no el valor absoluto.
"""

SKUS = [56218, 56225, 56226]
NODOS = ["Pilar", "Chacabuco", "CDT"]

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
