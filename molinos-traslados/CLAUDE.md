# Guía para Claude Code — Motor de traslados Molinos

Este repo implementa un modelo MILP de optimización de traslados de
harina entre 3 centros (Pilar, Chacabuco, CDT). Antes de proponer
cambios, leer `docs/checkpoint_proyecto.md` (historial de decisiones de
negocio) y `docs/modelo_matematico.md` (formulación matemática completa).

## Reglas de negocio que NO deben romperse sin confirmación explícita

- CDEE está eliminado del alcance a propósito (decisión de negocio, no
  omisión). No reintroducir arcos/lógica de CDEE sin que se pida.
- El camión completo (25 pallets, `CAMION_PALLETS` en
  `config/parametros.py`) es una restricción DURA, no un costo. No
  convertirla en penalización blanda.
- Pilar→Chacabuco está prohibido a propósito (Chacabuco no recibe
  traslados de nadie). Chacabuco→Pilar sí está permitido.
- El target de cobertura (`construir_target` en `src/model.py`) usa la
  suma real de forecast dentro de la ventana de `g` días — NO es un
  promedio constante multiplicado por `g`. Este fue un error ya corregido
  en el proyecto; no reintroducirlo.
- La corrección de Ibase (`construir_ibase_final` en `src/data_loader.py`)
  aplica `max(dato_real, plan/forecast)` tanto para demanda como para
  oferta (producción), de forma simétrica. Si se detecta stock
  fuertemente negativo pese a esta corrección, es una ALERTA genuina de
  producción no cargada en el sistema — no "arreglar" ocultando el
  negativo, reportarlo.

## Convenciones de código

- Todo dict de datos usa tuplas `(sku, nodo, t)` o `(sku, nodo)` como
  clave — mantener esa convención en nuevas funciones.
- Pesos y costos van en `config/parametros.py`, no hardcodeados en
  `src/model.py` ni en `src/data_loader.py`.
- Los solvers deben corer con `disp: False` salvo debugging explícito
  (evita ruido de logs).

## Al iterar

- Preguntar antes de cambiar el alcance de SKUs/nodos si no está
  explícitamente pedido.
- Cualquier cambio a la calibración (α, β, costos) debe declararse en
  términos de RATIO relativo, no solo el número absoluto, y agregarse al
  changelog en `docs/checkpoint_proyecto.md`.
