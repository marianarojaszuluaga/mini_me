# Adaptador Basecamp (seed histórico — superado por app/services/basecamp_client.py)

> Estado: **PoC / referencia histórica**. La integración real ya existe y está conectada:
> [`app/services/basecamp_client.py`](../../app/services/basecamp_client.py) (cliente HTTP vía
> `httpx`, auth OAuth reutilizando `AuthProfile`) +
> [`app/services/basecamp_publisher.py`](../../app/services/basecamp_publisher.py) (Message
> Board Publisher, Fases 1-4 completas y verificadas con tests) +
> [`app/services/basecamp_nomenclature.py`](../../app/services/basecamp_nomenclature.py) (parser
> de nomenclatura Autobasecamp). Este folder queda como **contexto histórico** de cómo se
> exploró la auth y el payload de la API antes de esa implementación — no se debe construir un
> segundo cliente aquí; cualquier trabajo nuevo de Basecamp va en `app/services/basecamp_*.py`.
>
> Consolidado desde el prototipo `sprint-assistant` (mini me), que probó la autenticación y el
> fetch de datos contra la API de Basecamp de forma aislada, sin conexión al orquestrador.

## Por qué vive aquí

El orquestrador es **agnóstico a sus conexiones** (ver "Principio: agnóstico al ecosistema y al
front" en el [README](../../README.md) raíz): Basecamp, Slack, n8n, WhatsApp — todo entra como un
**tool intercambiable** detrás de `toolRegistry` en `src/orchestrator.js`, nunca como lógica
bespoke mezclada con los agentes. Este folder es el punto de partida para ese tool, todavía sin
registrar.

## Dónde encajaría en las 5 fases

Basecamp no es una fase en sí — es una **fuente/destino de datos** que dos fases ya necesitan:

- **Planning (Fase 2)**: traer el Card Table / To-do lists de un proyecto Basecamp como input para
  Gimena (HUs) y Gabi (planes de trabajo), en vez de escribirlos a mano. `fetch_column.ps1` +
  `sample_column_cards.json` muestran la forma real de ese payload.
- **Follow-up / Seguimiento (Fase 3)**: reflejar de vuelta a Basecamp el estado de sprints,
  actas (Santi) o alertas del Project Brain (Gabriela) — la misma auth de `AUTH_POC.md` sirve
  para escribir, no solo leer.

## Archivos

| Archivo | Qué es |
|---|---|
| `AUTH_POC.md` | Guía paso a paso de auth OAuth + llamadas curl contra la API de Basecamp (cuenta/proyecto de ejemplo: Finanz Butik) |
| `fetch_column.ps1` | Script PowerShell que trae las cards de una columna del Card Table |
| `sample_column_cards.json` | Payload real de ejemplo devuelto por Basecamp (para diseñar el mapeo sin llamar a la API) |
| `sample_batch_input.md` | Ejemplo de batch de tareas para importar (relacionado con el flujo de import CSV del prototipo original) |

## Estado real (actualizado 2026-09-22)

Los puntos 1 y 4 de la lista original ya están resueltos por `basecamp_client.py` (cliente HTTP
con refresh de token vía `AuthProfile`, credenciales solo en `.env`/`BASECAMP_OAUTH_CLIENT_*`).
Pendiente, si se retoma:

1. Decidir el mapeo Card Table ↔ HU/Sprint (qué columna es "in progress"/"done" — pregunta abierta
   heredada del spec original de Scrum Assistant, nunca resuelta).
2. Si Basecamp necesita exponerse como servicio HTTP propio (no solo un cliente invocado desde
   dentro de `app/`), evaluar entonces registrarlo en `toolRegistry` (`src/orchestrator.js`) —
   ese registro es para *servicios* con URL propia (como `map`), y Basecamp hoy no lo es: es un
   cliente de librería usado in-process, lo cual ya cumple "invocar sin depender de su código".

`toolRegistry` no aplica a este caso mientras Basecamp siga siendo un cliente in-process — forzar
el registro ahí sin un servicio real detrás sería una capa sin propósito, no una mejora de
desacoplamiento (ver [tests/test_boundary_coupling.py](../../tests/test_boundary_coupling.py),
que ya vigila que ningún otro archivo importe basecamp_client.py por fuera de su rol).
