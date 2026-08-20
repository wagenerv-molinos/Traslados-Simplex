"""
model.py
Construccion y resolucion del modelo de optimizacion de traslados
(rebalanceo de inventario multiperiodo con transbordo, MILP).
Ver docs/modelo_matematico.md para la formulacion completa.
"""
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

from config.parametros import (
    ARCOS, COSTO_ARCO, ALPHA, BETA, DELTA, CAP_N, ALPHA_PEDIDO, CAMION_PALLETS,
)


def construir_target(skus, nodos, g_map, forecast_diario, horizonte):
    target = {}
    for s in skus:
        for n in nodos:
            g = g_map[(s, n)]
            dias_enteros = int(g)
            frac = g - dias_enteros
            for t in range(1, horizonte + 1):
                val = sum(forecast_diario.get((s, n, t + k), 0.0) for k in range(dias_enteros))
                val += frac * forecast_diario.get((s, n, t + dias_enteros), 0.0)
                target[(s, n, t)] = val
    return target


def resolver_modelo(skus, nodos, ibase, target, conf, nc, horizonte, time_limit=90):
    T_days = list(range(1, horizonte))
    all_days = list(range(1, horizonte + 1))

    ibase_neto = {}
    for s in skus:
        for n in nodos:
            c_conf = conf.get((s, n), 0.0)
            for t in all_days:
                ibase_neto[(s, n, t)] = ibase.get((s, n, t), 0.0) - c_conf

    var_idx = {}
    n_vars = [0]

    def add_var(key):
        var_idx[key] = n_vars[0]
        n_vars[0] += 1

    for s in skus:
        for a in ARCOS:
            for t in T_days:
                add_var(("T", s, a, t))
    for a in ARCOS:
        for t in T_days:
            add_var(("k", a, t))
    for s in skus:
        for n in nodos:
            for t in all_days:
                add_var(("I", s, n, t))
                add_var(("U", s, n, t))
                add_var(("E", s, n, t))
                add_var(("Up", s, n, t))

    nv = n_vars[0]
    c = np.zeros(nv)
    for s in skus:
        for n in nodos:
            for t in all_days:
                c[var_idx[("U", s, n, t)]] = ALPHA[n]
                c[var_idx[("E", s, n, t)]] = BETA[n]
                c[var_idx[("Up", s, n, t)]] = ALPHA_PEDIDO
    for s in skus:
        for a in ARCOS:
            for t in T_days:
                c[var_idx[("T", s, a, t)]] = COSTO_ARCO[a]
    for a in ARCOS:
        for t in T_days:
            c[var_idx[("k", a, t)]] = DELTA

    A_eq_rows, b_eq = [], []
    A_ub_rows, b_ub = [], []

    def eq_row(coefs, rhs):
        row = np.zeros(nv)
        for k_, v_ in coefs.items():
            row[k_] += v_
        A_eq_rows.append(row)
        b_eq.append(rhs)

    def ub_row(coefs, rhs):
        row = np.zeros(nv)
        for k_, v_ in coefs.items():
            row[k_] += v_
        A_ub_rows.append(row)
        b_ub.append(rhs)

    for a in ARCOS:
        for t in T_days:
            coefs = {}
            for s in skus:
                key = var_idx[("T", s, a, t)]
                coefs[key] = coefs.get(key, 0) + 1
            key_k = var_idx[("k", a, t)]
            coefs[key_k] = coefs.get(key_k, 0) - CAMION_PALLETS
            eq_row(coefs, 0.0)

    arcs_out = {n: [a for a in ARCOS if a[0] == n] for n in nodos}
    arcs_in = {n: [a for a in ARCOS if a[1] == n] for n in nodos}

    for s in skus:
        for n in nodos:
            for t in all_days:
                coefs = {var_idx[("I", s, n, t)]: 1}
                if t == 1:
                    for a in arcs_out[n]:
                        if 1 in T_days:
                            key = var_idx[("T", s, a, 1)]
                            coefs[key] = coefs.get(key, 0) + 1
                    rhs = ibase_neto[(s, n, 1)]
                else:
                    key_prev = var_idx[("I", s, n, t - 1)]
                    coefs[key_prev] = coefs.get(key_prev, 0) - 1
                    if (t - 1) in T_days:
                        for a in arcs_in[n]:
                            key = var_idx[("T", s, a, t - 1)]
                            coefs[key] = coefs.get(key, 0) - 1
                    if t in T_days:
                        for a in arcs_out[n]:
                            key = var_idx[("T", s, a, t)]
                            coefs[key] = coefs.get(key, 0) + 1
                    rhs = ibase_neto[(s, n, t)] - ibase_neto[(s, n, t - 1)]
                eq_row(coefs, rhs)

    for s in skus:
        for n in nodos:
            for t in all_days:
                ub_row({var_idx[("I", s, n, t)]: -1, var_idx[("U", s, n, t)]: -1}, -target[(s, n, t)])

    for s in skus:
        for n in nodos:
            for t in all_days:
                ub_row({var_idx[("I", s, n, t)]: 1, var_idx[("E", s, n, t)]: -1}, target[(s, n, t)])

    for n in CAP_N:
        for t in all_days:
            coefs = {}
            rhs = CAP_N[n]
            for s in skus:
                coefs[var_idx[("I", s, n, t)]] = 1
                rhs -= conf.get((s, n), 0.0)
            ub_row(coefs, rhs)

    for s in skus:
        for n in nodos:
            if nc.get((s, n), 0.0) > 0:
                for t in all_days:
                    ub_row({var_idx[("I", s, n, t)]: -1, var_idx[("Up", s, n, t)]: -1}, -nc[(s, n)])

    A_eq = np.array(A_eq_rows)
    A_ub = np.array(A_ub_rows)
    b_eq = np.array(b_eq)
    b_ub = np.array(b_ub)

    lb = np.zeros(nv)
    ub = np.full(nv, np.inf)
    integrality = np.zeros(nv)
    for key, idx in var_idx.items():
        if key[0] in ("T", "k"):
            integrality[idx] = 1
        if key[0] == "I":
            lb[idx] = -1e6

    bounds = Bounds(lb, ub)
    constraints = [
        LinearConstraint(A_eq, b_eq, b_eq),
        LinearConstraint(A_ub, -np.inf, b_ub),
    ]

    res = milp(c, constraints=constraints, integrality=integrality, bounds=bounds,
               options={"disp": False, "time_limit": time_limit})

    return {
        "res": res, "var_idx": var_idx, "target": target, "ibase": ibase_neto,
        "skus": skus, "nodos": nodos, "all_days": all_days, "T_days": T_days,
        "conf": conf, "nc": nc,
    }
