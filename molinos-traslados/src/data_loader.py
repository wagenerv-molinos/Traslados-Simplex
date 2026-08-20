"""
data_loader.py
Carga y preparacion de datos para el modelo de traslados.
Ver docs/checkpoint_proyecto.md para el detalle de cada fuente.
"""
import calendar
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from config.parametros import CAJAS_POR_PALLET, DIAS_PRORRATEO_CONF


def dias_restantes_mes(fecha: date) -> int:
    """Dias restantes en el mes de `fecha`, contando `fecha` y el ultimo dia del
    mes ambos inclusive (ej. 19/08 a 31/08 inclusive = 13 dias). Mismo criterio
    que ya usaba el DIAS_RESTANTES_MES hardcodeado en run_ejemplo.py."""
    ultimo_dia = calendar.monthrange(fecha.year, fecha.month)[1]
    return ultimo_dia - fecha.day + 1


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


def cargar_forecast_remanente_ibp(skus: list, loc_ids_por_nodo: dict, periodid3: str,
                                   fecha_corte: date = None) -> dict:
    """Como cargar_forecast_remanente pero via IBP OData (ver src/ibp_client.py) en
    vez del Excel FCST_por_centro.xlsx. Mismo criterio: forecast remanente mensual
    (version Baseline2, ZAUXFCSTREMANENTE2) prorrateado en partes iguales sobre los
    dias restantes del mes de `periodid3`, contados desde `fecha_corte` (default:
    hoy) hasta fin de mes, ambos inclusive (ver dias_restantes_mes).

    loc_ids_por_nodo: nombre de nodo interno -> LOCID de IBP (ej. {"Pilar": "2501"}).
    """
    from src.ibp_client import fetch_forecast_remanente_baseline2

    fecha_corte = fecha_corte or date.today()
    dias_restantes = dias_restantes_mes(fecha_corte)

    nodo_por_loc_id = {loc_id: nodo for nodo, loc_id in loc_ids_por_nodo.items()}
    filas = fetch_forecast_remanente_baseline2(
        [str(s) for s in skus], list(loc_ids_por_nodo.values()), periodid3,
    )
    dbar = {}
    for row in filas:
        nodo = nodo_por_loc_id.get(row["LOCID"])
        if nodo is None:
            continue
        dbar[(int(row["PRDID"]), nodo)] = float(row["ZAUXFCSTREMANENTE2"]) / dias_restantes
    return dbar


def _fecha_desde_tstamp_odata(valor: str) -> date:
    """Parsea '/Date(1786924800000)/' (epoch ms, UTC) a date. IBP entrega el
    lunes de inicio de la semana calendario en este campo."""
    ms = int(valor.strip("/").removeprefix("Date(").removesuffix(")"))
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


def cargar_plan_produccion_ibp(skus: list, loc_ids_por_nodo: dict, date_cols: list, anio: int,
                                dias_productivos: int = 6) -> dict:
    """Como cargar_plan_produccion pero via IBP OData - Response & Supply (ver
    src/ibp_client.py) en vez de Planes_de_produccion.xlsx. Mismo criterio: el
    plan semanal (PRODUCTION, planning area MOLIBPRS) se prorratea en partes
    iguales sobre `dias_productivos` dias productivos por semana (domingo sin
    produccion).

    Usa semana CALENDARIO (PERIODID4), no semana tecnica (PERIODID5): la
    tecnica se corta en los cambios de mes (aparece partida en dos filas, ej.
    "TW01a"/"TW01b"), lo que complica sumar el total semanal real.

    A diferencia del Excel, NO hace falta un diccionario semana->dia
    (SEMANA_POR_DIA) armado a mano: la semana de cada dia se calcula sola
    (lunes a domingo) y se cruza contra el lunes de inicio que devuelve IBP en
    PERIODID4_TSTAMP para cada semana calendario.

    date_cols: fechas del horizonte en formato "dd/mm" (mismo formato que ya
    usa run_ejemplo.py). anio: año calendario de esas fechas (date_cols no
    lleva año).
    loc_ids_por_nodo: nombre de nodo interno -> LOCID de IBP (ej. {"Pilar": "2501"}).
    """
    from src.ibp_client import fetch_produccion_semanal_rs

    fechas = [date(anio, int(d.split("/")[1]), int(d.split("/")[0])) for d in date_cols]
    fecha_desde, fecha_hasta = min(fechas), max(fechas)

    nodo_por_loc_id = {loc_id: nodo for nodo, loc_id in loc_ids_por_nodo.items()}
    filas = fetch_produccion_semanal_rs(
        [str(s) for s in skus], list(loc_ids_por_nodo.values()), fecha_desde, fecha_hasta,
    )

    produccion_semana = {}
    for row in filas:
        nodo = nodo_por_loc_id.get(row["LOCID"])
        if nodo is None:
            continue
        inicio_semana = _fecha_desde_tstamp_odata(row["PERIODID4_TSTAMP"])
        produccion_semana[(int(row["PRDID"]), nodo, inicio_semana)] = float(row["PRODUCTION"])

    plan = {}
    for s in skus:
        for nodo in loc_ids_por_nodo:
            for t, fecha in enumerate(fechas, start=1):
                if fecha.weekday() == 6:  # domingo: sin produccion
                    plan[(s, nodo, t)] = 0.0
                    continue
                inicio_semana = fecha - timedelta(days=fecha.weekday())
                total_semana = produccion_semana.get((s, nodo, inicio_semana), 0.0)
                plan[(s, nodo, t)] = total_semana / dias_productivos
    return plan


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
                           produccion_cargada: dict, plan_produccion_diario: dict, conf: dict,
                           skus: list, nodos: list, horizonte: int,
                           dias_prorrateo_conf: int = DIAS_PRORRATEO_CONF) -> dict:
    """
    Aplica las correcciones de negocio acordadas (ver docs/checkpoint_proyecto.md):

    1. DEMANDA: consumo_real(t) = max(despacho_planificado(t) + CONF/dias_prorrateo_conf,
       forecast(t)). El pendiente confirmado ("sin armar", CONF de Pendientes_AFO) se
       prorratea en partes iguales sobre `dias_prorrateo_conf` dias y se suma al despacho
       ya planificado antes de compararlo contra el forecast - reemplaza el neteo
       constante de CONF que antes se aplicaba directo contra Ibase en el MILP.
       Se resta el EXCEDENTE de ese consumo no cubierto por lo ya planificado.
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
            conf_diario = conf.get((s, n), 0.0) / dias_prorrateo_conf
            for t in range(1, horizonte + 1):
                fcst_t = forecast_diario.get((s, n, t), 0.0)
                despacho_t = despacho_planificado.get((s, n, t), 0.0) + conf_diario
                acumulado_demanda += max(0.0, fcst_t - despacho_t)

                plan_t = plan_produccion_diario.get((s, n, t), 0.0)
                cargada_t = produccion_cargada.get((s, n, t), 0.0)
                acumulado_oferta += max(0.0, plan_t - cargada_t)

                base = ibase_raw.get((s, n, t), 0.0)
                ibase_final[(s, n, t)] = base - acumulado_demanda + acumulado_oferta
    return ibase_final
