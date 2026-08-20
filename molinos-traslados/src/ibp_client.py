"""
ibp_client.py
Cliente OData para SAP IBP (servicio EXTRACT_ODATA_SRV, planning area MOLIBP).
Conexion confirmada contra IBP el 2026-08-20. Ver docs/checkpoint_proyecto.md.
"""
import os
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://my308646-api.scmibp1.ondemand.com/sap/opu/odata/IBP/EXTRACT_ODATA_SRV"
RESOURCE = "MOLIBP"

# OJO: lleva espacio. 'Baseline2' (sin espacio) no es un SCNID valido para MOLIBP.
SCNID_BASELINE2 = "Baseline 2"


def _leer_env(path: Path) -> dict:
    if not path.exists():
        return {}
    env = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def _credenciales() -> tuple:
    base = Path(__file__).resolve().parent.parent
    env = _leer_env(base / ".env.txt") or _leer_env(base / ".env")
    username = env.get("IBP_USERNAME") or os.getenv("IBP_USERNAME")
    password = env.get("IBP_PASSWORD") or os.getenv("IBP_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "Faltan credenciales IBP_USERNAME/IBP_PASSWORD. Completar .env.txt "
            "(ver .env.txt.example) o definir las variables de entorno."
        )
    return username, password


def _fetch_page(select_fields: str, filtro: str, skip: int, top: int) -> list:
    username, password = _credenciales()
    r = requests.get(
        f"{BASE_URL}/{RESOURCE}",
        params={"$format": "json", "$select": select_fields, "$filter": filtro, "$top": top, "$skip": skip},
        auth=(username, password), headers={"Accept": "application/json"},
        timeout=120, verify=False,
    )
    if r.status_code != 200:
        raise ConnectionError(f"IBP error {r.status_code}: {r.text[:300]}")
    return r.json()["d"]["results"]


def paginar(select_fields: str, filtro: str, top: int = 5000) -> list:
    """Pagina via $skip.

    El servicio no siempre devuelve __next aunque haya mas paginas (confirmado:
    con top=5000 se pueden recibir exactamente 5000 filas sin __next habiendo
    varios miles mas detras). No confiar en __next - cortar cuando una pagina
    devuelve MENOS filas que `top`.
    """
    all_rows = []
    skip = 0
    while True:
        page = _fetch_page(select_fields, filtro, skip, top)
        all_rows.extend(page)
        if len(page) < top:
            break
        skip += top
    return all_rows


def fetch_forecast_remanente_baseline2(skus: list, loc_ids: list, periodid3: str, uom: str = "UMG") -> list:
    """Forecast remanente mensual (ZAUXFCSTREMANENTE2, version 'Baseline 2') por
    SKU y centro logistico (LOCID), para un periodo mensual (formato IBP 'YY-Mon',
    ej. '26-Aug').

    OJO: sin el filtro SCNID eq 'Baseline 2' el LOCID nunca se abre por centro -
    devuelve solo el total (LOCID en blanco) y el agregado pais 'AR01'. Con el
    filtro correcto, LOCID abre a los codigos de centro reales (ej. '2501'
    Pilar, '2502' Chacabuco, '1018' CDT/Lucchetti).

    skus y loc_ids se pasan como listas de strings (PRDID y LOCID de IBP).
    """
    filtro_sku = " or ".join(f"PRDID eq '{s}'" for s in skus)
    filtro_loc = " or ".join(f"LOCID eq '{n}'" for n in loc_ids)
    filtro = (
        f"UOMTOID eq '{uom}' and PERIODID3 eq '{periodid3}' and SCNID eq '{SCNID_BASELINE2}'"
        f" and ({filtro_sku}) and ({filtro_loc})"
    )
    return paginar(
        select_fields="PRDID,PRDDESCR,LOCID,LOCDESCR,PERIODID3,ZAUXFCSTREMANENTE2",
        filtro=filtro,
    )
