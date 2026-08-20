"""
report.py
Extraccion de resultados del MILP resuelto, en tablas legibles.
"""
import pandas as pd


def extraer_traslados(res, var_idx, date_cols, arcos_laterales=None):
    arcos_laterales = arcos_laterales or []
    x = res.x
    filas = []
    for key, idx in var_idx.items():
        if key[0] == "T":
            _, s, a, t = key
            val = x[idx]
            if val > 0.5:
                filas.append({
                    "Fecha": date_cols[t - 1], "SKU": s,
                    "Origen": a[0], "Destino": a[1],
                    "Pallets": round(val, 1),
                    "Tipo": "Lateral" if a in arcos_laterales else "Primario",
                })
    df = pd.DataFrame(filas)
    return df.sort_values(["Fecha", "Origen", "SKU"]) if len(df) else df


def extraer_camiones(res, var_idx, date_cols):
    x = res.x
    filas = []
    for key, idx in var_idx.items():
        if key[0] == "k":
            _, a, t = key
            val = x[idx]
            if val > 0.5:
                filas.append({"Arco": f"{a[0]}->{a[1]}", "Fecha": date_cols[t - 1], "Camiones": round(val)})
    df = pd.DataFrame(filas)
    return df.sort_values(["Fecha", "Arco"]) if len(df) else df


def extraer_alertas_faltante(res, var_idx, skus, nodos, all_days, date_cols, umbral=0.5):
    x = res.x
    filas = []
    for s in skus:
        for n in nodos:
            for t in all_days:
                u = x[var_idx[("U", s, n, t)]]
                if u > umbral:
                    filas.append({"SKU": s, "Nodo": n, "Fecha": date_cols[t - 1], "Faltante_pallets": round(u, 1)})
    df = pd.DataFrame(filas)
    if len(df):
        resumen = df.groupby(["SKU", "Nodo"]).agg(
            dias_con_faltante=("Faltante_pallets", "count"),
            faltante_pico=("Faltante_pallets", "max"),
            faltante_promedio=("Faltante_pallets", "mean"),
        ).reset_index()
        return df, resumen
    return df, df


def extraer_cobertura(res, var_idx, ibase, target, skus, nodos, all_days, date_cols):
    x = res.x
    filas = []
    for s in skus:
        for n in nodos:
            for t in all_days:
                filas.append({
                    "SKU": s, "Nodo": n, "Fecha": date_cols[t - 1],
                    "Ibase": round(ibase[(s, n, t)], 1),
                    "Stock_resultante": round(x[var_idx[("I", s, n, t)]], 1),
                    "Target": round(target[(s, n, t)], 1),
                    "Faltante": round(x[var_idx[("U", s, n, t)]], 1),
                    "Excedente": round(x[var_idx[("E", s, n, t)]], 1),
                })
    return pd.DataFrame(filas)
