# Datos requeridos

Esta carpeta NO se versiona (datos reales de negocio, ver `.gitignore`).
Colocar acá, por corrida:

| Archivo | Contenido |
|---|---|
| `Stock_proyectado_Pilar.xlsx`, `_Chacabuco.xlsx`, `_CDT.xlsx` | Stock proyectado (Ibase) día a día |
| `Pilar_<SKU>.xlsx`, `Chaca_<SKU>.xlsx`, `CDT_<SKU>.xlsx` | Movimientos desagregados (Producción/Salida/Llegada) |
| `FCST_por_centro.xlsx` | Forecast remanente mensual (fallback) |
| `Planes_de_produccion.xlsx` | Plan de producción por semana técnica |
| `Pendientes_AFO.xlsx` | Pedidos pendientes (confirmados/no confirmados) |
| `PDG.xlsx` | Política de días de giro |

Ver `docs/checkpoint_proyecto.md` para el detalle de formato de cada fuente.
