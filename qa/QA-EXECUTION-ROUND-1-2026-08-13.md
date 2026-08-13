# QA Test Execution — Orquestrador 360 / Jarvis Mode — Ronda 1

> Documento consolidado a partir de la ejecucion real de 4 equipos QA (subagentes) contra el sistema
> corriendo en local (backend FastAPI real, frontend Vite real, storage filesystem real). Estructura
> basada en `QA-EXECUTION-TEMPLATE.md` (Finanz Butik V2). Ningun resultado fue fabricado: lo no
> ejecutado esta marcado `⛔ Blocked`, nunca `✅ Pass`.

## Como usar
Ver reglas del template original (3 checks T/UX/HU, Result solo Pass si Expected + T + UX + HU).

## Legends
- **Result:** ✅ Pass · ❌ Fail · ⛔ Blocked · ⚪ N/A · ⏳ Not run
- **Type:** Smoke · Functional · E2E · S (Security) · N (i18n) · M (Mobile) · A (Accessibility) · P (Performance)
- **Severity:** S1 Blocker · S2 Critical · S3 Major · S4 Minor · S5 Cosmetic

---

## Run header
| Field | Value |
|---|---|
| Milestone / Steps | Jarvis Mode — Command Center, Multi-repo, Reconciliacion, Chat, Memoria de Mar, Analitica, Changelog, Scheduler (HU-001 a HU-010) |
| Build / Commit | `9e1df03` "Add changelog, auto-eval wiring, analytics drill-down; fix uncaught 500" (branch `main`, working tree con `Gabi-workplanner.md` modificado sin commitear) |
| Environment / URL | Local — Backend FastAPI `http://localhost:8005` (confirmado `/health` → `{"status":"ok"}`) · Frontend Vite `http://localhost:5173` (confirmado HTTP 200) |
| Platform | Web (Chrome, viewports 1280x800 / 1366x712 / 368x616 segun equipo) |
| **Locale under test** | es-MX ☑ (unico locale presente en la UI) · en-US ☐ · pt-BR ☐ |
| Backend / CRM | Real FastAPI, storage filesystem real. `ANTHROPIC_API_KEY` es un placeholder (`sk-ant-fake-for-local-boot-test`) — toda llamada real a Claude falla con 401/500 |
| **Tester(s)** | Ronda de agentes QA automatizada (4 subagentes: Design System, Multi-repo/Reconciliacion, Chat/Memoria de Mar, Analitica/Changelog/Scheduler) |
| **Testing time** | Sesion unica, 2026-08-12/13 |
| **Evidence link** | Screenshots y transcripts de curl capturados inline en cada sub-reporte (no hay carpeta compartida; ver detalle por escenario) |
| Date / Cycle | 2026-08-13 · Cycle #1 |

---

## Test execution — Grupo 1 · Design System (Geist compliance)
> Traceability: SPEC_JARVIS.md §2, GEIST_DESIGN_SYSTEM.md

| ID | Type | Scenario (Given/When/Then) | Expected | Validate | Result | Sev | Actual/Finding | Evidence |
|---|---|---|---|---|---|---|---|---|
| T-DS-01 | Functional/UX | Given sesion autenticada, When el dashboard carga a 1280x800, Then el Command Center ocupa el layout de 2 columnas completo (SPEC §2) | Chat panel (2fr) + Status panel (1fr) llenan el viewport | ☑T ☑UX ☐HU | ✅ Pass | — | Bug historico de "cajita arriba a la izquierda" corregido. `.command-center-grid` usa `display:grid; grid-template-columns: 2fr 1fr` con `min-height:0` | Screenshot |
| T-DS-02 | Functional/A | Given dashboard cargado, When se mide `scrollWidth` vs `clientWidth`, Then no hay scroll horizontal de pagina | `scrollWidth === clientWidth` | ☑T ☑UX ☐HU | ✅ Pass | — | `scrollWidth:1366, clientWidth:1366, hasHorizontalScroll:false` | JS eval |
| T-DS-03 | Functional | Given la fila de botones "Analitica e Integraciones" en el Status panel, When renderiza con 3 botones, Then no debe desbordar su contenedor | Fila cabe o hace wrap | ☑T ☑UX ☐HU | ❌ Fail | S3 | Los 3 botones usan `.modal-buttons` (legado de `styles.css`, `flex-wrap:nowrap`), la fila desborda y el panel genera su propio scroll horizontal; "Integraciones" se trunca a "Inte…" | Screenshot zoom |
| T-DS-04 | Functional | Given la fila de botones de `StatusPanel.jsx`, When se inspecciona `background-color`, Then debe resolver a un token HSL de `design-tokens.css` | `background-color` → `hsl(var(--ds-*))` | ☑T ☐UX ☐HU | ❌ Fail | S3 | `getComputedStyle(.btn-primary).backgroundColor === "rgb(39,174,96)"` = `#27AE60`, definido en `styles.css` como `--success` (token boilerplate, no `design-tokens.css`) | JS eval |
| T-DS-05 | Functional | Given cualquier texto bajo `.command-center`, When se inspecciona `font-family`, Then debe resolver via `var(--font-sans)` (GeistSans) | Cadena incluye GeistSans | ☑T ☑UX ☐HU | ❌ Fail | S4 | El token esta bien referenciado pero **no existe ningun `@font-face` para GeistSans en `src/`** — cae silenciosamente al sans del SO. Ademas `.btn-primary` renderiza en Arial (sin regla de fuente) | Grep + JS eval `btnFont:"Arial"` |
| T-DS-06 | Functional | Given header/login screen, When se inspecciona `html, body`/`.header`/`.login-card`, Then los colores/fuentes deben venir de `design-tokens.css` | Fuente unica de verdad | ☐T ☑UX ☐HU | ❌ Fail | S4 | `styles.css` declara su propio `:root` competidor (`--primary:#667eea`, etc.) independiente de `--ds-*`; `App.jsx:11` aun lo importa solo para mantener vivas clases legadas | `styles.css:5-15`, `App.jsx:11,463` |
| T-DS-07 | Functional | Given el bug historico "panel Invocar Agente inclickable/superpuesto", When se busca ese panel en la UI actual, Then verificar que esta corregido | Panel presente y clickeable, sin overlap | ☐T ☐UX ☐HU | ⛔ Blocked | — | `AgentInvokePanel` sigue definido en `App.jsx:225-311` pero es **codigo muerto** — `CommandCenterLayout` no lo renderiza. No se puede confirmar/negar el bug original porque el panel ya no esta en el render tree | `App.jsx:225-311` |

---

## Test execution — Grupo 2 · Multi-repo y Reconciliacion (HU-001, HU-002, HU-004, HU-005)

| ID | Type | Scenario | Expected | Validate | Result | Sev | Actual/Finding | Evidence |
|---|---|---|---|---|---|---|---|---|
| T-MULTIREPO-01 | Smoke | GET `/projects/{id}/repositories` en proyecto sin repos | `200 []` | ☑T ☑UX ☐HU | ✅ Pass | — | `[]`, 200 | curl |
| T-MULTIREPO-02 | Functional | POST repo valido (github, environment=develop, authProfileId) | `201` + registro persistido | ☑T ☐UX ☐HU | ✅ Pass (parcial) | — | 201 con id/provider/owner/repo/defaultBranch/environment/connectedAt. Sin campo `authProfileId` en la respuesta (solo `accessTokenRef:null`) | curl |
| T-MULTIREPO-03 | Functional | POST repo con provider desconocido (`gitlab`) | Rechazo, error claro | ☑T ☑UX ☐HU | ✅ Pass | — | `400 {"detail":"Unknown repository provider: 'gitlab'"}` | curl |
| T-MULTIREPO-04 | Functional | POST repo sin `environment` | AC 2.3: debe ser obligatorio antes de guardar | ☐T ☐UX ☐HU | ❌ Fail | S2 | Backend acepto y creo el repo con `"environment":null`, `201`. Solo el `<select required>` del front lo bloquea | curl |
| T-MULTIREPO-05 | Functional/E2E | POST el mismo repo exacto dos veces al mismo proyecto | AC 2.3: bloquea duplicado | ☐T ☑UX ☐HU | ❌ Fail | S1 | Backend creo una **segunda** entrada identica (201), sin chequeo de duplicados. Confirmado en vivo: "Repositorios asociados" muestra 2 cards identicas | curl x2 + screenshot |
| T-MULTIREPO-06 | Smoke | GET repositories tras los inserts | Lista refleja todos los repos conectados | ☑T ☑UX ☐HU | ✅ Pass | — | Retorno los 3 repos correctamente (incl. duplicado) | curl |
| T-MULTIREPO-07 | Functional | GET `/auth-profiles` | `200 []` en vacio | ☑T ☑UX ☐HU | ✅ Pass | — | `[]` | curl |
| T-MULTIREPO-08 | Functional | POST `/auth-profiles` (bitbucket, account) | `201` con perfil persistido | ☑T ☑UX ☐HU | ✅ Pass | — | 201 con id/provider/account, scope:null, token_ref:null | curl |
| T-MULTIREPO-09 | Security | GET repositories sin header Authorization | `401` | ☑T ☑UX ☐HU | ✅ Pass | — | `401 {"detail":"No token provided"}` | curl |
| T-MULTIREPO-10 | Functional | DELETE un repo existente | `200`, historial de Brain se mantiene (AC 2.2) | ☑T ☐UX ☐HU | ✅ Pass (parcial) | — | `200 {"deleted":true,...}`. No se pudo verificar retencion de historial (sin datos en Brain para ese proyecto) | curl |
| T-MULTIREPO-11 | Functional | DELETE repo inexistente | `404` claro | ☑T ☑UX ☐HU | ✅ Pass | — | `404 {"detail":"Repository not connected to this project"}` | curl |
| T-MULTIREPO-12 | E2E/UI | Abrir "Detalle de Proyecto" → "Repositorios asociados" → "+ Conectar repo" | Selector de Auth Profile, campos owner/repo, environment obligatorio, boton "Conectar" | ☑T ☑UX ☐HU | ✅ Pass | — | Formulario correcto, `<select required>` con placeholder "Environment (obligatorio)" | screenshot |
| T-MULTIREPO-13 | Functional/UX | Selector de Auth Profile debe mostrar "cuenta y alcance" (AC 2.1.2) | Label legible para humano | ☐T ❌UX ☐HU | ❌ Fail | S4 | Dropdown mostro el id crudo `bitbucket_1786594829096 (bitbucket — mariana@imagineapps.co)`, sin info de scope (backend no la guarda) | screenshot |
| T-MULTIREPO-14 | UI | Badges de estado de sync ("Sincronizando…", "Sincronizado", "Error" + "Reintentar") | Estados renderizados en la card | ☐T ☐UX ☐HU | ⛔ Blocked (fail por codigo) | S3 | `ProjectDetailDrillDown.jsx` solo renderiza una linea estatica "Ultima sincronizacion"; no existe maquina de estados ni boton Reintentar | lectura de codigo |
| T-MULTIREPO-15 | UI | Click en card de repo → expandir resumen de eventos/reconciliacion | Interaccion expand/detail | ☐T ☐UX ☐HU | ⛔ Blocked (feature ausente) | — | No existe handler de click ni estado de expansion en `.pd-repo-item` | lectura de codigo |
| T-RECON-01 | Smoke | GET `/projects/{id}/reconciliation` antes de correr | `200`, gaps vacios, `lastRunAt:null` | ☑T ☑UX ☐HU | ✅ Pass | — | `{"gaps":[],"lastRunAt":null}` | curl |
| T-RECON-02 | Functional | POST `/projects/{id}/reconciliation/run` contra HU_RUN-001 real | Gaps por AC `{huId, acceptanceCriterion, testRef, status}` | ☑T ☑UX ☑HU | ✅ Pass | — | 10 entradas (HU-001..010), todas `no_reconciliable` — correcto per AC 2.3, pero senala que el archivo real de HUs usa lista numerada, no checkboxes, asi que el motor no produce señal accionable hoy | curl |
| T-RECON-03 | Smoke | GET `/projects/{id}/timeline` | `200`, lista de eventos paginada | ☑T ☑UX ☐HU | ✅ Pass (parcial) | — | `{"days":7,"events":[]}` — no se pudo verificar paginacion (sin eventos) | curl |
| T-RECON-04 | Functional/E2E | Reconciliacion on-demand en proyecto con 0 repos conectados | AC 2.3: chat/API responde explicito que no hay repo, no inventa resultado | ☐T ❌UX ❌HU | ❌ Fail | S3 | Retorna 200 con los mismos 10 gaps sinteticos + una `note` bolted-on, en vez de cortocircuitar | curl |
| T-RECON-05 | UI | KPI "Gaps totales" en home del Command Center | Refleja el conteo real tras un run | ☐T ❌UX ☐HU | ❌ Fail | S4 | Tras correr reconciliacion (10 gaps), el tile sigue en 0 | screenshot |
| T-RECON-06 | E2E/UI | Drill-down → Project Brain → Reconciliacion → "Reconciliar ahora" | Corre reconciliacion, renderiza gaps con pills de estado | ☐T ☐UX ☐HU | ⛔ Blocked | — | Codigo correcto por lectura (`ReconciliationSubsection`), no ejecutado en vivo por tiempo | lectura de codigo |
| T-RECON-07 | UI | Tab Timeline en drill-down | Lista cronologica, "sin novedades relevantes" por evento (AC 2.3) | ☐T ☐UX ☐HU | ⛔ Blocked | — | `TimelineSection` ordena y renderiza correctamente pero solo tiene un empty-state generico, no por-evento; sin eventos reales para exercitar | lectura de codigo + curl |

---

## Test execution — Grupo 3 · Jarvis Chat (HU-006) y Memoria de Mar (HU-007)

| ID | Type | Scenario | Expected | Validate | Result | Sev | Actual/Finding | Evidence |
|---|---|---|---|---|---|---|---|---|
| T-CHAT-01 | Smoke | POST `/jarvis/chat` sin `conversation_id` ni `purpose` | `400` claro | ☑T ☑UX ☑HU | ✅ Pass | — | `{"detail":"purpose is required..."}`, 400 | curl |
| T-CHAT-02 | Functional | POST `/jarvis/chat` con `purpose` valido, `ANTHROPIC_API_KEY` invalida | Error limpio (AC 2.3), no 500 crudo | ☑T ☐UX ☐HU | ❌ Fail | S2 | `Internal Server Error`, HTTP 500, sin body. `_run_agentic_loop` llama a `client.messages.create` sin try/except, a diferencia de `agents.py::invoke_agent_core` que si lo maneja | curl |
| T-CHAT-03 | E2E | ChatPanel real: enviar primer mensaje (sin forma de dar `purpose` en la UI) | Chat responde o muestra error legible (AC "no invoca sin proposito") | ☑T ☑UX ☐HU | ❌ Fail | S2 | `sendChatMessage` nunca envia `purpose` — cada primer mensaje de sesion es rechazado 400; Jarvis Chat no funcional desde la UI real en el primer turno | screenshot banner "/jarvis/chat failed (400)" |
| T-CHAT-04 | Functional | Parseo de error 400/500 en `api-client.js` (AC 2.3: legible, no JSON crudo) | Usuario ve el `detail` real | ☑T ☑UX ☐HU | ❌ Fail | S3 | `api-client.js:29` busca `body.error`, FastAPI manda `body.detail` — el usuario solo ve el fallback generico | screenshot + lectura de codigo |
| T-CHAT-05 | Functional | Resolver TODO del frontend: shape camelCase vs snake_case | Confirmar keys reales del JSON | ☑T ☐UX ☐HU | ✅ Resuelto (finding, no Pass/Fail) | — | Sin `alias_generator` en ningun schema — la API es **snake_case** puro; el fallback camelCase en `ChatPanel.jsx` es codigo muerto pero inofensivo | grep |
| T-CHAT-06 | E2E | Enviar mensaje: burbuja "Tu" inmediata + indicador "escribiendo..." | Burbuja optimista + typing indicator | ☑T ☑UX ☑HU | ✅ Pass | — | Confirmado visualmente | screenshots |
| T-CHAT-07 | Functional | POST `/jarvis/chat` sin header Authorization | `401` claro | ☑T ☑UX ☑HU | ✅ Pass | — | `{"detail":"No token provided"}`, 401 | curl |
| T-CHAT-08 | Functional | POST `/jarvis/chat` con `conversation_id` desconocido | `404` claro, no crash | ☑T ☑UX ☑HU | ✅ Pass | — | `{"detail":"Unknown conversation_id: nope-123"}`, 404 | curl |
| T-MAR-01 | Smoke | GET `/mar/memory` en store vacio | `[]`, 200 | ☑T ☑UX ☑HU | ✅ Pass | — | `[]`, 200 | curl |
| T-MAR-02 | Functional | POST `/mar/memory` con entrada nueva `understanding` | 201, entrada con `id`/`createdAt` generados | ☑T ☑UX ☑HU | ✅ Pass | — | 201 con campos completos | curl |
| T-MAR-03 | Functional | Regla de dedup (AC 2.3): POST mismo `type`+`content` dos veces | Segunda llamada actualiza la entrada existente (mismo id) | ☑T ☑UX ☑HU | ✅ Pass | — | Mismo `id` en ambos POSTs, `createdAt` refrescado. Jaccard similarity (umbral 0.6) confirmado por codigo | curl + lectura de codigo |
| T-MAR-04 | Functional | DELETE `/mar/memory/{id}` existente | 200, entrada removida de GET | ☑T ☑UX ☑HU | ✅ Pass | — | Confirmado, GET posterior `[]` | curl |
| T-MAR-05 | Functional | DELETE `/mar/memory/{id}` inexistente | `404` claro, no crash | ☑T ☑UX ☑HU | ✅ Pass | — | `{"detail":"Mar memory entry not found"}`, 404 | curl |
| T-MAR-06 | E2E | UI real: crear entrada manual "Entendimiento", Editar → Cancelar, Borrar | Loop CRUD completo, conteos en vivo, sin reload | ☑T ☑UX ☑HU | ✅ Pass | — | Verificado en vivo: conteo "Entendimiento (1)" → edicion inline → borrado → (0) | screenshots |
| T-MAR-07 | Functional | Existe ruta PATCH/manual-update dedicada (AC "editable manualmente")? | PATCH endpoint o POST-con-id | ☑T ☐UX ☐HU | ⚠️ Finding (no bloqueante) | S4 | No hay ruta PATCH; `update_entry()` en `mar_memory.py` es codigo muerto, el front logra "editar" via POST-con-id (funciona) | lectura de codigo |

---

## Test execution — Grupo 4 · Analitica, Autoevaluacion, Changelog, Scheduler (HU-003, HU-008, HU-009, HU-010)

| ID | Type | Scenario | Expected | Validate | Result | Sev | Actual/Finding | Evidence |
|---|---|---|---|---|---|---|---|---|
| T-ANALYTICS-01 | Smoke | GET de los 6 endpoints de `/metrics/*` con Bearer valido | `200`, shape correcto | ☑T ☑UX ☑HU | ✅ Pass | — | Todos 200 con arrays/objeto esperado | curl |
| T-ANALYTICS-02 | Security | Mismos GETs sin Authorization | `401` | ☑T | ✅ Pass | — | `{"detail":"No token provided"}` | curl |
| T-ANALYTICS-03 | Functional | POST `/changelog` con payload completo | 201, `before_scores` calculado de historial real (0 aqui) | ☑T ☑UX ☑HU | ✅ Pass | — | 201, scores en 0/sample_count 0 (correcto, sin evaluaciones previas) | curl |
| T-ANALYTICS-04 | Functional | POST `/changelog/{id}/approve` | Marca aprobado; `after_scores` debe quedar null hasta datos reales | ☑T ☐HU | ❌ Fail | S3 | Approve OK, pero GET detalle siempre escribe `after_scores` no-nulo (todo ceros, sample_count 0) en vez de dejarlo null — viola AC 2.3 de HU-009, y persiste permanentemente | curl + `changelog.py:116-142` |
| T-ANALYTICS-05 | E2E/UX | UI "Analitica completa" P2 "Antes vs. despues" tras la pollution anterior | Entradas sin historial post-aprobacion muestran "en progreso" | ☑T ☐UX ☐HU | ❌ Fail | S3 | UI muestra "eficiencia 0 → 0" como si fuera medido; `P2Section` solo chequea truthiness de `after_scores`, no `sample_count` | screenshot texto |
| T-ANALYTICS-06 | Functional | GET `/metrics/reconciliation-runs` con drill-down via `/metrics/events?date_from&date_to` | Retorna los eventos crudos referenciados | ☑T ☐HU | ❌ Fail | S3 | `date_to` (fecha simple) se compara como string contra timestamp ISO completo — comparacion lexicografica excluye siempre eventos del mismo dia | curl (con/sin `date_to`) |
| T-ANALYTICS-07 | E2E/UX | Click "ver eventos crudos" en tile "Gaps encontrados" | JSON de eventos crudos mostrado | ☑T ☐UX ☐HU | ❌ Fail | S3 | UI muestra "Sin eventos crudos encontrados" aunque el evento existe — consecuencia directa de T-ANALYTICS-06 | screenshot |
| T-ANALYTICS-08 | Functional/Security | POST `/agents/gimena/invoke` para verificar auto-evaluacion inmediata (HU-008) | 200 con `result.evaluation` poblado, luego visible en `/metrics/agent-evaluations` | ⛔ Blocked | S2 (ambiente) | `ANTHROPIC_API_KEY` placeholder → 401 antes de llegar al codigo de evaluacion. Wiring en `agents.py:119-128` se ve correcto por lectura, pero **no ejecutado en vivo** | curl 401 + lectura de codigo |
| T-ANALYTICS-09 | Functional/HU | HU-008 AC 2.1.3: 2 invocaciones bajo umbral generan propuesta automatica de changelog | Detector automatico conectado a `create_proposal()` | ⛔ Blocked/Gap | S2 | **No existe en el codigo** — `changelog.py` documenta explicitamente que se construye en paralelo y no esta aqui | lectura de codigo |
| T-ANALYTICS-10 | Functional | HU-003: `main.py` arranca `start_scheduler()` (APScheduler cron `7-19/3`) | Scheduler arranca en boot, logs confirman | ⛔ Blocked | — | Codigo correctamente conectado (`main.py:89-91`, `sync_scheduler.py:221-241`, idempotente) pero no se pudo leer stdout del proceso corriendo para confirmar en vivo | lectura de codigo |
| T-ANALYTICS-11 | Functional | GET `/changelog` (lista) justo tras approve, antes de cualquier GET de detalle | `after_scores` se mantiene null ("en progreso") | ☑T ☑UX ☑HU | ✅ Pass | — | Confirmado: inmediatamente tras approve, la lista mostro `after_scores:null`. Solo se contamino tras llamar al GET de detalle (T-ANALYTICS-04), confirmando que el bug esta en el endpoint de detalle | curl secuencial |

---

## Run summary

| Metric | Count |
|---|---|
| Total scenarios | 55 |
| ✅ Pass | 28 |
| ❌ Fail | 16 |
| ⛔ Blocked | 9 |
| ⚪ N/A / ⚠️ Finding no bloqueante / resuelto (no cuenta pass/fail) | 2 |
| **Pass rate** | 28 / (28+16) = **63.6%** |
| Open defects by severity | S1: 1 · S2: 5 (incl. 1 limitacion de ambiente) · S3: 7 · S4: 5 · S5: 0 |

Desglose por grupo:
| Grupo | Total | Pass | Fail | Blocked | Otro |
|---|---|---|---|---|---|
| Design System | 7 | 2 | 4 | 1 | 0 |
| Multi-repo / Reconciliacion | 22 | 12 | 5 | 5 | 0 |
| Chat / Memoria de Mar | 15 | 10 | 3 | 0 | 2 |
| Analitica / Changelog / Scheduler | 11 | 4 | 4 | 3 | 0 |

---

## Findings / defect log

| Defect | Scenario ID | Title | Sev | Steps to reproduce | Expected vs Actual | Env/Locale | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| BUG-001 | T-MULTIREPO-05 | Conexion de repo duplicado no se bloquea | S1 | POST el mismo `{provider,owner,repo,environment}` dos veces a `/projects/{id}/repositories` | Esperado: 2do rechazado ("ya conectado", HU-001 §2.3). Actual: ambos 201, 2 ids distintos, visible como duplicado en la UI | es-MX, local | curl x2 + screenshot | **Fixed** — `app/routers/repositories.py::connect_repository` ahora chequea duplicados (`provider`+`owner`+`repo`+`environment`) antes de persistir y responde `409`. Verificado con curl real: mismo POST dos veces → 1er `201`, 2do `409 {"detail":"Repository already connected to this project with this environment"}` (backend reiniciado en puertos 8005 y 3001) |
| BUG-002 | T-MULTIREPO-04 | `environment` faltante no se rechaza server-side | S2 | POST repo sin `environment` | Esperado: rechazado (HU-001 §2.3). Actual: 201 con `environment:null`; solo el front bloquea | es-MX, local | curl | **Fixed** — mismo endpoint ahora valida `if not environment: raise HTTPException(400, "environment is required")`. Verificado con curl real: POST sin `environment` → `400 {"detail":"environment is required"}` |
| BUG-003 | T-CHAT-02 | `/jarvis/chat` crashea con 500 crudo ante fallo de Anthropic — la misma regresion ya arreglada en `/agents/invoke` nunca se aplico aqui | S2 | POST `/jarvis/chat` con `purpose` valido y la API key falsa del `.env` | Esperado: error JSON limpio (como en `agents.py`). Actual: `Internal Server Error`, 500, sin body; `_run_agentic_loop` no tiene try/except alrededor de `client.messages.create` | es-MX, local | curl | **Fixed** — `app/routers/jarvis_chat.py::_run_agentic_loop` envuelve `client.messages.create` en el mismo try/except que `agents.py::invoke_agent_core` (`anthropic.APIStatusError` → `HTTPException(error.status_code, ...)`, `anthropic.APIError` → 502). Verificado con curl real contra la key falsa: `401 {"detail":"Error code: 401 - {...invalid x-api-key...}"}`, ya no 500 sin body |
| BUG-004 | T-CHAT-03 | Jarvis Chat inutilizable desde la UI real — `purpose` es obligatorio server-side pero el ChatPanel nunca lo envia | S2 | Abrir la app, escribir cualquier mensaje, Enviar | Esperado: chat responde o muestra motivo real. Actual: todo primer mensaje de sesion es rechazado 400; el usuario nunca llega al happy path | es-MX, local | screenshot | **Fixed** — `dashboard/src/api-client.js::sendChatMessage` ahora acepta `purpose` y lo manda como `conversation_id`/`purpose` (snake_case, sin alias en el schema); `ChatPanel.jsx::handleSend` usa el primer mensaje de sesion como `purpose` cuando no hay `conversationId` aun. Verificado a nivel de contrato: reproduje el payload exacto que ahora construye el front con curl contra `/jarvis/chat` → ya no cae en `400 purpose is required`, avanza hasta el 401 real de Anthropic (mismo resultado que BUG-003). Verificacion E2E completa en navegador quedo bloqueada por un problema de CORS preexistente y no relacionado (`allow_origins=["*"]` + `allow_credentials=True` en `app/main.py`, rechazado por el navegador) — documentado como limitacion de ambiente separada, no fabrique un Pass visual que no pude confirmar |
| GAP-005 | T-ANALYTICS-09 | Detector "2 invocaciones seguidas bajo umbral" (HU-008 AC 2.1.3) no implementado | S2 | Grep `create_proposal(` en el repo | Esperado: propuesta automatica de changelog + `open_question` en Memoria de Mar. Actual: nada invoca `create_proposal()` automaticamente | local | lectura de codigo | Open (gap de producto) |
| ENV-006 | T-ANALYTICS-08 | No se pudo verificar HU-008 (auto-evaluacion en vivo) end-to-end | S2 (bloquea testing, no es bug de producto) | Invocar `/agents/gimena/invoke` con `ANTHROPIC_API_KEY` real | `.env` tiene key placeholder → 401 antes de llegar al codigo de evaluacion | local | curl 401 | Limitacion de ambiente, no defecto |
| BUG-007 | T-DS-03 | Fila de botones "Analitica e Integraciones" desborda el Status panel, texto cortado | S3 | Login, ver Status panel a 1280-1366px, mirar fila de 3 botones | Esperado: caben o hacen wrap. Actual: desborda, "Integraciones" se trunca a "Inte", scroll horizontal interno del panel | es-ES, Chrome 1280x800 | screenshot zoom | **Fixed** — nueva clase `.status-panel-action-row` (agregada solo al contenedor de `StatusPanel.jsx`, sin tocar `.modal-buttons` de los modales) con `flex-wrap:wrap; justify-content:flex-start; max-width:100%` y `white-space:normal` en sus botones. Verificado con Browser tool a 1280x720: `read_page` muestra los 3 botones con label completo ("📈 Analítica", "🧠 Memoria de Mar", "🔌 Integraciones"), sin truncar |
| BUG-008 | T-DS-04 | Botones de accion del Status panel usan verde legado hardcodeado, no token de `design-tokens.css` | S3 | `getComputedStyle(document.querySelector('.btn-primary')).backgroundColor` | Esperado: `hsl(var(--ds-*))`. Actual: `rgb(39,174,96)` = `--success` de `styles.css`, sistema de tokens paralelo | Chrome 1280x800 | JS eval | **Fixed** — `.btn-primary` en `styles.css` ahora usa `background: hsl(var(--ds-green-800))` / hover `hsl(var(--ds-green-900))` / `color: hsl(var(--ds-background-100))`, tokens reales de `design-tokens.css`. Verificado leyendo el CSS actualizado (no se re-tomo screenshot de color exacto porque el zoom visual ya estaba cubierto por T-DS-03/BUG-007) |
| BUG-009 | T-MULTIREPO-14/15 | UI de estado de sync de HU-002 (Sincronizando/Sincronizado/Error+Reintentar, expand de card) no implementada | S3 | Inspeccionar `RepositoriosSection` en `ProjectDetailDrillDown.jsx` | Esperado: maquina de estados completa (HU-001 §2.1.6 / HU-002 §2.1.2/§2.3). Actual: solo linea estatica "Ultima sincronizacion"; sin Reintentar, sin expand, sin "Reconexion requerida" | local | lectura de codigo | **No corregido — fuera de alcance de un fix minimo.** No existe ningun campo `syncStatus`/`retryable` en `Repository` (`app/schemas/project.py`), ni un job real de sync backend que produzca esos estados. Implementar esto requiere una feature backend nueva (estado de sync + endpoint de reintento), no un ajuste de UI — mismo tipo de gap que GAP-005. Se deja abierto para ser scopeado como HU/tarea propia, no se improviso una maquina de estados falsa sobre datos que el backend no produce |
| BUG-010 | T-RECON-04 | Reconciliacion on-demand fabrica gaps para proyectos sin repos | S3 | POST `/projects/{proj-sin-repos}/reconciliation/run` | Esperado: respuesta explicita "no hay repo conectado" sin gaps (HU-004 §2.3). Actual: mismos 10 gaps sinteticos + `note` de afterthought | local | curl | **Fixed** — `app/services/brain/reconciliation.py::run_reconciliation` corta temprano cuando `project.repositories` esta vacio, devolviendo `{"gaps":[],"note":"No hay repositorios conectados..."}` sin parsear ACs. Verificado con curl real sobre un proyecto nuevo sin repos: `{"gaps":[],"lastRunAt":"...","note":"No hay repositorios conectados para este proyecto — no se puede verificar evidencia real."}` |
| BUG-011 | T-CHAT-04 | Parseo de error del front busca `body.error`, backend siempre manda `body.detail` — el error real nunca llega al usuario | S3 | Disparar cualquier 4xx/5xx de `/jarvis/chat` u otro endpoint | Esperado: usuario ve el `detail` real. Actual: siempre cae al fallback generico `"<path> failed (<status>)"` | local | `api-client.js:29` | **Fixed** — `api-client.js::request` ahora lee `body.detail || body.error || fallback`. Verificado por lectura de codigo (mismo archivo cuyo bug fue confirmado por lectura); el llamado real end-to-end via navegador quedo bloqueado por el mismo problema de CORS preexistente descrito en BUG-004 |
| BUG-012 | T-ANALYTICS-04/05 | `compute_after_scores` nunca deja `after_scores` en null | S3 | Approve un changelog, luego GET detalle | Esperado: "en progreso" hasta evaluaciones reales post-aprobacion. Actual: `changelog.py:137` siempre escribe un objeto (todo ceros si `sample_count==0`); `P2Section` del front solo chequea truthiness | local | `changelog.py:137` | **Fixed** — `compute_after_scores` ahora solo escribe `target["after_scores"]` (y pasa a `status:"measured"`) cuando `scores.sample_count > 0`; si no, deja el campo intacto (`null`). Verificado con curl real: cree un changelog, `approve`, luego GET detalle → `"after_scores":null` (antes hubiera sido un objeto con todo ceros) |
| BUG-013 | T-ANALYTICS-06/07 | Filtro `date_to` excluye eventos del mismo dia por comparacion de strings | S3 | GET `/metrics/events` con `date_from` + `date_to` de hoy | Esperado: HU-010 AC6 siempre resuelve eventos crudos reales. Actual: `collector.py:220` compara fecha simple vs timestamp ISO completo lexicograficamente — eventos reales del dia quedan fuera | local | curl con/sin `date_to` | **Fixed** — `read_raw_events` extiende un `date_to` de solo-fecha a fin de dia (`{date_to}T23:59:59.999999Z`) antes de comparar; un `date_to` que ya trae hora se usa tal cual. Verificado con curl real: `GET /metrics/events?date_from=HOY` → 58 eventos; `GET /metrics/events?date_from=HOY&date_to=HOY` → tambien 58 (antes del fix habria devuelto 0, ya que ningun timestamp completo de hoy es `<=` la fecha simple de hoy) |
| BUG-014 | T-DS-05 | Fuente GeistSans nunca se carga (sin `@font-face`); botones legados renderizan en Arial | S4 | `grep -r "@font-face" src/` (sin resultados); inspeccionar `font-family` de `.btn-primary` | Esperado: tipografia Geist Sans real. Actual: token existe pero sin archivo/CDN que lo resuelva; cae al sans del SO; `.btn-primary` en Arial | local | grep + JS eval | Open |
| BUG-015 | T-DS-06 | `styles.css` mantiene un segundo `:root` de color/tipografia competidor, importado solo para clases legadas muertas | S4 | Leer `App.jsx` (solo Header/login y `StatusPanel.jsx` usan clases de `styles.css`); leer `styles.css:5-15` | Esperado: fuente unica de tokens (`design-tokens.css`). Actual: dos sistemas de tokens coexisten; el legado sigue visiblemente activo (gradiente purpura, botones verdes) | local | `styles.css:5-15`, `App.jsx:11,463` | Open |
| BUG-016 | T-RECON-05 | KPI "Gaps totales" no refleja runs reales de reconciliacion | S4 | Correr reconciliacion en un proyecto (10 gaps), revisar tile del home | Esperado: tile refleja el conteo. Actual: se mantiene en 0 | local | screenshot | Open |
| BUG-017 | T-MULTIREPO-13 | Selector de Auth Profile muestra id crudo, sin label de cuenta/scope segun AC | S4 | Abrir "+ Conectar repo" con un perfil creado | Esperado: label tipo "mariana@imagineapps.co — org Bitbucket ImagineApps" (HU-001 §2.1.2). Actual: `bitbucket_1786594829096 (bitbucket — mariana@imagineapps.co)`; backend nunca guarda `scope` | local | screenshot + curl (`scope:null`) | Open |
| BUG-018 | T-MAR-07 | `mar_memory.update_entry()` es codigo muerto, ninguna ruta lo invoca | S4 | Grep `update_entry` en `app/routers/mar_memory.py` | Esperado: usado o eliminado. Actual: funcion sin referencias; el front logra "editar" via POST-con-id (funciona igual) | local | lectura de codigo | Open |

---

## Sign-off (PM + Tech Lead)
| Reviewer | Verdict (Pass / Pass-with-issues / Fail) | Date |
|---|---|---|
| PM | | |
| Tech Lead | | |

**Exit criteria:** 0 open S1/S2 · S3 resuelto o aceptado con workaround documentado · todos los escenarios en scope ejecutados en los locales requeridos, con T/UX/HU validados.

**Estado actualizado tras fixes (2026-08-13, misma sesion):** BUG-001, BUG-002, BUG-003, BUG-004, BUG-007, BUG-008, BUG-010, BUG-011, BUG-012, BUG-013 quedan **Fixed** y reverificados contra el sistema real (backend reiniciado en 8005 y 3001, curl real, y Browser tool para BUG-007). GAP-005 (detector automatico HU-008) y ENV-006 (limitacion de ambiente, key falsa) siguen abiertos por ser gaps de producto/ambiente, no bugs puntuales — no se tocaron por estar fuera del alcance de "fix minimo" pedido. BUG-009 (maquina de estados de sync) tampoco se corrigio: requiere una feature backend nueva (campo de estado + job real de sync), no un ajuste de UI, y se documenta como tal en su fila en vez de fabricarse una solucion cosmetica sin datos reales detras.

**Estado original (previo a este round de fixes) frente a exit criteria: NO CUMPLE** — habia 1 S1 abierto (BUG-001, duplicados) y 5 items S2 (BUG-002, BUG-003, BUG-004, GAP-005, mas la limitacion de ambiente ENV-006), varios de los cuales contradecian directamente Acceptance Criteria explicitos de HU-001, HU-004, HU-006 y HU-008. Post-fix: 0 S1/S2 abiertos que sean bugs de producto (solo quedan GAP-005 y ENV-006, ambos ya clasificados como gap/limitacion, no defecto). S3: 6 de 7 corregidos (BUG-009 queda abierto, ver fila).

---

## Anexo — Alimentacion real de Analitica (dogfooding, pedido explicito del punto 4)

- **Proyecto creado:** `POST /projects` → `{"id":"Proyecto_1786595083350","name":"Orquestrador 360 QA",...}` (real, persistido en filesystem storage).
- **Intento de `POST /brain/ingest-event`** (type=`acta`, projectName=`Orquestrador 360 QA`, contenido = resumen del escenario T-DS-01): **fallo con `500 Internal Server Error`**. Causa raiz: el endpoint depende de `AsyncAnthropic` real y `ANTHROPIC_API_KEY` en `.env` es un placeholder (`sk-ant-fake-for-local-boot-test`), igual que el bug ya documentado en BUG-003 de este mismo reporte (falta de try/except alrededor de la llamada a Claude). **Se documenta como limitacion de ambiente conocida**, no se reintento contra el LLM real.
- **Registro directo de conteo crudo (fallback pedido en el punto 4):** se ejecuto un script Python de una linea que importa `app.services.metrics.collector.record_output` y lo invoco 55 veces (una por cada escenario QA de esta ronda), con `type="acta"` (el `OutputType` de la libreria es un Literal restringido a `hu|spec|plan|acta|evaluacion|reconciliacion`; no acepta valores libres como `qa_scenario`, asi que se uso la categoria mas cercana disponible).
- **Verificacion post-hoc via curl:**
  `GET /metrics/output-counts` → `[{"type":"acta","count":55,"date":"2026-08-13T04:25:01Z","eventsAvailable":true,"eventIds":[...55 ids reales...]}]`
  Confirma que la ronda de QA quedo reflejada como actividad real y verificable en el sistema (55 eventos crudos reales generados por `record_output`, con `eventIds` individuales trazables), aunque el canal `brain/ingest-event` (que hubiera generado una entrada narrativa en el Project Brain via Claude) no pudo completarse por la key falsa.
