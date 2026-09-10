# Flujo de QA real — Orquestrador 360 / Mar en internet

Documento para que cualquier persona del equipo pueda reproducir el esquema de QA y correr las
pruebas exactamente como se corren en este proyecto — nada acá es aspiracional, todo referencia
código y endpoints reales que ya existen.

Fuente de verdad complementaria: [`ia-hybrid-teams/spec-kit/PHASE_CONTRACTS.md`](../../../mini%20me/ia-hybrid-teams/spec-kit/PHASE_CONTRACTS.md)
§Fase 4, y [`SPEC_JARVIS.md`](../SPEC_JARVIS.md) §14–§16.

> **2026-09-02**: se integró el esquema de QA V2 de Finanz Butik (conclusión dual, gate de cierre,
> pipeline test-design → runs → corrections → evidence). Ver [`README-QA-SCHEME.md`](README-QA-SCHEME.md)
> y [`QA-EXECUTION-TEMPLATE.md`](QA-EXECUTION-TEMPLATE.md) — esto es la ejecución **manual**/humana,
> complementaria (no un reemplazo) del `qa-sweep` automatizado descrito abajo.

---

## 1. Los agentes de QA reales

| Agente (id corto) | Nombre / rol | Qué hace |
|---|---|---|
| `moni` | QA Integrator | Validación automatizada de APIs — contratos, seguridad, performance. |
| `rena` | Integration | Evidencia real de integración UI ↔ API (unit tests de servicios + plan E2E). |
| `sara` | Sonar Quality Gate | Análisis tipo Sonar — calidad, seguridad, duplicación, cobertura. |
| `xime` | Unit Test Standards Reviewer | Verifica estándares de unit tests: naming, aislamiento, aserciones. |
| `tami` | MCP Integration Tester | Tests end-to-end vía MCP — escenarios cross-módulo. |
| `vane` | Test Video Recorder | Captura evidencia visual (video/screenshots) de las ejecuciones. |
| `pau` | Quality Report Generator | Consolida todo lo anterior en un reporte go/no-go. |
| `vale` | Auditor (reconciliación) | Compara claims de "hecho" contra evidencia real en el código conectado. |

Cada uno tiene su especificación completa en `ia-hybrid-teams/agents/{nombre-real}.md` (ej.
`agents/qa-integrator.md` para `moni`) — ahí está su contrato de output exacto, no solo el
resumen de esta tabla.

---

## 2. Las 3 capas — con su disparo real, nunca "correr todo siempre"

### Capa 1 — Código completo (gate previo, fuera de Jarvis)

No son agentes de este repo — son 5 meta-agentes reales de **Claude Code**
([github.com/darcyegb/ClaudeCodeAgents](https://github.com/darcyegb/ClaudeCodeAgents)):

1. **Jenny** — verifica que el código implementado coincide con la especificación.
2. **Karen** — evalúa el estado real de completitud, sin optimismo.
3. **Task Completion Validator** — confirma que lo "completado" funciona de punta a punta.
4. **Claude MD Compliance Checker** — verifica cumplimiento de las guías del proyecto.
5. **Code Quality Pragmatist** — detecta sobre-ingeniería y complejidad innecesaria.

**Disparo**: cada PR/commit, antes de pasar a la Capa 2. Es un gate documental/de proceso — no
hay endpoint de runtime que lo dispare, se sigue como práctica del equipo.

### Capa 2 — Funcionales (esta fase, agentes reales de Jarvis)

Lo más básico: ¿el flujo completo funciona de punta a punta según sus propios criterios?

**Disparo (cualquiera de estos):**
- A demanda (ver §3 abajo).
- Cuando un Milestone tiene todas sus tareas mergeadas.
- Cuando una HU está completa y mergeada.

> Nota real: el disparo automático por "Milestone/HU mergeada" todavía no está implementado —
> requiere definir ese evento en el schema. Hoy Capa 2 solo corre a demanda.

### Capa 3 — Integración (solo a demanda, nunca automática)

Extiende a `tami` (MCP) + `vane` (video) con 4 verificaciones reales:

- Validación de campos (tipo, requerido/opcional, longitud, formato — contra el contrato real).
- Pixel-perfect (comparación real contra el diseño aprobado).
- Flujos alternos (cancelaciones, timeouts, reintentos, errores — no solo el camino feliz).
- Prueba de carga (al menos un escenario con volumen real).

Es la capa más costosa de correr — nunca se dispara sola.

---

## 3. Cómo correr la Capa 2 de verdad — `POST /projects/{id}/qa-sweep`

Este es el comando real que encadena `moni → rena → sara/xime → vale (reconciliación) → pau` en
un solo llamado — reemplaza invocar los 6 agentes uno por uno a mano.

```bash
curl -X POST "https://backmar-in-theinternet.vercel.app/projects/{PROJECT_ID}/qa-sweep" \
  -H "Authorization: Bearer {APP_API_KEY}"
```

- `{PROJECT_ID}` — el id real del proyecto (ej. `Proyecto_1786721589586`).
- `{APP_API_KEY}` — una key real de `APP_API_KEYS` (Vercel → env vars).

**Tiempo esperado**: 3–5 minutos. Son 5 llamadas reales a Claude en secuencia, cada una con su
propio juez de acertividad (evaluación HU-008) — no es un bug si tarda, es el costo real de
invocar 5 agentes uno tras otro.

### Forma de la respuesta

```json
{
  "projectId": "...",
  "steps": {
    "moni": { "output": "..." },
    "rena": { "output": "..." },
    "sara": { "output": "..." },
    "xime": { "output": "..." }
  },
  "reconciliation": { "lastRunAt": "...", "gaps": [...] },
  "report": "... reporte markdown de Pau ..."
}
```

Si un agente falla, su entrada en `steps` es `{"error": "..."}` en vez de `{"output": "..."}` —
el sweep sigue con los demás y Pau consolida con lo que sí haya salido real. **Nunca se fabrica
un "todo pasó"** — si un proyecto no tiene repos conectados, la reconciliación devuelve `0 gaps`
con una nota explícita, y el reporte de Pau marca las secciones sin evidencia como
`🟡 SIN DATOS`/`🟡 PARCIAL`, no como aprobadas.

### Corrida real de referencia (2026-08-21, Finanz Butik)

```
HTTP 200 en 311.8s
moni: OK · rena: OK · sara: OK · xime: OK
reconciliation: 0 gaps (proyecto sin repos conectados — nota explícita)
report: Pau generó "🟡 SIN DATOS" en Sonar/Unit Tests, "🟡 PARCIAL" en MCP/Video
```

---

## 4. Reconciliación (`vale`) — qué mide y cómo

Corre dentro del qa-sweep, pero también se puede correr sola:

```bash
curl -X POST "https://backmar-in-theinternet.vercel.app/projects/{PROJECT_ID}/reconciliation/run" \
  -H "Authorization: Bearer {APP_API_KEY}"
```

**Cómo mide de verdad**: parsea los Acceptance Criteria de cada HU conectada y busca en el
código real un comentario `# @ac:HU-XXX-N` (Python) o `// @ac:HU-XXX-N` (JS/TS) que enlace ese AC
con un test real. Sin ese marcador, el AC queda `sin_test` — nunca se reporta "cumple" sin
evidencia encontrada.

Estados posibles por AC: `sin_test`, `con_test_sin_resultado` (hay test, falta CI conectado),
`no_reconciliable` (la HU no tiene una sección de AC parseable), o cerrado.

Cada gap trae `helpText` con la acción exacta para resolverlo (ej. qué marcador agregar y dónde)
— implementado en `app/services/brain/reconciliation.py`'s `_help_text()`.

---

## 5. Capa 1 en la práctica — cómo correrla vos mismo

No hay comando único: son subagentes de Claude Code que se invocan desde una sesión de Claude
Code normal, antes de pedir la Capa 2. Ejemplo real de cómo se usan:

> "Usa el agente Jenny para verificar que este código implementa lo que dice
> [spec.md]; después usa Karen para confirmar que está realmente completo, no solo que compila."

Si alguno de los 3 gates críticos (Jenny, Karen, Task Completion Validator) encuentra un problema
real, se corrige antes de correr `qa-sweep` — correr Capa 2 sobre código que Capa 1 ya sabe que
está incompleto es desperdiciar 3-5 minutos de llamadas reales.

---

## 6. Referencias de código real (para quien quiera modificar esto)

| Qué | Archivo |
|---|---|
| Endpoint `qa-sweep` | `app/routers/agents.py` — `run_qa_sweep` |
| Reconciliación + `helpText` | `app/services/brain/reconciliation.py` |
| Registry de agentes (ids, tiers, prompts) | `app/services/agent_registry.py` |
| Specs completas por agente | `ia-hybrid-teams/agents/*.md` |
| Contratos de fase (incluye estas 3 capas) | `ia-hybrid-teams/spec-kit/PHASE_CONTRACTS.md` §Fase 4 |
| Extensión Capa 3 (4 verificaciones) | `ia-hybrid-teams/agents/mcp-integration-tester.md`, `agents/test-video-recorder.md` |
