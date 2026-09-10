# QA Test Execution Template — Orquestrador 360 (Jarvis Mode)

> Reusable template to run the test scenarios and record/flag findings. One **execution doc per
> milestone/feature** (steps inside), built from the project's test plans. Adapted from Finanz
> Butik's QA scheme — v1 adapted 2026-08-13 (AC-id/reconciliation convention below), **upgraded
> 2026-09-02** to Finanz Butik's V2 format (conclusión dual, gate de cierre, pipeline de
> runs/corrections/evidence) — ver [`README-QA-SCHEME.md`](README-QA-SCHEME.md) para cómo esto se
> integra con las 3 capas de `QA_FLOW_README.md` (Moni, Rena, Sara, Xime, Tami, Vane, Pau, Vale).

## Unidad de Acceptance Criteria (AC) — convención de este proyecto (sin cambios, es lo que nos distingue de Finanz Butik)

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
  en cualquier archivo bajo una ruta "test-ish" de los repos conectados. Cada
  gap ahora también trae `helpText` con la acción exacta (BUG-019, corregido
  2026-08-21).

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

## Cómo usar
1. Llenar el **Run header** del ciclo (build, entorno, testers, tiempo, evidence link).
2. **Enumerar en `qa/runs/` al ejecutar** (`RUN_###.#` — ver §Pipeline abajo).
3. Ir paso por paso. Por cada escenario: ejecutarlo, tildar los **3 checks de validación** (todos
   deben pasar), poner **Result**, y si falla escribir **Actual/Finding**, poner **Severity**,
   adjuntar **Evidence**, y abrir un **Defect**. En **Traceability**, listar los AC-id(s) exactos.
4. Llenar los **2 boxes de Scoring** (Functional / Non-Functional) — separados, no un solo número.
5. Aplicar el **Closure gate** (mecánico, sin discreción).
6. Extraer `qa/corrections/RUN_###.#-Correcciones.md` con cada ❌ — existe siempre, incluso con 0 hallazgos.
7. PM + Tech Lead hacen el **Sign-off**.
8. Re-run por build → nuevo Run header + tablas frescas (mantener historial, `.#` +1 por reintento).

## Scope
Ejecutar manualmente (o vía Capa 3, Tami/Vane): **Smoke, Functional, E2E, Security, Accessibility,
Performance** + no-funcionales (URL, TAB, RSP, N, COPY, DSGN, UX). Unit/Integration son
dev-automatizados (referencia) y se reconcilian automáticamente vía `reconciliation.py` usando los
comentarios `@ac:`.

## Los 3 checks de validación (todo escenario debe cumplir los 3)
- **T — Completitud técnica:** se comporta según la definición técnica (endpoint/contrato correcto,
  status codes, data, máquina de estados); sin errores de consola/red.
- **UX — De cara al usuario:** lo que el usuario ve y hace es correcto — copy, estados
  (vacío/cargando/error), navegación, responsive.
- **HU — Acceptance de la HU:** cumple el/los AC-id(s) listados en Traceability.
> Un escenario es **Pass** solo si Expected coincide **y** T + UX + HU están todos tildados.

## Leyendas
- **Result:** ✅ Pass · ❌ Fail · ⛔ Blocked · ⚪ N/A · ⏳ Not run
- **Type funcional:** Smoke · Functional · E2E · S (Security)
- **Type no-funcional:** URL · TAB · RSP · N (i18n) · COPY · DSGN · UX · A (Accessibility) · P (Performance)
- **Severity → Acción:** S1 Blocker (arreglar ya) · S2 Critical (bloquea release) · S3 Major (este ciclo) · S4 Minor (backlog) · S5 Cosmetic (backlog)

---

## Run header *(llenar por ciclo)*
| Field | Value |
|---|---|
| Feature / HU(s) | `e.g. Tarea 2 Gap 3 · HU-013-JarvisMode` |
| **Cycle / Iter** | `1.1` *(ver TEST-REPORT.md)* |
| Build / Commit | `___` |
| Environment / URL | `local · uvicorn app.main:app --port ___ / vite dashboard ___` |
| Capa 1 (meta-agentes) pasada | Sí ☐ · N/A ☐ |
| Modo de ejecución | Manual ☐ · Auto ☐ (`qa-sweep`) |
| **Tester(s)** | `___` |
| **Testing time** | `start–end · total ___` |
| **Evidence link** | `qa/evidence/___` |
| Date / Cycle | `YYYY-MM-DD · Cycle #__` |

---

## Test execution — Step `<X.n · name>`
> Traceability: HU(s) `HU-XXX-Name` · AC-id(s) `HU-XXX-Name-2.1.N, HU-XXX-Name-2.3.N, ...`

### Consignas funcionales
| ID | Type | Scenario (Given / When / Then) | Expected | AC-id(s) covered | Validate (all pass) | Result | Sev | Actual / Finding | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| `T-…-01` | Smoke | Given … When … Then … | … | `HU-XXX-…-2.1.1` | ☐T ☐UX ☐HU | ⏳ |  |  |  |
| `T-…-02` | Functional | … | … | `HU-XXX-…-2.2.1, HU-XXX-…-2.3.1` | ☐T ☐UX ☐HU | ⏳ |  |  |  |

### Consignas no-funcionales *(mismo formato, Type no-funcional)*
| ID | Type | Scenario | Expected | AC-id(s) covered | Validate | Result | Sev | Actual / Finding | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| `T-…-URL-01` | URL | Given abro la vista, When reviso la barra, Then la URL es exactamente `/<ruta>` | `/<ruta>` | — | ☐T ☐UX | ⏳ |  |  |  |
| `T-…-RSP-01` | RSP | Given cada tamaño (desktop/tablet/mobile), When abro la vista, Then el layout se mantiene sin overflow | sin overflow | — | ☐UX | ⏳ |  |  |  |

*(repetir tablas por paso)*

---

## Scoring — **conclusión dual** *(llenar después de correr — novedad V2, antes era un solo pass-rate)*
> Contar filas: **A** = ✅ · **R** = ❌+⛔ · **N** = A+R (sin contar ⚪ ni ⏳). Los sets son
> disjuntos por Type — Functional cuenta filas Type funcional, Non-Functional cuenta las de Type
> no-funcional. No se mezclan en un solo número.

| Conclusión | N | A (✅) | R (❌+⛔) | **% Aprobación** = A/N×100 | Bloqueantes (S1+S2) |
|---|---|---|---|---|---|
| **Functional** | | | | `__ %` | |
| **Non-Functional** | | | | `__ %` | |
| AC-ids sin cobertura QA manual (cruzar con `gaps[].status` de reconciliation.py) | | | | | |

## Closure gate *(mecánico, sin discreción — novedad V2)*
- ✅ **APPROVED** solo si **Functional bloqueante = 0 Y Non-Functional bloqueante = 0.**
- ❌ Cualquier **S1/S2** en cualquiera de los dos lados → **NOT APPROVED** (arreglar + re-correr).
  S3–S5 → change orders, no bloquean.

| Veredicto | ☐ APPROVED · ☐ NOT APPROVED | Functional %/bloq | `__/__` | Non-Functional %/bloq | `__/__` | Razón | `___` |
|---|---|---|---|---|---|---|---|

## Findings / defect log
| Defect | Scenario ID | AC-id(s) | Title | Sev | Steps to reproduce | Expected vs Actual | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| `BUG-001` |  |  |  |  |  |  |  | Open |

## Suggestions & change orders *(siempre lleno — mayor severidad primero, novedad V2)*
| # | Type | Scenario/AC-id | Change ordered (qué arreglar) | Owner | Priority | Bloquea cierre? |
|---|---|---|---|---|---|---|
| 1 | | | | | S_ | Sí/No |

## Sign-off (PM + Tech Lead)
| Reviewer | Verdict (Pass / Pass-with-issues / Fail) | Date |
|---|---|---|
| PM |  |  |
| Tech Lead |  |  |

**Exit criteria:** `Functional bloqueante = 0` Y `Non-Functional bloqueante = 0` · todos los
escenarios en alcance ejecutados con T/UX/HU validados · cada ❌ tiene un change order · cada AC-id
en alcance está cubierto por un escenario Pass acá o reflejado en `reconciliation.py`'s `gaps[]`
como `sin_test`/`con_test_sin_resultado` (nunca silenciosamente sin contar).
