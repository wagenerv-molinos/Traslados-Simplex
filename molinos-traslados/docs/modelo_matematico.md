# Modelo de optimización de traslados en red (semi-automático)
## Red Molinos: 2 plantas (Pilar, Chacabuco) + 1 CD activo (CDT)

> CDEE fue eliminado por completo del alcance (no se despacha harina
> desde ahí). La red vigente tiene 3 nodos.

## 1. Conjuntos e índices
- s ∈ S : SKUs de harina — 56218, 56225, 56226
- n ∈ N : PL = {Pilar, Chacabuco}, CD = {CDT}
- (i,j) ∈ A : Pilar→CDT, Chacabuco→CDT (primario) ; Chacabuco→Pilar
  (lateral) ; Pilar→Chacabuco PROHIBIDO ; CD→planta PROHIBIDO
- t ∈ {1,…,H} : horizonte rolling, H≈11

## 2. Parámetros

- Ibase_{s,n,t}: stock proyectado neto de producción+despachos+traslados TM
- Despacho_plan_{s,n,t}: despacho ya planificado (real)
- fcst_{s,n,t}: forecast diario
- CONF_{s,n}: pendiente confirmado ("sin armar", de Pendientes_AFO), prorrateado
  a D=7 días (`DIAS_PRORRATEO_CONF`)
- CONSUMO_CORREGIDO = max(Despacho_plan + CONF/D, fcst)
- Producción_cargada_{s,n,t}: producción ya cargada (real)
- plan_produccion_{s,n,t}: plan semanal prorrateado (6 días/semana)
- PRODUCCIÓN_CORREGIDA = max(Producción_cargada, plan_produccion)
- g_{s,n} = pdg−pdg_cdee (planta) / pdg_cdee (CD)
- TARGET DINÁMICO:
```
target_{s,n,t} = Σ_{k=0}^{⌊g⌋−1} fcst_{s,n,t+k} + frac(g) · fcst_{s,n,t+⌊g⌋}
```
- L=1 día. c_{i,j}: BASE primario / 2×BASE lateral. q_s=1 pallet.
- CAMIÓN=25 pallets, restricción DURA. Cap_n: Pilar=1600, Chacabuco=1100, CDT=∞.
- NC_{s,n}: pedidos no confirmados

## 3. Variables

T_{s,i,j,t}≥0, k_{i,j,t}∈ℤ≥0, I_{s,n,t}, U_{s,n,t}≥0, E_{s,n,t}≥0, Up_{s,n,t}≥0

## 4. Ecuación núcleo

```
I_{s,n,t} = Ibase_neto_{s,n,t} + Σ_{τ≤t}[Σ_i T_{s,i,n,τ−L} − Σ_k T_{s,n,k,τ}]
```

## 5. Restricciones

- (a) Camión completo: Σ_s T_{s,i,j,t} = 25·k_{i,j,t}, k∈ℤ≥0
- (b) Cobertura mínima blanda: I + U ≥ target
- (c) Exceso: I − E ≤ target
- (d) Pedido NO confirmado: I + Up ≥ NC
- (e) Capacidad física: Σ_s I_{s,n,t} ≤ Cap_n − Σ_s CONF_{s,n}
- (f) Topología: T=0 fuera de A

## 6. Función objetivo

```
min Σ [ α_n·U + β_n·E + α_pedido·Up + Σ c_{i,j}·T ]
```

| Parámetro | Pilar | Chacabuco | CDT |
|---|---|---|---|
| α | 400 | 400 | 100 |
| β | 10 | 10 | 20 |
| Cap_n | 1600 | 1100 | ∞ |

Jerarquía: α_pedido ≫ α_planta (4×) > α_CD ≫ β_CD (2×) > β_planta

## 7. Operación semi-automática (rolling horizon)

1. Ingesta diaria: Ibase + despacho planificado + forecast + producción
   cargada + plan de producción + g + pedidos pendientes.
2. Corrección: max(despacho_plan, fcst) y max(producción_cargada, plan).
3. Disparo si I proyectada < target, o NC sin cobertura.
4. Optimización MILP.
5. Propuesta: traslados + alertas no resolubles + cobertura antes/después.
6. Confirmación humana.
7. Ejecución futura vía API a SAP (no implementada).
8. Re-solve diario con horizonte desplazado.

## 8. Notas de diseño

- Trabajar sobre Ibase evita re-modelar producción/demanda/tránsito.
- CDEE descartado del alcance por decisión operativa.
- Target usa forecast real día a día, no promedio.
- max(...) simétrico en demanda y oferta evita doble conteo y expone
  huecos reales de información no cargada — valioso para supply.
- Camión completo: restricción DURA, no costo.
- MILP resuelto con scipy.optimize.milp (HiGHS); formulación agnóstica al solver.
