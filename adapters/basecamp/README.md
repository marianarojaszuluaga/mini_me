# Adaptador Basecamp (seed — no conectado aún)

> Estado: **PoC / referencia**, sin código de integración real todavía. Consolidado desde el
> prototipo `sprint-assistant` (mini me), que probó la autenticación y el fetch de datos contra
> la API de Basecamp de forma aislada, sin conexión al orquestrador.

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

## Para conectarlo de verdad

1. Formalizar un cliente (`adapters/basecamp/client.js`) que envuelva `AUTH_POC.md` en código,
   con refresh de token — hoy es solo curl manual.
2. Registrar `basecamp` en `toolRegistry` (`src/orchestrator.js`), igual que `map`.
3. Decidir el mapeo Card Table ↔ HU/Sprint (qué columna es "in progress"/"done" — pregunta abierta
   heredada del spec original de Scrum Assistant, nunca resuelta).
4. Credenciales (`Client ID`/`Client Secret`/tokens) van a `.env`, nunca a este repo — el
   `AUTH_POC.md` ya evita exponer el secret real.
