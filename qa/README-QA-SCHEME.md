# Esquema de QA V2 — integrado desde Finanz Butik (2026-09-02)

Adopción real del esquema de QA V2 de Finanz Butik
(`Clientes/Finanz Butik/fb-dev/v2/planning-fb/04-QA/V2/`) dentro del flujo de QA de Minime — ver
[`QA_FLOW_README.md`](QA_FLOW_README.md) para los agentes reales (Moni, Rena, Sara, Xime, Tami,
Vane, Pau, Vale) y las 3 capas (código completo / funcionales / integración).

## Qué cambia con esta integración

Antes de esta ronda, Minime tenía **un** template de ejecución manual (`QA-EXECUTION-TEMPLATE.md`,
2026-08-13) con un solo pass-rate. El esquema V2 de Finanz Butik agrega 3 cosas reales que faltaban:

1. **Conclusión dual** — Functional % y Non-Functional % se scorean por separado, nunca mezclados
   en un solo número. Un feature puede funcionar perfecto (Functional 100%) y tener el copy roto
   (Non-Functional 60%) — antes esto se perdía en un promedio.
2. **Gate de cierre mecánico** — `APPROVED` solo si ambos bloqueantes (S1+S2) son 0 en ambos lados.
   Sin discreción humana sobre si "está bien así".
3. **Pipeline con 4 tipos de archivo relacionados** (no solo un doc de ejecución suelto):

| Carpeta | Tipo de archivo | Nombrado | Qué es |
|---|---|---|---|
| [`test-design/`](test-design/) | Diseño de test | `<feature>-tests.md` | El diseño reusable y **en blanco** por feature/HU (criterios, mapa de nav, template de scoring). |
| [`runs/`](runs/) | Test ejecutado | `QA_RUN_###.#-<feature>.md` | Un diseño **lleno con resultados** de una corrida. `###` = id consecutivo, `.#` = iteración. |
| [`corrections/`](corrections/) | Correcciones (dev) | `QA_RUN_###.#-<feature>-Correcciones.md` | Lista de correcciones para dev extraída de esa corrida — existe siempre, incluso con 0 hallazgos. |
| [`evidence/`](evidence/) | Evidencia | — | Fotos/video/logs de reproducción por hallazgo. |
| [`human-test-cases/`](human-test-cases/) | Casos humanos/UAT | `<feature>-cases.md` | Casos estilo HU para testers no técnicos — pasos de usuario simples, sin endpoints. |

**Flujo:** `test-design/` (en blanco) → correr → `runs/` (lleno) + `corrections/` (fixes) →
relacionado en un índice tipo `TEST-REPORT.md` (crear cuando haya ≥3 corridas reales).

## Regla de red-flag (adoptada tal cual)

Una iteración (`.#`) **no debe superar 3**. Cuando llega a `.#` ≥ 3 en el mismo `RUN_###`, se marca
como red flag real y se escala — no se sigue reintentando en silencio.

## Las 2 capas de revisión (adoptadas tal cual)

Todo run **no está completo hasta que ambas capas** estén hechas:

- **Capa Código (static)** — leer el código real contra cada criterio (endpoints, contratos, i18n,
  autorización, validación). En Minime, esto lo cubren **Capa 1** (Jenny/Karen/Task Completion
  Validator) + **Vale** (reconciliación código↔spec). Tag: `(code review <fecha>)`.
- **Capa Usuario (UI, vía browser)** — ejercitar la app corriendo en el navegador: flujos reales,
  estados, i18n en pantalla, captura de evidencia. En Minime, esto lo cubren **Tami** (MCP) +
  **Vane** (video) en **Capa 3**, o un tester humano llenando `QA-EXECUTION-TEMPLATE.md` a mano.
  Tag: `(user test <fecha>)`.

## Mapeo completo: esquema V2 ↔ agentes reales de Minime

| Pieza del esquema V2 | Equivalente real en Minime |
|---|---|
| Test design (criterios en blanco) | `qa/test-design/*.md`, escrito a mano o por `moni`/`rena` como insumo |
| Ejecución automatizada | `POST /projects/{id}/qa-sweep` (Capa 2: Moni→Rena→Sara/Xime→Vale→Pau) |
| Ejecución manual (Layer 2 / UI) | `QA-EXECUTION-TEMPLATE.md` llenado a mano, o Capa 3 (Tami/Vane) cuando aplica |
| Corrections doc | Se puede generar pidiéndole a `pau` que consolide los ❌ de un run real |
| Reconciliación código↔spec | `vale` — ya existente, con `helpText` real por gap (BUG-019) |
| Evidence | `qa/evidence/` + lo que capture `vane` |
| Red-flag ≥3 iteraciones | Nuevo — agregar como chequeo en el `qa-sweep` si se pide construirlo |

## Qué NO se copió tal cual (y por qué)

- **Los ~530 escenarios manuales de Finanz Butik** — son específicos de ese producto (Salesforce,
  Opportunities, SSP flows). Minime usa la misma **estructura**, no ese contenido.
- **Locales en-US/es-MX/pt-BR** — Minime hoy es un solo locale (es). Se deja la fila `N` (i18n) en
  el template para cuando aplique, sin inventar soporte multi-idioma que no existe.
