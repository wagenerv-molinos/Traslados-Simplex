# CHECKPOINT — Modelo de optimización de traslados Molinos

## Alcance actual
- SKUs: 56218 (Blancaflor Leudante), 56225 (Favorita 000), 56226 (Favorita 0000)
- Nodos: **Pilar, Chacabuco, CDT** (CDEE fue eliminado por completo del alcance)
- Horizonte de la última corrida: 19/08 → 29/08 (11 días)

## Topología de red vigente
- Arcos permitidos: Pilar→CDT, Chacabuco→CDT (primario, costo BASE)
- Chacabuco→Pilar habilitado (lateral, costo 2×BASE)
- Pilar→Chacabuco: PROHIBIDO (Chacabuco no recibe traslados de ningún lado)
- Cualquier arco con CDEE: eliminado

## Parámetros del objetivo (calibrados)
- α (prioridad quiebre): 400 en Pilar/Chacabuco, 100 en CDT
- β (prioridad sobre-stock): 10 en Pilar/Chacabuco, 20 en CDT
- α_pedido (pedidos NO confirmados): 4000, prioridad máxima
- Costo arco: BASE en primario, 2×BASE en lateral Chacabuco→Pilar
- δ (costo fijo envío) = 0 (camión completo ya es restricción dura)
- Camión: restricción DURA, múltiplos exactos de 25 pallets por arco/día
- Cap_n: Pilar=1600, Chacabuco=1100 pallets. CDT sin límite.
- Lead time L=1 día, único para todos los arcos.

## Política de cobertura (g, días de giro)
- Fuente: PDG.xlsx → columnas `pdg` (total) y `pdg cdee` (tramo CD)
- Regla: g_planta = pdg − pdg_cdee ; g_CD = pdg_cdee
- g_Chacabuco-56218: restaurado a política normal (override a 0 descartado
  tras evidencia de producción activa)

## Target de cobertura — MÉTODO CORRECTO
- Target NO es `g × dbar_promedio` (error corregido durante el proyecto)
- Target SÍ es: suma del forecast real de los próximos `⌊g⌋` días completos
  + `frac(g)` × forecast del día parcial siguiente
- Ejemplo g=2.48: target(t) = fcst(t) + fcst(t+1) + 0.48×fcst(t+2)
- Requiere forecast DIARIO real para calcularse bien día a día

## Forecast (dbar) — estado y limitación abierta
- Fuente disponible: FCST_por_centro.xlsx = forecast REMANENTE de agosto
  a una fecha de corte, prorrateado / 13 días (19 al 31/08 inclusive)
- PENDIENTE: reemplazar por forecast diario real para todo el horizonte

## Consumo diario real vs. forecast — regla acordada
- Ibase (stock proyectado) llega NETO — no se puede desagregar directo
- Desagregado por movimiento individual (Fecha, Tipo=Producción/Salida/
  Llegada, Qty) disponible para Pilar, Chacabuco y CDT
- Regla: consumo_real_del_día = **max(despacho ya planificado, forecast)**
- Ibase_corregido(t) = Ibase_raw(t) − Σ max(0, fcst(τ) − despacho_plan(τ))

## Producción — misma lógica simétrica (RESUELTO)
- Se conectó Planes_de_produccion.xlsx (semanas técnicas TW34/TW35),
  prorrateado a 6 días productivos por semana (domingo sin producción)
- Regla: producción_real(t) = **max(producción ya cargada, plan diario)**
- El EXCEDENTE de plan no cubierto por lo ya cargado se SUMA a Ibase
- Esto resolvió gran parte del faltante estructural detectado: ej.
  Pilar-56218 pasó de -234 pallets proyectados a +526,6
- Persisten alertas en CDT (no produce, depende 100% de traslados) —
  se reportan como alerta a escalar a supply, no como "solución" forzada

## Pedidos pendientes (CONF / NC)
- Fuente: Pendientes_AFO.xlsx (formato AFO, Centro forward-fill, cajas)
- Conversión: ÷70 cajas/pallet
- CONF → netea Ibase directo. NC → prioridad MÁXIMA (α_pedido=4000)

## Datos maestros resueltos
- Múltiplo logístico: 70 cajas/pallet para las 3 harinas
- Camión = 25 pallets

## Refactor a repo formal
- Código modularizado: config/parametros.py, src/data_loader.py,
  src/model.py, src/report.py, run_ejemplo.py como orquestador
- Reemplaza los scripts sueltos generados durante la exploración

## Próximos pasos
1. Conectar forecast diario real (reemplazar el remanente/prorrateado)
2. Automatizar rolling horizon: re-solve diario emitiendo solo deltas
3. Evaluar integración con SAP vía API para ejecución de traslados aprobados
4. Extender a más SKUs/familias si el enfoque valida bien en producción

## Preferencias de formato de trabajo
- No mostrar logs completos del solver (disp:False)
- No generar un archivo .py nuevo por cada variante — parchear el mismo módulo
- Mostrar resúmenes cortos por defecto, no tablas completas salvo que se pidan
