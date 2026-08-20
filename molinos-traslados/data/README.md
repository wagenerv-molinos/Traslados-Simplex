# Datos requeridos

Esta carpeta NO se versiona (datos reales de negocio, ver `.gitignore`).
Colocar acá, por corrida:

| Archivo | Contenido |
|---|---|
| `Stock_proyectado_Pilar.xlsx`, `_Chacabuco.xlsx`, `_CDT.xlsx` | Stock proyectado (Ibase) día a día |
| `Pilar_<SKU>.xlsx`, `Chaca_<SKU>.xlsx`, `CDT_<SKU>.xlsx` | Movimientos desagregados (Producción/Salida/Llegada) |
| `Pendientes_AFO.xlsx` | Pedidos pendientes (confirmados/no confirmados) |
| `PDG.xlsx` | Política de días de giro |

El forecast remanente y el plan de producción ya NO vienen de Excel — se
consultan directo a IBP vía OData (`src/ibp_client.py`, ver
`docs/checkpoint_proyecto.md`). Requiere `.env.txt` con `IBP_USERNAME`/
`IBP_PASSWORD` en la raíz del repo (ver `.env.txt.example`).

Ver `docs/checkpoint_proyecto.md` para el detalle de formato de cada fuente.
