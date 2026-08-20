"""
run_ejemplo.py
Orquestacion completa: carga -> correccion de Ibase -> target -> MILP -> reporte.
AJUSTAR: horizonte de fechas, rutas de archivos.
"""
from src.data_loader import (
    cargar_ibase, cargar_movimientos_desagregados, cargar_forecast_remanente_ibp,
    cargar_plan_produccion_ibp, cargar_pedidos_pendientes, cargar_politica_giro,
    construir_ibase_final,
)
from src.model import construir_target, resolver_modelo
from src.report import extraer_traslados, extraer_camiones, extraer_alertas_faltante, extraer_cobertura
from config.parametros import SKUS, NODOS, ARCOS, LOC_IDS_IBP

DATE_COLS = ["19/08", "20/08", "21/08", "22/08", "23/08", "24/08", "25/08",
             "26/08", "27/08", "28/08", "29/08"]
HORIZONTE = len(DATE_COLS)
ANIO = 2026

_MESES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_mes_horizonte = int(DATE_COLS[0].split("/")[1])
PERIODID3_HORIZONTE = f"{ANIO % 100:02d}-{_MESES_EN[_mes_horizonte - 1]}"

PATHS_IBASE = {
    "Pilar": "data/Stock proyectado Pilar.xlsx",
    "Chacabuco": "data/Stock proyectado Chacabuco.xlsx",
    "CDT": "data/Stock proyectado CDT.xlsx",
}
PATHS_MOVIMIENTOS = {
    ("Pilar", 56218): "data/Pilar 56218.xlsx",
    ("Pilar", 56225): "data/Pilar 56225.xlsx",
    ("Pilar", 56226): "data/Pilar 56226.xlsx",
    ("Chacabuco", 56218): "data/Chaca 56218.xlsx",
    ("Chacabuco", 56225): "data/Chaca 56225.xlsx",
    ("Chacabuco", 56226): "data/Chaca 56226.xlsx",
    ("CDT", 56218): "data/CDT 56218.xlsx",
    ("CDT", 56225): "data/CDT 56225.xlsx",
    ("CDT", 56226): "data/CDT 56226.xlsx",
}
PATH_PENDIENTES_AFO = "data/Pendientes AFO.xlsx"
PATH_PDG = "data/PDG.xlsx"

CENTRO_MAP_AFO = {2501: "Pilar", 2502: "Chacabuco", 1018: "CDT"}


def main():
    ibase_raw = cargar_ibase(PATHS_IBASE, SKUS, DATE_COLS)
    despacho_plan, prod_cargada = cargar_movimientos_desagregados(PATHS_MOVIMIENTOS, DATE_COLS)

    dbar_const = cargar_forecast_remanente_ibp(SKUS, LOC_IDS_IBP, PERIODID3_HORIZONTE)
    forecast_diario = {
        (s, n, t): dbar_const[(s, n)]
        for (s, n) in dbar_const
        for t in range(1, HORIZONTE + 1)
    }

    plan_diario = cargar_plan_produccion_ibp(SKUS, LOC_IDS_IBP, DATE_COLS, ANIO)

    conf, nc = cargar_pedidos_pendientes(PATH_PENDIENTES_AFO, "Hoja1", CENTRO_MAP_AFO, SKUS)

    ibase_final = construir_ibase_final(
        ibase_raw, despacho_plan, forecast_diario, prod_cargada, plan_diario, conf,
        SKUS, NODOS, HORIZONTE,
    )

    g_planta_cd = cargar_politica_giro(PATH_PDG, SKUS)
    g_map = {}
    for s in SKUS:
        g_map[(s, "Pilar")] = g_planta_cd[(s, "planta")]
        g_map[(s, "Chacabuco")] = g_planta_cd[(s, "planta")]
        g_map[(s, "CDT")] = g_planta_cd[(s, "cd")]

    target = construir_target(SKUS, NODOS, g_map, forecast_diario, HORIZONTE)

    salida = resolver_modelo(SKUS, NODOS, ibase_final, target, conf, nc, HORIZONTE)

    arcos_laterales = [a for a in ARCOS if a not in [("Pilar", "CDT"), ("Chacabuco", "CDT")]]

    df_traslados = extraer_traslados(salida["res"], salida["var_idx"], DATE_COLS, arcos_laterales)
    df_camiones = extraer_camiones(salida["res"], salida["var_idx"], DATE_COLS)
    df_alertas, resumen_alertas = extraer_alertas_faltante(
        salida["res"], salida["var_idx"], SKUS, NODOS, salida["all_days"], DATE_COLS)
    df_cobertura = extraer_cobertura(
        salida["res"], salida["var_idx"], salida["ibase"], target, SKUS, NODOS, salida["all_days"], DATE_COLS)

    print("=== TRASLADOS SUGERIDOS ===")
    print(df_traslados.to_string(index=False) if len(df_traslados) else "(ninguno)")
    print("\n=== CAMIONES ===")
    print(df_camiones.to_string(index=False) if len(df_camiones) else "(ninguno)")
    print("\n=== ALERTAS DE FALTANTE ESTRUCTURAL (escalar a supply/produccion) ===")
    print(resumen_alertas.to_string(index=False) if len(resumen_alertas) else "(ninguna)")
    print(f"\nObjetivo total: {salida['res'].fun:,.0f}")

    df_traslados.to_csv("output_traslados.csv", index=False)
    df_alertas.to_csv("output_alertas.csv", index=False)
    df_cobertura.to_csv("output_cobertura.csv", index=False)


if __name__ == "__main__":
    main()
