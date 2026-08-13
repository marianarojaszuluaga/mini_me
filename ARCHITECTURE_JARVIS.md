# Arquitectura técnica — Jarvis Mode (Python / FastAPI)
> **Status**: Elaboración técnica — documentación de arquitectura, sin código todavía
> **Creado**: Agosto 2026 — **revisado 2026-08-12**: el backend se reescribe completo en
> Python/FastAPI (decisión registrada en `SPEC_JARVIS.md` §8.0). Esta versión reemplaza la
> anterior, que asumía Node/Express.
> **Depende de**: `SPEC_JARVIS.md` (spec aprobado) + `SPEC.md` (arquitectura base de Orquestrador
> 360 — nota de pivote en su cabecera).

---

## 0. Estructura de capas (FastAPI) — dónde vive cada pieza

FastAPI no impone una estructura, pero el patrón de capas explícitas es el que mejor encaja con
lo que ya existía en Node (donde `server.js`/`orchestrator.js` mezclaban rutas + lógica): separar
**routers** (HTTP) de **services** (lógica de negocio) de **adapters** (integraciones externas) de
**schemas** (contratos Pydantic) — cada capa solo conoce la de abajo, nunca al revés.

```
orquestrador-360/
├── app/
│   ├── main.py                     # instancia FastAPI, monta los dos sub-apps (map, orchestrator)
│   ├── core/
│   │   ├── config.py               # settings vía pydantic-settings (reemplaza dotenv+process.env)
│   │   ├── security.py             # dependency de auth (reemplaza middleware/auth.js)
│   │   └── storage.py              # abstracción filesystem/Redis (reemplaza store.js, misma interfaz)
│   │
│   ├── schemas/                    # Pydantic — contratos de entrada/salida de cada endpoint
│   │   ├── project.py              #   Project, Repository, incluye environment (prod/develop)
│   │   ├── chat.py                 #   ChatRequest, ChatTurn, Session
│   │   ├── auth_profile.py
│   │   ├── mar_memory.py
│   │   └── metrics.py
│   │
│   ├── routers/                    # capa HTTP — solo valida input (via schemas) y delega a services
│   │   ├── projects.py             #   /projects, /projects/{id}/repositories
│   │   ├── brain.py                #   /brain/ingest-event, /projects/{id}/reconciliation
│   │   ├── jarvis_chat.py          #   /jarvis/chat
│   │   ├── mar_memory.py           #   /mar/memory
│   │   ├── metrics.py              #   /metrics/agents, /metrics/reconciliation, /metrics/usage
│   │   └── agents.py               #   /agents, /agents/{name}/invoke, /phases, /orchestrate (ya existían, se migran)
│   │
│   ├── services/                   # lógica de negocio real — donde vive el conocimiento del dominio
│   │   ├── repositories/
│   │   │   ├── github_adapter.py   #   implementa la interfaz común (§1.2)
│   │   │   └── bitbucket_adapter.py
│   │   ├── auth_profiles.py        # CRUD de Auth Profiles (§3)
│   │   ├── brain/
│   │   │   ├── ingest.py           # generaliza la lógica de /brain/ingest-acta
│   │   │   └── reconciliation.py   # motor de reconciliación (Auditor, §5)
│   │   ├── jarvis_chat/
│   │   │   ├── session_manager.py  # apertura/cierre/versionado de sesiones (§2.3)
│   │   │   └── tools.py            # las 5 herramientas invocables por Claude en el loop (§2.2)
│   │   ├── mar_memory.py
│   │   ├── metrics/
│   │   │   ├── collector.py        # registra cada evento medible
│   │   │   └── cost_monitor.py     # consulta gasto Vercel/Upstash/Anthropic, dispara alertas
│   │   ├── agent_evaluator.py      # migración de agent-evaluator.js, extendido a 4 dimensiones (§4)
│   │   └── agent_registry.py       # migración de agents/registry.js
│   │
│   ├── phases/
│   │   └── phase_contracts.py      # migración de phaseContracts.js + extensión del modelo ampliado (§6)
│   │
│   └── cron/
│       └── sync_scheduler.py       # dispara Flujo B (sesión + cada 3h 7am-7pm) — APScheduler o Vercel Cron
│
├── src/agents/spec-kit-agents/     # SIN CAMBIO — los 14 .md de ia-hybrid-teams se leen igual
│                                    # (verbatim, sin importar el lenguaje del backend que los carga)
├── adapters/basecamp/              # SIN CAMBIO — el seed de auth/fetch no depende del lenguaje
├── backlog.md / outputs/           # SIN CAMBIO — Gimena sigue generando Markdown, agnóstico al backend
└── dashboard/                      # SIN CAMBIO DE FONDO — React sigue hablando la misma API REST,
                                     # solo cambia el servidor que la sirve
```

**Regla de capas**: `routers/` nunca importa nada de `services/*/adapters` directamente para
lógica — siempre pasa por el `service` correspondiente. Un router no sabe si un repo es GitHub o
Bitbucket; eso lo resuelve `services/repositories/__init__.py` (registry, ver §1.2).

### 0.1 Qué se conserva sin reescribir de lógica (solo cambia el lenguaje que la ejecuta)

- Los **22 prompts de agentes** (`src/agents/spec-kit-agents/*.md` + `external-agents/*.md`) —
  se siguen leyendo verbatim como system prompt, sin importar qué backend los carga.
- **`backlog.md` / `outputs/*.md`** — formato de Gimena, es Markdown plano, agnóstico al backend.
- **Los contratos REST ya definidos** (`GET /agents`, `POST /orchestrate`, etc.) — mismo path,
  mismo verbo, mismo shape de JSON. El frontend React no debería notar la migración salvo por el
  `VITE_API_URL` apuntando al nuevo despliegue.
- **El modelo de datos** (`Project`, `repositories[]`, Project Brain) — mismo shape, ahora
  validado con Pydantic en vez de objetos JS sueltos (una mejora, no un cambio de contrato).

---

## 1. Adaptadores de repositorio

### 1.1 Interfaz común (Python — Protocol, no ABC, para no forzar herencia)

```python
# app/services/repositories/base.py
from typing import Protocol
from datetime import datetime

class RepoAdapter(Protocol):
    async def validate_access(self, auth_profile: AuthProfile, owner: str, repo: str) -> bool: ...
    async def list_commits_since(self, auth_profile: AuthProfile, owner: str, repo: str, since: datetime) -> list[Commit]: ...
    async def list_pull_requests(self, auth_profile: AuthProfile, owner: str, repo: str, state: str) -> list[PullRequest]: ...
    async def get_file_tree(self, auth_profile: AuthProfile, owner: str, repo: str, branch: str) -> list[FileNode]: ...
    async def get_file_content(self, auth_profile: AuthProfile, owner: str, repo: str, path: str, branch: str) -> str: ...
```

### 1.2 Selección de adaptador (registry, mismo patrón que `agent_registry.py`)

```python
# app/services/repositories/__init__.py
from .github_adapter import GitHubAdapter
from .bitbucket_adapter import BitbucketAdapter

_ADAPTERS: dict[str, RepoAdapter] = {
    "github": GitHubAdapter(),
    "bitbucket": BitbucketAdapter(),
}

def get_adapter(provider: str) -> RepoAdapter:
    return _ADAPTERS[provider]
```

Consumido así desde cualquier service (digest, reconciliación, herramienta de chat):
```python
adapter = get_adapter(repo.provider)
commits = await adapter.list_commits_since(auth_profile, repo.owner, repo.repo, since)
```

### 1.3 Librerías

- GitHub: `PyGithub` (wrapper maduro sobre la REST API) o `httpx` async directo si se prefiere no
  añadir una dependencia pesada — a decidir en implementación, no cambia la interfaz.
- Bitbucket: `httpx` async contra la REST API v2.0 — reutiliza los patrones de auth ya probados en
  `adapters/basecamp/AUTH_POC.md`.
- Ambos son **async** de punta a punta — FastAPI + `httpx.AsyncClient` permite que el digest de
  varios repos en paralelo no bloquee el event loop, algo que el Express original no aprovechaba.

---

## 2. Jarvis Chat — arquitectura del loop agéntico

### 2.1 Secuencia de un turno

```
Usuaria escribe en el Panel de Chat
        │
        ▼
POST /jarvis/chat  { conversation_id?: str, message: str }   (schemas/chat.py: ChatRequest)
        │
        ▼
session_manager.py:
  - Si no hay conversation_id → crea sesión nueva, exige `purpose` (HU-006-JarvisMode)
  - Si existe → carga historial de turnos + verifica si se acerca al límite de contexto
        │
        ▼
Cargar contexto: Memoria de Mar completa + lista de proyectos activos (nombre + estado resumido)
        │
        ▼
Llamada async al SDK de Anthropic con tool-calling habilitado (tools.py expone las 5 herramientas)
        │
        ├──> Claude decide llamar 0-N herramientas, en cualquier orden, antes de responder
        │    (loop: await tool_call() → resultado → Claude decide si necesita otra)
        │
        ▼
Respuesta final de Claude (cita fuentes explícitamente, o dice "no lo sé")
        │
        ▼
session_manager.py persiste el turno completo (mensaje, herramientas usadas, resultado, fuentes)
        │
        ▼
Response del endpoint incluye lo necesario para que el frontend refresque el Panel de Estado
en el mismo request/response (sin socket aparte en v1)
```

### 2.2 Las 5 herramientas (`services/jarvis_chat/tools.py`)

Cada una se declara como tool schema para el SDK de Anthropic (formato `input_schema` estándar) y
se resuelve con una función Python async:

| Herramienta | Qué hace | Service que invoca |
|---|---|---|
| `read_project_brain(project_id)` | decisionLog + alerts + meetingLog + reconciliación | `core/storage.py` |
| `read_timeline(project_id, days)` | Eventos crudos recientes | `services/brain/ingest.py` |
| `read_reconciliation(project_id)` | Gaps abiertos/cerrados | `services/brain/reconciliation.py` |
| `invoke_agent(agent_name, input)` | Invoca un agente real | `services/agent_evaluator.py` + `services/agent_registry.py` |
| `write_mar_memory(entry)` | Guarda/actualiza una entrada de Memoria de Mar | `services/mar_memory.py` |

### 2.3 Modelo de sesiones — versionado para no romper la ventana de contexto

```python
# app/schemas/chat.py (Pydantic)
class ChatSession(BaseModel):
    id: str
    purpose: str                      # obligatorio — no hay sesión sin propósito
    project_id: str | None = None
    status: Literal["open", "closed"]
    version: int = 1                  # v2/v3 si se retoma el mismo propósito después
    turns: list[ChatTurn]
    opened_at: datetime
    closed_at: datetime | None = None
```

Al acercarse al límite de contexto (umbral de tokens acumulados, a calibrar con uso real): se
resume el contenido relevante de la versión actual, se marca `status="closed"`, se abre una
versión nueva con el mismo `purpose` y el resumen como primer mensaje — la usuaria no nota el
corte. El historial de sesiones cerradas queda consultable, no se borra.

---

## 3. Auth Profiles — flujo de conexión

```
Usuaria (drill-down Integraciones) → "+ Agregar Auth Profile"
        │
        ▼
Elige provider (GitHub | Bitbucket) → redirige al flujo OAuth de ese provider
        │
        ▼
[Pendiente de investigación, SPEC_JARVIS.md §11]: si la cuenta es @imagineapps.co (SSO Google),
el flujo puede terminar siendo "Continuar con Google" en vez de usuario/contraseña de
GitHub/Bitbucket directamente — a confirmar con una prueba real antes de implementar.
        │
        ▼
Provider redirige de vuelta con un token → FastAPI lo recibe en un callback endpoint
(`routers/auth_profiles.py`, ej. `GET /auth/callback/{provider}`) → se guarda vía
`services/auth_profiles.py`:
  AuthProfile(id, provider, account, scope, token_ref)   # token_ref, nunca el token en claro
        │
        ▼
Ese perfil queda disponible como opción en Flujo A (HU-001-JarvisMode) para cualquier proyecto
```

**Nota de seguridad**: el token real nunca se guarda en el JSON/Redis del store — `token_ref`
apunta a una env var o a un secreto con TTL/rotación (a definir en implementación). Mismo
principio que ya aplica a `access_token_ref` en el modelo de `Project.repositories[]`.

---

## 4. Autoevaluación — wrapper async sobre `agent_evaluator.py`

`services/agent_evaluator.py` (migración de `agent-evaluator.js`) ya calcula la rúbrica ponderada
existente (completeness, clarity, adherence, actionability, alignment). Se envuelve, no se
reemplaza:

```python
# app/services/metrics/evaluate_invocation.py (pseudocódigo)
async def evaluate_invocation(agent_name: str, output: str, context: dict) -> Evaluation:
    calidad = await agent_evaluator.evaluate(agent_name, output, context)   # YA EXISTE (migrado)
    eficiencia = await score_eficiencia(output, context)     # NUEVO — heurística v1
    acertividad = await score_acertividad(output, context)   # NUEVO
    formato = await score_formato(agent_name, output)        # NUEVO — valida contrato esperado
    await collector.record_evaluation(agent_name, calidad, eficiencia, acertividad, formato)
    return Evaluation(calidad=calidad, eficiencia=eficiencia, acertividad=acertividad, formato=formato)
```

Se invoca automáticamente después de cada `invoke_agent` (desde el chat o desde "Invocar Agente"
manual vía `routers/agents.py`) — no es un paso opcional.

---

## 5. Reconciliación — de dónde saca los Acceptance Criteria

```
services/brain/reconciliation.py
    │
    ├─ 1. Lee el/los archivo(s) de HUs del proyecto (backlog.md + outputs/*.md — mismo formato
    │     que Gimena ya usa; este mismo repo es el ejemplo real)
    │
    ├─ 2. Parsea cada checkbox `- [ ]` de Acceptance Criteria como unidad reconciliable
    │     (regex/markdown parser — `markdown-it-py` o `mistune`)
    │
    ├─ 3. Por cada AC, busca un test asociado (convención de vínculo a definir en implementación,
    │     ej. un comentario `# @ac:HU-004-2.2` en el archivo de test)
    │     - si no encuentra ninguno → status "sin test"
    │
    ├─ 4. Si encuentra un test, lee su resultado (última corrida CI, o lo ejecuta) contra el
    │     estado actual del repo (vía RepoAdapter.get_file_content / API de estado de CI)
    │
    └─ 5. Escribe gaps[] a project.memory.projectBrain.reconciliation, dispara alerta si status="gap"
```

Sin test real por AC, nunca se afirma cumplimiento — es "sin test", no "cumple". El valor crece
con el tiempo a medida que se desarrollan tests reales (fase Calidad del modelo de §6).

---

## 6. Fases — cómo `phase_contracts.py` extiende lo existente

`phaseContracts.js` (ahora `phase_contracts.py`) modela 5 fases con `id: 1-5`. El modelo ampliado
de `SPEC_JARVIS.md` §4 no las reemplaza — las envuelve en una jerarquía superior:

```python
# app/phases/phase_contracts.py — extensión, no reemplazo
PROJECT_LIFECYCLE = {
    "iniciacion": {
        "subfases": ["kick_off", "planning"],
        "mapeo_a_fases_existentes": {"planning": 1},   # kick_off es nuevo, sin fase numérica hoy
    },
    "ejecucion": {
        "subfases": ["desarrollo_backend", "desarrollo_frontend", "desarrollo_devops", "calidad", "seguimiento"],
        "mapeo_a_fases_existentes": {"desarrollo_backend": 2, "desarrollo_frontend": 3, "calidad": 4},
        # desarrollo_devops mapea a fase 5 (Deploy) — hoy sin agentes, gap heredado
        # seguimiento es nuevo — lo cubre el propio Jarvis Mode (Brain vivo + reconciliación)
    },
    "cierre": {
        "subfases": ["entregas_parciales", "entregas_finales", "renovacion", "garantia"],
        "mapeo_a_fases_existentes": {},   # gap total (pilar "Delivery" de SPEC_FOLLOWUP.md)
    },
}
```

Los endpoints existentes (`GET /phases`, `POST /orchestrate`, ahora en `routers/agents.py`) siguen
el mismo contrato — esta capa es metadata adicional, no un cambio de shape de respuesta.

---

## 7. Monitoreo de costos

```
services/metrics/cost_monitor.py (job programado, junto al ciclo de sincronización)
    │
    ├─ Vercel: API de uso/facturación del proyecto (token de cuenta de Vercel)
    ├─ Upstash: API de métricas de la base de datos Redis (comandos, almacenamiento)
    └─ Anthropic: costo total de cuenta (el costo por invocación individual ya vive en
       services/metrics/collector.py — esto es el agregado, no el detalle por output)
    │
    ▼
Si algún proveedor sale de free tier o supera un umbral (a definir en implementación) →
alerta por el mismo canal que las alertas del Brain (chat + Panel de Estado)
```

---

## 8. Despliegue — dónde corre FastAPI

Dos rutas posibles, ambas compatibles con la decisión ya tomada de Vercel + Redis Marketplace
(`SPEC_JARVIS.md` §8.2):

- **Vercel (serverless, Python runtime)**: Vercel soporta funciones Python nativamente
  (`api/*.py` con el mismo patrón de rewrites que ya usa el repo hoy para `/map` y
  `/orchestrator`). FastAPI corre envuelto en un handler ASGI compatible con el runtime
  serverless de Vercel (`mangum` o el adaptador nativo de Vercel para ASGI).
- **Host persistente** (si el cron/estado en memoria lo justifica más adelante): `uvicorn` sirviendo
  la app FastAPI directamente, sin adaptador — mismo código, sin cambios.

El cron de sincronización (§2 de `SPEC_JARVIS.md`, sesión + cada 3h 7am-7pm) se implementa con
**Vercel Cron** llamando a un endpoint interno protegido, o con **APScheduler** si se corre en un
host persistente — la lógica de negocio (`sync_scheduler.py`) es la misma en ambos casos, solo
cambia quién la dispara.

---

## 9. Lo que esta elaboración técnica NO decide todavía (correcto dejarlo así)

- Umbral exacto de tokens para versionar una sesión de chat (§2.3) — se calibra con uso real.
- Convención exacta de vínculo test↔AC en `reconciliation.py` (§5) — decisión de implementación.
- Umbral de alerta de costos (§7) — depende del presupuesto mensual que defina Mar.
- Detalle del flujo OAuth de Auth Profiles con SSO de Google (§3) — bloqueado por la
  investigación pendiente ya registrada en `SPEC_JARVIS.md` §11.
- `PyGithub` vs `httpx` directo para el adaptador de GitHub (§1.3) — no cambia la interfaz común,
  se decide al implementar.
- Mangum vs adaptador nativo de Vercel para ASGI (§8) — detalle de despliegue, no de arquitectura.
