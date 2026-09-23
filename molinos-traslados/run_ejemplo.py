"""
run_ejemplo.py
Orquestacion completa: carga -> correccion de Ibase -> target -> MILP -> reporte.

El horizonte se toma de las columnas dd/mm de "data/Stock proyectado Pilar.xlsx",
asi que para una corrida nueva alcanza con reemplazar los Excel de data/.
Forecast y plan de produccion se leen de IBP (credenciales en .env.txt).
"""
import datetime as dt
from pathlib import Path

import pandas as pd

from src.data_loader import (
    cargar_ibase, cargar_movimientos_desagregados, cargar_forecast_diario_ibp,
    cargar_plan_produccion_ibp, cargar_pedidos_pendientes, cargar_politica_giro,
    construir_ibase_final,
)
from src.model import construir_target, resolver_modelo
from src.report import extraer_traslados, extraer_camiones, extraer_alertas_faltante, extraer_cobertura
from config.parametros import (
    SKUS, NODOS, ARCOS, LOC_IDS_IBP, LOC_IDS_IBP_FORECAST_EXTRA,
    DIAS_SEMANA_SIN_DESPACHO, DIAS_PRORRATEO_CONF,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "output"
ANIO = dt.date.today().year

PATHS_IBASE = {
    "Pilar": DATA_DIR / "Stock proyectado Pilar.xlsx",
    "Chacabuco": DATA_DIR / "Stock proyectado Chacabuco.xlsx",
    "CDT": DATA_DIR / "Stock proyectado CDT.xlsx",
}
PATHS_MOVIMIENTOS = {
    "Pilar": DATA_DIR / "Pilar x SKU.xlsx",
    "Chacabuco": DATA_DIR / "Chaca x SKU.xlsx",
    "CDT": DATA_DIR / "CDT x SKU.xlsx",
}
PATH_PENDIENTES_AFO = DATA_DIR / "Pendientes AFO.xlsx"
PATH_PDG = DATA_DIR / "PDG.xlsx"

CENTRO_MAP_AFO = {2501: "Pilar", 2502: "Chacabuco", 1018: "CDT"}


def detectar_horizonte(path_ibase: Path, anio: int) -> list:
    """Columnas dd/mm del Excel de stock proyectado, en orden."""
    date_cols = []
    for c in pd.read_excel(path_ibase, nrows=0).columns:
        try:
            dt.datetime.strptime(f"{c}/{anio}", "%d/%m/%Y")
            date_cols.append(str(c))
        except ValueError:
            pass
    return date_cols


def main():
    date_cols = detectar_horizonte(PATHS_IBASE["Pilar"], ANIO)
    horizonte = len(date_cols)
    fechas = [dt.datetime.strptime(f"{d}/{ANIO}", "%d/%m/%Y").date() for d in date_cols]
    print(f"Horizonte: {date_cols[0]} -> {date_cols[-1]} ({horizonte} dias)")

    ibase_raw = cargar_ibase(PATHS_IBASE, SKUS, date_cols)
    despacho_plan, prod_cargada = cargar_movimientos_desagregados(PATHS_MOVIMIENTOS, SKUS, date_cols)

    # Se extiende mas alla del horizonte para que el target de los ultimos dias
    # cubra la ventana completa de g dias (si no, el target cae a ~0 al final).
    fechas_fcst = [fechas[0] + dt.timedelta(days=i) for i in range(horizonte + 14)]
    forecast_diario = cargar_forecast_diario_ibp(
        SKUS, LOC_IDS_IBP, fechas_fcst, loc_ids_extra_por_nodo=LOC_IDS_IBP_FORECAST_EXTRA,
    )

    plan_diario = cargar_plan_produccion_ibp(SKUS, LOC_IDS_IBP, date_cols, ANIO)

    conf, nc = cargar_pedidos_pendientes(PATH_PENDIENTES_AFO, "Hoja1", CENTRO_MAP_AFO, SKUS)

    ibase_final, consumo = construir_ibase_final(
        ibase_raw, despacho_plan, forecast_diario, prod_cargada, plan_diario, conf,
        SKUS, NODOS, horizonte,
    )

    g_planta_cd = cargar_politica_giro(PATH_PDG, SKUS)
    g_map = {}
    for s in SKUS:
        g_map[(s, "Pilar")] = g_planta_cd[(s, "planta")]
        g_map[(s, "Chacabuco")] = g_planta_cd[(s, "planta")]
        g_map[(s, "CDT")] = g_planta_cd[(s, "cd")]

    target = construir_target(SKUS, NODOS, g_map, forecast_diario, horizonte)

    dias_sin_despacho = [t for t, f in enumerate(fechas, start=1) if f.weekday() in DIAS_SEMANA_SIN_DESPACHO]
    salida = resolver_modelo(SKUS, NODOS, ibase_final, target, conf, nc, horizonte,
                             dias_sin_despacho=dias_sin_despacho)
    print(f"Solver: {salida['res'].message}")

    arcos_laterales = [a for a in ARCOS if a not in [("Pilar", "CDT"), ("Chacabuco", "CDT")]]

    df_traslados = extraer_traslados(salida["res"], salida["var_idx"], date_cols, arcos_laterales)
    df_camiones = extraer_camiones(salida["res"], salida["var_idx"], date_cols)
    df_alertas, resumen_alertas = extraer_alertas_faltante(
        salida["res"], salida["var_idx"], SKUS, NODOS, salida["all_days"], date_cols)
    df_cobertura = extraer_cobertura(
        salida["res"], salida["var_idx"], salida["ibase"], target, SKUS, NODOS, salida["all_days"], date_cols)
    df_consumo = pd.DataFrame([
        {"SKU": s, "Nodo": n, "Fecha": date_cols[t - 1],
         "Despacho_planificado": round(despacho_plan.get((s, n, t), 0.0), 1),
         "Confirmado_prorrateado": round(conf.get((s, n), 0.0) / DIAS_PRORRATEO_CONF, 1)
         if t <= DIAS_PRORRATEO_CONF else 0.0,
         "Forecast": round(forecast_diario.get((s, n, t), 0.0), 1),
         "Consumo_modelo": round(consumo[(s, n, t)], 1),
         "Produccion_cargada": round(prod_cargada.get((s, n, t), 0.0), 1),
         "Plan_produccion": round(plan_diario.get((s, n, t), 0.0), 1)}
        for s in SKUS for n in NODOS for t in range(1, horizonte + 1)
    ])

    print("=== TRASLADOS SUGERIDOS ===")
    print(df_traslados.to_string(index=False) if len(df_traslados) else "(ninguno)")
    print("\n=== CAMIONES ===")
    print(df_camiones.to_string(index=False) if len(df_camiones) else "(ninguno)")
    print("\n=== ALERTAS DE FALTANTE ESTRUCTURAL (escalar a supply/produccion) ===")
    print(resumen_alertas.to_string(index=False) if len(resumen_alertas) else "(ninguna)")
    print(f"\nObjetivo total: {salida['res'].fun:,.0f}")

    OUT_DIR.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT_DIR / "resultado_traslados.xlsx") as xw:
        df_traslados.to_excel(xw, sheet_name="Traslados", index=False)
        df_camiones.to_excel(xw, sheet_name="Camiones", index=False)
        resumen_alertas.to_excel(xw, sheet_name="Alertas resumen", index=False)
        df_alertas.to_excel(xw, sheet_name="Alertas detalle", index=False)
        df_cobertura.to_excel(xw, sheet_name="Cobertura", index=False)
        df_consumo.to_excel(xw, sheet_name="Consumo", index=False)
    print(f"Detalle en {OUT_DIR / 'resultado_traslados.xlsx'}")


if __name__ == "__main__":
    main()
