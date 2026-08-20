"""
run_ejemplo.py
Orquestacion completa: carga -> correccion de Ibase -> target -> MILP -> reporte.
AJUSTAR: horizonte de fechas, mapeo semana tecnica -> dia, rutas de archivos.
"""
from src.data_loader import (
    cargar_ibase, cargar_movimientos_desagregados, cargar_forecast_remanente,
    cargar_plan_produccion, cargar_pedidos_pendientes, cargar_politica_giro,
    construir_ibase_final,
)
from src.model import construir_target, resolver_modelo
from src.report import extraer_traslados, extraer_camiones, extraer_alertas_faltante, extraer_cobertura
from config.parametros import SKUS, NODOS, ARCOS

DATE_COLS = ["19/08", "20/08", "21/08", "22/08", "23/08", "24/08", "25/08",
             "26/08", "27/08", "28/08", "29/08"]
HORIZONTE = len(DATE_COLS)

SEMANA_POR_DIA = {
    "19/08": "TW34", "20/08": "TW34", "21/08": "TW34", "22/08": "TW34",
    "23/08": None,
    "24/08": "TW35", "25/08": "TW35", "26/08": "TW35", "27/08": "TW35",
    "28/08": "TW35", "29/08": "TW35",
}

PATHS_IBASE = {
    "Pilar": "data/Stock_proyectado_Pilar.xlsx",
    "Chacabuco": "data/Stock_proyectado_Chacabuco.xlsx",
    "CDT": "data/Stock_proyectado_CDT.xlsx",
}
PATHS_MOVIMIENTOS = {
    ("Pilar", 56218): "data/Pilar_56218.xlsx",
    ("Pilar", 56225): "data/Pilar_56225.xlsx",
    ("Pilar", 56226): "data/Pilar_56226.xlsx",
    ("Chacabuco", 56218): "data/Chaca_56218.xlsx",
    ("Chacabuco", 56225): "data/Chaca_56225.xlsx",
    ("Chacabuco", 56226): "data/Chaca_56226.xlsx",
    ("CDT", 56218): "data/CDT_56218.xlsx",
    ("CDT", 56225): "data/CDT_56225.xlsx",
    ("CDT", 56226): "data/CDT_56226.xlsx",
}
PATH_FORECAST_REMANENTE = "data/FCST_por_centro.xlsx"
PATH_PLAN_PRODUCCION = "data/Planes_de_produccion.xlsx"
PATH_PENDIENTES_AFO = "data/Pendientes_AFO.xlsx"
PATH_PDG = "data/PDG.xlsx"

LOC_MAP = {
    "2501 - Pilar (Molca)": "Pilar",
    "2502 - Chacabuco (Molca)": "Chacabuco",
    "1018 - Lucchetti": "CDT",
}
SKU_MAP = {
    "56218 - Blancaflor Harina Leudante 15x1kg": 56218,
    "56225 - Favorita Harina 000 Vitaminas 15x1kg": 56225,
    "56226 - Favorita Harina 0000 15x1kg": 56226,
}
CENTRO_MAP_AFO = {2501: "Pilar", 2502: "Chacabuco", 1018: "CDT"}

DIAS_RESTANTES_MES = 13


def main():
    ibase_raw = cargar_ibase(PATHS_IBASE, SKUS, DATE_COLS)
    despacho_plan, prod_cargada = cargar_movimientos_desagregados(PATHS_MOVIMIENTOS, DATE_COLS)

    dbar_const = cargar_forecast_remanente(PATH_FORECAST_REMANENTE, SKU_MAP, LOC_MAP, DIAS_RESTANTES_MES)
    forecast_diario = {
        (s, n, t): dbar_const[(s, n)]
        for (s, n) in dbar_const
        for t in range(1, HORIZONTE + 1)
    }

    plan_diario = cargar_plan_produccion(PATH_PLAN_PRODUCCION, LOC_MAP, SKU_MAP, DATE_COLS, SEMANA_POR_DIA)

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
