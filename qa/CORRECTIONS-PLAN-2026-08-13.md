# Plan de correcciones — post QA Round 1
> Basado en `qa/QA-EXECUTION-ROUND-1-2026-08-13.md`. Solo cubre lo que quedó **abierto** después
> de los fixes ya aplicados en esa misma ronda (BUG-001/002/003/004/007/008/010/011/012/013 ya
> están Fixed y verificados — no se repiten aquí).

## P0 — Bloquea que la reconciliación sirva de algo con HUs reales

**Hallazgo nuevo, no estaba en el defect log**: `app/services/brain/reconciliation.py` parsea
Acceptance Criteria buscando checkboxes `- [ ]`, pero el formato **canónico de Gimena**
(`src/agents/spec-kit-agents/Gimena-userstorywriter.md`, el que realmente generó
`outputs/HU_RUN-001_2026-08-12.md`) nunca usa checkboxes — usa subsecciones numeradas
(`2.1 Interfaz y Experiencia`, `2.2 Casos de Uso`, `2.3 Manejo de Errores`). Resultado: contra
cualquier HU real generada por Gimena, el motor siempre devuelve `no_reconciliable` para las 10
HUs (confirmado en T-RECON-02) — la reconciliación está "implementada" pero es **funcionalmente
inútil** hoy.

- [ ] Redefinir la unidad reconciliable: en vez de un checkbox, usar cada bullet dentro de
  `2.1`/`2.2`/`2.3` (o cada fila de la tabla de "Manejo de Errores") como el AC individual.
- [ ] Actualizar la convención de vínculo `@ac:HU-XXX-N` para que N se numere contra esas
  subsecciones reales, no contra checkboxes que no existen.
- [ ] Re-correr `POST /projects/{id}/reconciliation/run` contra este mismo repo (que ya tiene
  HUs reales) y confirmar que produce al menos un gap/status distinto de `no_reconciliable` en
  todas las 10.

## P1 — Gaps de producto (HU-008) y limitación de ambiente

- [ ] **GAP-005**: construir el detector "2 invocaciones seguidas bajo umbral" y conectarlo a
  `changelog.create_proposal()` — hoy nada lo dispara automáticamente (HU-008 AC 2.1.3).
- [ ] **ENV-006**: no es un bug — cuando decidas poner una `ANTHROPIC_API_KEY` real, re-ejecutar
  T-ANALYTICS-08/09/10 y HU-008 en general para confirmar en vivo (hoy solo verificado por
  lectura de código).

## P2 — Backend feature real faltante (no un parche de UI)

- [ ] **BUG-009**: agregar `syncStatus`/`retryable`/`lastError` al schema `Repository`
  (`app/schemas/project.py`) y que `sync_scheduler.py` los actualice de verdad. Sin esto, el
  frontend no tiene datos reales que mostrar — construir la UI antes sería fabricar estados falsos.
- [ ] **BUG-017**: guardar `scope` real al crear un Auth Profile (`account + org/alcance legible`,
  no solo el id crudo) para que el selector de "+ Conectar repo" muestre algo humano.

## P3 — Limpieza (S4, no bloquean nada, pero acumulan deuda visible en QA)

- [ ] **BUG-014**: agregar `@font-face` real para GeistSans (o servirla desde Google
  Fonts/self-host) — hoy el token existe pero cae en silencio al sans del SO.
- [ ] **BUG-015**: eliminar el `:root` competidor de `styles.css` (`--primary`, `--success`, etc.)
  y migrar las clases legadas (`.btn-primary`, `.login-card`, `.header`) a `design-tokens.css` —
  hoy coexisten dos sistemas de tokens.
- [ ] **BUG-016**: conectar el tile "Gaps totales" del home a un run real de reconciliación (hoy
  se queda en 0 aunque haya gaps).
- [ ] **BUG-018**: borrar `mar_memory.update_entry()` (código muerto, nadie lo llama — el front
  edita vía POST-con-id, que sí funciona).

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
