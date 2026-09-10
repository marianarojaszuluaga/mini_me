# Plan de implementación — Basecamp Message Board Publisher (lo que falta)

**Proyecto:** orquestrador-360 (construido acá, no en un repo "Scrum Assistant" separado — no existe código)
**Basado en:** `SPEC-basecamp-message-board-publisher.md`, `HU-041-046-basecamp-publisher.md`, `PLAN-GABI-basecamp-publisher.md`
**Estado de partida:** Fase 1 (schema) + núcleo de Fase 2 (Resolver, Renderer, Publisher.publish síncrono) ya construidos y con 7 tests reales en verde — ver `app/schemas/basecamp_publication.py`, `app/services/basecamp_publisher.py`, `tests/test_basecamp_publisher.py`.
**Fecha:** 2026-09-07

---

## 0. Adaptaciones reales al stack de orquestrador-360 (vs. el plan original)

El plan de Gabi asume un backend con migraciones SQL, un job worker (`PublicationQueue`), y un
frontend con su propio sistema de diseño. Acá:

| Pieza del plan original | Adaptación real |
|---|---|
| Migración SQL + `UNIQUE` | Ya resuelto — serie `basecamp-publications` en Redis/JSON + chequeo de idempotencia en código (`_find_publication`) |
| `PublicationQueue` con worker propio | **No hay infraestructura de colas** en este repo (no Celery/RQ/SQS). Dos opciones reales, ver §1 |
| Sistema de diseño del frontend | Reusa `dashboard/src/components/Modal/Modal.jsx` + `command-center.css`, mismo patrón que `ConnectRepoForm`/`BasecampSection` ya construidos |
| `OrphanSweeper` como job cron | Puede vivir en `app/cron/sync_scheduler.py` (ya existe, corre cada 3h) — mismo problema real ya documentado: no dispara en Vercel serverless. Ver §1.2 |

---

## 1. Fase 2 (resto) — Cola de reintentos + Orphan Sweeper

### 1.1 Decisión real pendiente: ¿cola verdadera o reintento en el próximo request?

No hay worker persistente disponible en Vercel serverless (mismo problema real que ya encontramos
con `sync_scheduler.py`). Dos caminos honestos:

- **Opción A — Reintento perezoso (recomendada, sin infra nueva):** cuando algo lee el estado de
  una publicación `pending` (endpoint de Fase 3, o el propio `qa-sweep`/Dashboard), si pasaron los
  segundos del backoff correspondiente, se reintenta ahí mismo antes de responder. Sin cron, sin
  worker — el costo es que un `pending` no se resuelve hasta que alguien lo consulta.
- **Opción B — Vercel Cron Job real:** un endpoint `POST /internal/basecamp-publications/sweep`
  protegido, llamado por un Cron Job de Vercel (`vercel.json`) cada 1-2 min. Si Mariana quiere que
  esto se resuelva solo, sin depender de que alguien abra la UI, esta es la opción real.

**Necesito que elijas A o B antes de construir esto** — cambia el endpoint y el `vercel.json`.

### 1.2 Tareas (independiente de A/B)

1. `app/services/basecamp_publisher.py`: `retry_publication(publication_id)` — reintenta con los
   datos **actuales** del sprint (HU-045 CA-3), respeta el backoff (2s/8s/32s/2m/8m) comparando
   `created_at`/`attempts` contra el tiempo real transcurrido.
2. `sweep_orphans()` — reencola publicaciones `pending` con más de 15 min (HU-046 E-2).
3. Verificación previa antes de republicar (HU-046 E-3): antes de reintentar, buscar en
   `GET .../messages.json` recientes si ya existe un mensaje con el mismo `subject` exacto — evita
   duplicar si el POST anterior sí llegó pero el guardado del id falló.

---

## 2. Fase 3 — API (4 endpoints reales)

| Endpoint | Método | Archivo | Notas reales |
|---|---|---|---|
| `/projects/{id}/basecamp-publish` | GET | `app/routers/projects.py` | Lee `project.basecamp.publish` |
| `/projects/{id}/basecamp-publish` | PUT | `app/routers/projects.py` | Valida `category_id` contra `GET /buckets/{id}/categories.json` real antes de guardar (HU-043 E-1) — nuevo `list_categories()` en `basecamp_client.py` |
| `/sprints/{id}/publications` | GET | nuevo `app/routers/sprints.py` **o** anexo a `projects.py` (orquestrador-360 no tiene concepto de "sprint" propio con id — ver §4) | Lee la serie `basecamp-publications` filtrada por `sprint_id` |
| `/publications/{id}/retry` | POST | mismo archivo | Idempotente: si ya es `pending`/`sent`, 200 sin encolar (HU-045 CA-6) |

---

## 3. Fase 4 — Frontend (4 piezas reales)

Todas dentro de `dashboard/src/components/ProjectDetail/ProjectDetailDrillDown.jsx` (mismo patrón
que `BasecampSection`/`ConnectRepoForm` ya construidos) o extraídas a un archivo propio si crece
demasiado.

| Componente | Qué hace | Reusa |
|---|---|---|
| `BasecampPublishSettings` | Toggle + checkboxes de inicio/cierre + selector de categoría + personas a notificar | `Modal.jsx`, mismo patrón de `BasecampLinkForm` |
| `SprintPublicationStatus` | 3 estados: `sent` (✓ + link) / `pending` (Publicando…) / `failed` (⚠ + mensaje + Reintentar) | `BasecampMirrorCard` ya construido, mismo lugar |
| `RetryPublicationButton` | Visible solo en `failed`, llama al endpoint de retry | — |
| `errorMessageMap` | Mapea `last_error` técnico a texto legible (HU-044 E-3) | función pura, sin dependencias |

**Estados a implementar tal cual el spec (§ HU-044):**
```
sent    → "✓ Publicado" + "Ver post ↗" (target blank)
pending → "Publicando…" + botón de reintento deshabilitado
failed  → "⚠ Falló" + mensaje legible + botón "Reintentar"
oculto  → publish.enabled = false → no se renderiza la sección
```

---

## 4. Decisión real pendiente: ¿de dónde sale `sprint_id`?

El spec asume que Scrum Assistant ya tiene un dominio de Sprints con eventos
`sprint.started`/`sprint.closed`. **orquestrador-360 no tiene esto** — solo `Project.memory.sprints`
(`{current: int, status}`), sin id propio ni eventos de dominio reales.

**Necesito que definas esto antes de la Fase 3/4:**
- (a) Se usa el **Card Table seleccionado** (Tarea 2 Gap 3) como "sprint" — abrir/cerrar el sprint
  = marcar la Card Table activa/cerrada manualmente desde la UI. Reusa lo ya construido.
- (b) Se construye un dominio de Sprint real nuevo (id propio, fechas, estado) — trabajo adicional
  no estimado todavía.

---

## 5. Fase 5 — Integración (adaptada)

Igual que el plan original, pero contra el Auth Profile de Basecamp real que ya conectaste:

1. Sandbox: usar uno de los proyectos ya vinculados (Finanz Butik/PESMAV/Uptracker) o uno de prueba — **nunca activar `enabled: true` en un proyecto de cliente real sin avisar** (mismo R-2 del plan original).
2. HTML válido — confirmar que ninguna plantilla renderiza `<table>` (ya cubierto por 2 tests reales).
3. Idempotencia real — llamar `publish_event` dos veces con el mismo `sprint_id`+`event_type`, confirmar un solo POST.
4. Rate limit — no aplica todavía a nuestra escala (no hay 60 sprints cerrándose en 10s), se deja como riesgo bajo, no como tarea de esta ronda.
5. Token expirado — forzar un 401 real revocando el Auth Profile y confirmar el mensaje "Sesión de Basecamp expirada, reconecta la cuenta".

---

## 6. Orden sugerido

```
[Ya hecho] Fase 1 + Resolver/Renderer/Publisher síncrono
   ↓
§4 decisión (sprint_id) ←── bloquea Fase 3 y 4
   ↓
§1.1 decisión (cola A/B) ←── bloquea 1.2
   ↓
Fase 2 resto (retry + sweep)
   ↓
Fase 3 (4 endpoints)
   ↓
Fase 4 (4 componentes)
   ↓
Fase 5 (integración real, sandbox)
```

## 7. Qué necesito de ti para poder ejecutar esto

1. **§1.1** — ¿reintento perezoso (A, sin infra nueva) o Cron Job real de Vercel (B)?
2. **§4** — ¿el "sprint" es el Card Table ya construido (a, reusa todo), o hace falta un dominio de Sprint nuevo (b)?
3. Confirmar que apruebas el orden de §6, o priorizas distinto (ej. Fase 3/4 antes que completar la cola, para poder probarlo desde la UI cuanto antes aunque los reintentos queden manuales por ahora).
