# QA Test Execution Template — Orquestrador 360 (Jarvis Mode)

> Reusable template to run the test scenarios and record/flag findings. One **execution doc per milestone** (steps inside), built from the project's test plans. Adapted from Finanz Butik's `qa/QA-EXECUTION-TEMPLATE.md` for this repo's HU/AC conventions. Date: 2026-08-13.

## Unidad de Acceptance Criteria (AC) — convencion de este proyecto

Este proyecto reconcilia HUs contra evidencia real (tests, PRs, commits) via
`app/services/brain/reconciliation.py`. Para que QA y el motor de
reconciliacion hablen el mismo idioma sobre "que es un AC", esta plantilla usa
exactamente la misma unidad que el reconciliador parsea de las HUs que produce
Gimena (`src/agents/spec-kit-agents/Gimena-userstorywriter.md` §5, ver ejemplo
real en `outputs/HU_RUN-001_2026-08-12.md`):

- **Unidad de AC = un bullet o una fila de tabla dentro de la seccion "2.
  CRITERIOS DE ACEPTACIÓN"**, no un checkbox (Gimena nunca emite `- [ ]`):
  - **2.1 Interfaz y Experiencia** y **2.2 Casos de Uso y Reglas de Negocio**:
    cada bullet de primer nivel (`1. texto` o `- texto`) es un AC.
  - **2.3 Manejo de Errores**: cada fila de datos de la tabla
    `| Escenario | Mensaje... |` (sin contar encabezado ni fila separadora)
    es un AC.
- **ID de AC:** `{huId}-2.{subseccion}.{indice}`, ej. `HU-004-JarvisMode-2.1.3`
  (3er bullet de §2.1) o `HU-004-JarvisMode-2.3.1` (1ra fila de la tabla de
  §2.3).
- **Enlace test↔AC:** un test real se vincula a un AC con un comentario que
  contenga exactamente ese id: `# @ac:HU-004-JarvisMode-2.1.3` (Python) o
  `// @ac:HU-004-JarvisMode-2.3.1` (JS/TS). El reconciliador busca este patron
  en cualquier archivo bajo una ruta "test-ish" de los repos conectados.

**AC-id (reconciliacion) ≠ ID de escenario QA (`T-XXX-NN`) de esta plantilla:**
son unidades distintas y complementarias.
- El **AC** es la unidad de negocio/reconciliacion: un criterio individual
  extraido literalmente de la HU, usado por `reconciliation.py` para saber si
  existe evidencia real (test enlazado) de que se cumple.
- El **escenario de QA** (`T-XXX-NN`, fila de la tabla "Test execution" mas
  abajo) es la unidad de prueba manual/E2E: un Given/When/Then ejecutado a
  mano, que puede cubrir **uno o varios ACs a la vez** (por ejemplo, un solo
  escenario E2E de "login con MFA" puede satisfacer 3 bullets de 2.2 y 1 fila
  de 2.3).

Por eso, cada fila de la tabla "Test execution" de esta plantilla debe listar
en su columna **Traceability** los AC-ids reales que cubre (ej.
`HU-004-JarvisMode-2.1.1, HU-004-JarvisMode-2.1.2, HU-004-JarvisMode-2.3.1`),
ademas del HU al que pertenece — asi un Pass/Fail manual de QA se puede cruzar
directamente contra el estado (`sin_test` / `con_test_sin_resultado` /
`no_reconciliable`) que `reconciliation.py` calcula para esos mismos AC-ids.

## Como usar
1. Fill the **Run header** for your cycle (build, environment, testers, time, evidence link).
2. Go step by step. For each scenario: perform it, then tick the **3 validation checks** (all must pass), set **Result**, and if it fails write **Actual/Finding**, set **Severity**, attach **Evidence**, and open a **Defect**. In **Traceability**, list the exact AC-id(s) (per the convention above) this scenario covers.
3. Fill the **Run summary**; PM + Tech Lead do the **Sign-off**.
4. Re-run per build → new Run header + fresh tables (keep history).

## Scope
Run manually: **Smoke, Functional, E2E, Security, Accessibility, Performance**. Unit/Integration are dev-automated (reference only) and reconciled automatically via `reconciliation.py` using the `@ac:` link comments.

## The 3 validation checks (every scenario must satisfy all)
- **T — Technical completeness:** behaves per the technical definition (correct endpoint/contract, status codes, data, state machine); no console/network errors.
- **UX — User-facing:** what the user sees and does is correct — copy, states (empty/loading/error), navigation, responsive.
- **HU — HU acceptance:** matches the specific AC-id(s) listed in Traceability (happy path bullets from 2.1/2.2, error-table rows from 2.3).
> A scenario is **Pass** only if Expected matches **and** T + UX + HU are all ticked.

## Legends
- **Result:** ✅ Pass · ❌ Fail · ⛔ Blocked · ⚪ N/A · ⏳ Not run
- **Type:** Smoke · Functional · E2E · S (Security) · A (Accessibility) · P (Performance)
- **Severity:** S1 Blocker · S2 Critical · S3 Major · S4 Minor · S5 Cosmetic

---

## Run header *(fill per cycle)*
| Field | Value |
|---|---|
| Milestone / Steps | `e.g. M1 · 2.1–2.4` |
| Build / Commit | `___` |
| Environment / URL | `local · uvicorn app.main:app --port ___ / vite dashboard ___` |
| **Tester(s)** | `___` |
| **Testing time** | `start–end · total ___` |
| **Evidence link** | `drive/folder with screenshots & recordings ___` |
| Date / Cycle | `YYYY-MM-DD · Cycle #__` |

---

## Test execution — Step `<X.n · name>`
> Traceability: HU(s) `HU-XXX-Name` · AC-id(s) `HU-XXX-Name-2.1.N, HU-XXX-Name-2.3.N, ...`

| ID | Type | Scenario (Given / When / Then) | Expected | AC-id(s) covered | Validate (all pass) | Result | Sev | Actual / Finding | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| `T-…-01` | Smoke | Given … When … Then … | … | `HU-XXX-…-2.1.1` | ☐T ☐UX ☐HU | ⏳ |  |  |  |
| `T-…-02` | Functional | … | … | `HU-XXX-…-2.2.1, HU-XXX-…-2.3.1` | ☐T ☐UX ☐HU | ⏳ |  |  |  |

*(repeat table per step)*

---

## Run summary
| Metric | Count |
|---|---|
| Total scenarios |  |
| ✅ Pass / ❌ Fail / ⛔ Blocked |  |
| ⚪ N/A · ⏳ Not run |  |
| **Pass rate** | `pass / (pass+fail) %` |
| Open defects by severity | S1:_ · S2:_ · S3:_ · S4:_ · S5:_ |
| AC-ids sin cobertura QA manual (cruzar con `gaps[].status` de reconciliation.py) |  |

## Findings / defect log
| Defect | Scenario ID | AC-id(s) | Title | Sev | Steps to reproduce | Expected vs Actual | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| `BUG-001` |  |  |  |  |  |  |  | Open |

## Sign-off (PM + Tech Lead)
| Reviewer | Verdict (Pass / Pass-with-issues / Fail) | Date |
|---|---|---|
| PM |  |  |
| Tech Lead |  |  |

**Exit criteria:** 0 open S1/S2 · S3 resolved or accepted with documented workaround · all in-scope scenarios executed, with T/UX/HU validated · every AC-id in scope is either covered by a Pass scenario here or reflected in `reconciliation.py`'s `gaps[]` as `sin_test`/`con_test_sin_resultado` (never silently unaccounted for).
