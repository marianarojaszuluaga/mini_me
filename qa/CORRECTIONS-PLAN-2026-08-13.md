# Plan de correcciones — post QA Round 1
> Basado en `qa/QA-EXECUTION-ROUND-1-2026-08-13.md`. Solo cubre lo que quedó **abierto** después
> de los fixes ya aplicados en esa misma ronda (BUG-001/002/003/004/007/008/010/011/012/013 ya
> están Fixed y verificados — no se repiten aquí).

## P0 — ✅ Resuelto (2026-08-13) — reconciliación funcional con HUs reales

`app/services/brain/reconciliation.py` ahora parsea las subsecciones reales de Gimena
(`2.1`/`2.2`/`2.3`, bullets + filas de tabla de errores) en vez de checkboxes que nunca existían.
Verificado en vivo: `POST /projects/{id}/reconciliation/run` contra este repo produjo **98 ACs
reales** (antes: 10 `no_reconciliable` en bloque), 0 `no_reconciliable`. La misma convención
quedó documentada en `qa/QA-EXECUTION-TEMPLATE.md`.

## P1 — ✅ Resuelto — gaps de producto (HU-008) y limitación de ambiente

- [x] **GAP-005**: el detector "2 invocaciones seguidas bajo umbral" (`check_degradation` en
  `evaluate_invocation.py`) ya está conectado a `changelog.create_proposal()`. Verificado en vivo
  2026-08-13: se sembraron 2 evaluaciones bajas reales para un agente de prueba vía
  `collector.record_evaluation()`, y `check_degradation()` devolvió `True` correctamente (y
  `False` para una dimensión sin racha baja) — confirma que la lógica de "estrictamente 2
  consecutivas" funciona con datos reales, no solo por lectura de código. Datos de prueba
  limpiados de `storage/` después (que de todos modos está en `.gitignore`).
- [x] **ENV-006**: ya no es una limitación — se conectó una `ANTHROPIC_API_KEY` real (proxy
  LiteLLM de Mariana, `admin-llm.imagineapps.co`, modelo `claude-sonnet-4-6`), probada en vivo con
  una llamada real a `messages.create` que devolvió una respuesta real.

## P2 — Backend feature real faltante (no un parche de UI)

- [x] **BUG-009 — Resuelto (2026-08-13).** `syncStatus`/`lastError` reales en `Repository`,
  actualizados por `sync_one_repository()` (compartida entre conectar-repo, "Reintentar" y el cron
  de 3h). Verificado en vivo con la API real de GitHub: repo público → `synced`; repo inexistente
  → `error` con el 404 real de GitHub; "Reintentar" repite la misma llamada real. Confirmado
  también visualmente en el navegador.
- [x] **BUG-017 — Resuelto** (misma ronda que BUG-016/018, ver más abajo).

## P3 — ✅ Resuelto — Limpieza (S4)

- [x] **BUG-014**: Inter cargada real vía Google Fonts (no GeistSans — no existe en Google Fonts,
  decisión confirmada con Mariana).
- [x] **BUG-015**: `:root` competidor de `styles.css` eliminado, clases legadas migradas a
  `design-tokens.css`.
- [x] **BUG-016**: KPI "Gaps totales" corregido — leía `reconciliation?.items` (clave que nunca
  existió; el backend manda `.gaps`). Verificado en vivo: 108 real (antes 0).
- [x] **BUG-017**: selector de Auth Profile ahora muestra `{account} — {scope|provider}`, no el id
  crudo. Verificado en vivo.
- [x] **BUG-018**: `mar_memory.update_entry()` borrado (código muerto confirmado).

## Sin categoría de severidad, pero vale resolver pronto

- [ ] **CORS bloqueó la verificación E2E completa de BUG-004/BUG-011 en navegador** — hoy
  `allow_origins=["*"]` + `allow_credentials=True` es una combinación que Chrome rechaza. Arreglar
  esto no es solo higiene: sin arreglarlo, **ninguna ronda de QA futura puede verificar nada end-to-end
  en navegador real**, solo por contrato via curl.
- [ ] **`AgentInvokePanel` es código muerto** (T-DS-07) — el sitemap (`SPEC_JARVIS.md` §2) todavía
  lista "⚙️ Invocar Agente" como un drill-down válido para cuando no se quiere pasar por el chat.
  Decisión pendiente: ¿se recupera como drill-down real, o se borra del sitemap porque el chat ya
  cubre ese caso de uso? Necesito tu decisión antes de tocarlo — no es solo un fix de código.

## Orden de ejecución sugerido
P0 (reconciliación real) → P1 (GAP-005) → P2 (sync status + auth profile label) → P3 (limpieza) →
CORS + decisión de `AgentInvokePanel`.
