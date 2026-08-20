"""
data_loader.py
Carga y preparacion de datos para el modelo de traslados.
Ver docs/checkpoint_proyecto.md para el detalle de cada fuente.
"""
import pandas as pd

from config.parametros import CAJAS_POR_PALLET


def cargar_ibase(path_por_centro: dict, skus: list, date_cols: list) -> dict:
    ibase = {}
    for centro, path in path_por_centro.items():
        df = pd.read_excel(path)
        df["Material"] = pd.to_numeric(df["Material"], errors="coerce")
        df = df[df["Material"].isin(skus)]
        for _, row in df.iterrows():
            sku = int(row["Material"])
            for t, col in enumerate(date_cols, start=1):
                ibase[(sku, centro, t)] = row[col]
    return ibase


def cargar_movimientos_desagregados(path_por_sku_centro: dict, date_cols: list) -> tuple:
    despacho, produccion = {}, {}
    for (centro, sku), path in path_por_sku_centro.items():
        df = pd.read_excel(path)
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)
        df["FechaStr"] = df["Fecha"].dt.strftime("%d/%m")
        tipos = df["Tipo"].unique()
        tipo_prod = "Producci\u00f3n" if "Producci\u00f3n" in tipos else "Llegada"
        for t, d in enumerate(date_cols, start=1):
            sub = df[df["FechaStr"] == d]
            prod = sub[sub["Tipo"] == tipo_prod]["Qty (PAL)"].sum()
            sal = abs(sub[sub["Tipo"] == "Salida"]["Qty (PAL)"].sum())
            despacho[(sku, centro, t)] = sal
            produccion[(sku, centro, t)] = prod
    return despacho, produccion


def cargar_forecast_remanente(path: str, sku_map: dict, loc_map: dict,
                               dias_totales: int, columna_valor: str = "26-Aug") -> dict:
    df = pd.read_excel(path)
    df["Nodo"] = df["Location ID"].map(loc_map)
    df["Material"] = df["Product ID"].map(sku_map)
    dbar = {}
    for _, row in df.iterrows():
        dbar[(int(row["Material"]), row["Nodo"])] = row[columna_valor] / dias_totales
    return dbar


def cargar_forecast_diario_real(path: str, loc_map: dict, date_cols: list,
                                 cajas_por_pallet: int = CAJAS_POR_PALLET) -> dict:
    df = pd.read_csv(path, sep=None, engine="python")
    if df["ZFCSTESTIMADO"].dtype == object:
        df["ZFCSTESTIMADO"] = df["ZFCSTESTIMADO"].astype(str).str.replace(",", ".").astype(float)
    df["KEYFIGUREDATE"] = pd.to_datetime(df["KEYFIGUREDATE"])
    df["Centro"] = df["LOCID"].map(loc_map)
    agg = df.groupby(["PRDID", "Centro", "KEYFIGUREDATE"])["ZFCSTESTIMADO"].sum().reset_index()
    agg["fcst_pallets"] = agg["ZFCSTESTIMADO"] / cajas_por_pallet

    fcst = {}
    for _, row in agg.iterrows():
        fecha_str = row["KEYFIGUREDATE"].strftime("%d/%m")
        if fecha_str in date_cols:
            t = date_cols.index(fecha_str) + 1
            fcst[(int(row["PRDID"]), row["Centro"], t)] = row["fcst_pallets"]
    return fcst


def cargar_plan_produccion(path: str, loc_map: dict, sku_map: dict, date_cols: list,
                            semana_por_dia: dict, dias_productivos: int = 6) -> dict:
    df = pd.read_excel(path)
    df["Nodo"] = df["Location ID"].map(loc_map)
    df["Material"] = df["Product ID"].map(sku_map)
    df = df.fillna(0)

    columnas_semana = [c for c in df.columns if c not in ("Location ID", "Product ID", "Nodo", "Material")]
    col_por_clave = {col.split(" ")[0]: col for col in columnas_semana}

    plan = {}
    for _, row in df.iterrows():
        sku, centro = row["Material"], row["Nodo"]
        for t, d in enumerate(date_cols, start=1):
            clave_semana = semana_por_dia.get(d)
            if clave_semana in col_por_clave:
                plan[(sku, centro, t)] = row[col_por_clave[clave_semana]] / dias_productivos
            else:
                plan[(sku, centro, t)] = 0.0
    return plan


def cargar_pedidos_pendientes(path: str, sheet_name: str, centro_map: dict, skus: list,
                               cajas_por_pallet: int = CAJAS_POR_PALLET) -> tuple:
    df = pd.read_excel(path, sheet_name=sheet_name)
    df.columns = ["Centro", "Producto", "Material", "CantConfirmado", "CantNoConfirmado"]
    df = df.iloc[1:].copy()
    df["Centro"] = df["Centro"].ffill()
    df["Material"] = pd.to_numeric(df["Material"], errors="coerce")
    df["CantConfirmado"] = pd.to_numeric(df["CantConfirmado"], errors="coerce").fillna(0)
    df["CantNoConfirmado"] = pd.to_numeric(df["CantNoConfirmado"], errors="coerce").fillna(0)
    df["Centro"] = pd.to_numeric(df["Centro"], errors="coerce")
    df["Nodo"] = df["Centro"].map(centro_map)

    sub = df[(df["Material"].isin(skus)) & (df["Nodo"].notna())]
    conf, nc = {}, {}
    for _, row in sub.iterrows():
        key = (int(row["Material"]), row["Nodo"])
        conf[key] = conf.get(key, 0.0) + row["CantConfirmado"] / cajas_por_pallet
        nc[key] = nc.get(key, 0.0) + row["CantNoConfirmado"] / cajas_por_pallet
    return conf, nc


def cargar_politica_giro(path: str, skus: list) -> dict:
    df = pd.read_excel(path)
    df.columns = ["Material", "Producto", "_", "pdg_total", "pdg_cdee"]
    df = df[df["Material"].isin(skus)]
    g = {}
    for _, row in df.iterrows():
        sku = int(row["Material"])
        g[(sku, "planta")] = row["pdg_total"] - row["pdg_cdee"]
        g[(sku, "cd")] = row["pdg_cdee"]
    return g


def construir_ibase_final(ibase_raw: dict, despacho_planificado: dict, forecast_diario: dict,
                           produccion_cargada: dict, plan_produccion_diario: dict,
                           skus: list, nodos: list, horizonte: int) -> dict:
    """
    Aplica las DOS correcciones de negocio acordadas (ver docs/checkpoint_proyecto.md):

    1. DEMANDA: consumo_real(t) = max(despacho_planificado(t), forecast(t))
       Se resta el EXCEDENTE de forecast no cubierto por lo ya planificado.
    2. OFERTA:  produccion_real(t) = max(produccion_cargada(t), plan_diario(t))
       Se suma el EXCEDENTE de plan no cubierto por lo ya cargado en el sistema.

    Ambos ajustes son ACUMULATIVOS dia a dia. Si el resultado muestra stock
    fuertemente negativo pese a esta correccion, es una ALERTA GENUINA de
    produccion no cargada en el sistema - no un error del modelo.
    """
    ibase_final = {}
    for s in skus:
        for n in nodos:
            acumulado_demanda = 0.0
            acumulado_oferta = 0.0
            for t in range(1, horizonte + 1):
                fcst_t = forecast_diario.get((s, n, t), 0.0)
                despacho_t = despacho_planificado.get((s, n, t), 0.0)
                acumulado_demanda += max(0.0, fcst_t - despacho_t)

                plan_t = plan_produccion_diario.get((s, n, t), 0.0)
                cargada_t = produccion_cargada.get((s, n, t), 0.0)
                acumulado_oferta += max(0.0, plan_t - cargada_t)

                base = ibase_raw.get((s, n, t), 0.0)
                ibase_final[(s, n, t)] = base - acumulado_demanda + acumulado_oferta
    return ibase_final
