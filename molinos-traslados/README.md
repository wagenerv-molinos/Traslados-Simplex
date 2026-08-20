# Motor de traslados inter-centro — Molinos

Modelo de optimización (MILP) para decidir traslados incrementales de
harina entre centros productivos (Pilar, Chacabuco) y de distribución
(CDT), reemplazando la gestión reactiva día a día por un motor
semi-automático que propone traslados para aprobación humana.

## Estado del proyecto
- Formulación matemática: cerrada (ver `docs/modelo_matematico.md`).
- Implementación: MILP resuelto con `scipy.optimize.milp` (backend HiGHS).
- Alcance: 3 SKUs de harina (56218, 56225, 56226) × 3 nodos (Pilar,
  Chacabuco, CDT). CDEE fue evaluado y excluido del alcance.
- Pendiente: forecast diario real para todo el horizonte (hoy: forecast
  remanente mensual prorrateado como fallback); automatizar la ingesta.

## Estructura del repo

```
config/
  parametros.py       # pesos del objetivo, costos, capacidades
src/
  data_loader.py       # carga y correccion de Ibase (demanda + produccion)
  model.py              # construccion y resolucion del MILP
  report.py             # extraccion de traslados/alertas/cobertura
run_ejemplo.py           # orquestacion completa, punto de entrada
docs/
  modelo_matematico.md      # formulacion matematica completa
  checkpoint_proyecto.md    # historial de decisiones de negocio
data/
  (no versionado — ver data/README.md)
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

1. Colocar los archivos fuente (Excel) en `data/` según `data/README.md`.
2. Ajustar `run_ejemplo.py`: horizonte, mapeo semana técnica → día, rutas.
3. Ajustar `config/parametros.py` si cambia la calibración.
4. Correr:
   ```bash
   python run_ejemplo.py
   ```
5. Resultados en `output_traslados.csv`, `output_alertas.csv`,
   `output_cobertura.csv`.

## Reglas de negocio clave

(ver `docs/checkpoint_proyecto.md` para el historial completo)

- CDEE eliminado del alcance: no se despacha harina desde ahí.
- Camión completo (25 pallets) es restricción DURA: nunca se despacha
  incompleto, se posterga.
- Chacabuco→Pilar habilitado (2x costo). Pilar→Chacabuco prohibido.
- Target de cobertura = suma real del forecast dentro de la ventana de
  política de giro (NO promedio constante × días).
- Consumo real = max(despacho planificado, forecast).
- Producción real = max(producción cargada, plan semanal prorrateado a
  diario) — expone huecos de producción no cargada como alerta.
- CONF ("pendiente sin armar") se prorratea a 7 días como consumo diario extra
  (`max(despacho + CONF/7, forecast)`), no se netea de una vez contra Ibase.
  Sigue reservando capacidad física. NC tiene prioridad máxima.

## Próximos pasos sugeridos

- Conectar forecast diario real para todo el horizonte.
- Automatizar rolling horizon (re-solve diario, solo deltas).
- Integración con SAP vía API para ejecución de traslados aprobados.
- Extender a más SKUs/familias.
