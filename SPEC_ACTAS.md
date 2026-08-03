# SPEC — Actas (flujo completo + módulo de compartir)
> **Status**: Diseño conceptual cerrado — sin código todavía
> **Creado**: Agosto 2026

---

## El flujo completo

| # | Paso | Estado |
|---|---|---|
| 1 | Crear acta | ✅ Ya existe (Apps Script: Calendar → transcript → Gemini → Doc) |
| 2 | Agregar al historial | ✅ Ya existe (`meetingLog` en el Project Brain, vía `/brain/ingest-acta`) |
| 3 | Extraer info clave al Brain | ✅ Ya existe (Gabriela extrae decisiones/alertas) |
| 4 | Compartir el acta | ⚠️ Rediseñado abajo — hoy solo hace la mitad (correo con link, en borrador) |

---

## Paso 4 — Módulo de Compartir (rediseño)

Modular: cada canal se puede prender/apagar, elegir formato, y personalizar el mensaje.

### Canales

| Canal | Estado | Config |
|---|---|---|
| **Correo** | Se ajusta ahora | `enabled` (on/off) · `mode`: `draft` \| `send` · **adjunta el archivo real** (no solo link) · mensaje personalizable |
| **Basecamp** | Bloqueado — requiere que Mariana cree una OAuth app en Basecamp y la autorice | `enabled` (on/off) · `publishAs`: `message` (post tipo noticia) \| `document` (subir archivo) · mensaje personalizable |

### Variables disponibles para el mensaje personalizable

| Variable | Fuente | Ya calculado por el Apps Script? |
|---|---|---|
| `{cliente}` | Del proyecto | Sí (vía `obtenerNombreProyecto`) |
| `{proyecto}` | Del proyecto | Sí |
| `{fecha}` | Fecha de la reunión | Sí (`fechaReunion`) |
| `{semana}` | Semana del año (ISO), calculada desde `{fecha}` | No — cálculo nuevo simple |
| `{resumen}` | Highlights del acta | Sí, ya se genera para el correo actual |
| `{decisiones}` | Sección "Decisiones Tomadas" | Sí, ya se extrae (`extraerResumenCorreoDesdeActa`) |
| `{proximos_pasos}` | Sección "Próximos Pasos" | Sí, ya se extrae |
| `{link_doc}` | URL del Google Doc | Sí (`linkDoc`) |

La mayoría de las variables ya existen en el código actual del Apps Script — el trabajo real
es exponerlas como plantilla en vez de un HTML fijo, más el cálculo nuevo de `{semana}`.

---

## Gaps a construir

1. Adjuntar el archivo real al correo (hoy solo manda link) — cambio simple en Apps Script
   (`DriveApp`/`GmailApp` ya autenticados, no requiere nada nuevo de Mariana).
2. Enviar el correo de verdad en vez de dejarlo en borrador — toggle `mode: send`.
3. Cálculo de `{semana}` (número de semana del año) desde la fecha de la reunión.
4. Sistema de plantilla de mensaje con sustitución de variables (`{cliente}`, etc.).
5. Integración con Basecamp (API OAuth) — **bloqueada hasta que Mariana cree la app OAuth en
   Basecamp y la autorice.** No se construye nada de esto hasta que ese prerequisito exista.

---

## Open Questions

- [NEEDS CLARIFICATION] Formato exacto del post en Basecamp cuando `publishAs: document` —
  ¿sube el archivo tal cual, o también necesita un mensaje de texto acompañándolo?
- [NEEDS CLARIFICATION] Plantilla de mensaje por defecto — ¿Mariana la escribe, o propongo un
  default y ella la ajusta?
