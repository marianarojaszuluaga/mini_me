# Arquitectura técnica — Jarvis Mode
> **Status**: Elaboración técnica — documentación de arquitectura, sin código todavía
> **Creado**: Agosto 2026
> **Depende de**: `SPEC_JARVIS.md` (spec aprobado) + `SPEC.md` (arquitectura base de Orquestrador 360)
> **Alcance**: cómo se conecta cada pieza nueva a lo que ya existe en `src/` — no reinventa nada,
> extiende siguiendo los mismos patrones (Express, `toolRegistry`, registry de agentes, storage
> intercambiable).

---

## 0. Dónde vive cada pieza nueva (mapa contra `src/` actual)

```
orquestrador-360/
├── src/
│   ├── server.js                  # MAP — YA EXISTE, se le agregan rutas nuevas (§2)
│   ├── orchestrator.js            # Master Orchestrator — YA EXISTE, sin cambios de fondo
│   ├── agent-evaluator.js         # YA EXISTE — se extiende a 4 dimensiones (§4)
│   ├── store.js                   # YA EXISTE — mismo patrón filesystem/Redis, nuevas colecciones
│   ├── middleware/auth.js         # YA EXISTE, sin cambios
│   ├── agents/registry.js         # YA EXISTE, sin cambios de fondo
│   ├── phases/phaseContracts.js   # YA EXISTE — se extiende con el modelo ampliado (§6)
│   │
│   ├── repositories/              # NUEVO
│   │   ├── github-adapter.js      #   implementa la interfaz común (§1.2)
│   │   └── bitbucket-adapter.js   #   implementa la interfaz común (§1.2)
│   ├── auth-profiles/             # NUEVO
│   │   └── profiles.js            #   CRUD de Auth Profiles (§3)
│   ├── brain/
│   │   ├── ingest.js              # NUEVO — generaliza la lógica de /brain/ingest-acta
│   │   └── reconciliation.js      # NUEVO — motor de reconciliación (Auditor, §5)
│   ├── jarvis-chat/               # NUEVO
│   │   ├── session-manager.js     #   apertura/cierre/versionado de sesiones (§2.3)
│   │   └── tools.js               #   las 5 herramientas que Claude puede llamar en el loop (§2.2)
│   ├── mar-memory/                # NUEVO
│   │   └── memory.js              #   CRUD de Memoria de Mar
│   ├── metrics/                   # NUEVO
│   │   ├── collector.js           #   registra cada evento medible (invocación, output, gap...)
│   │   └── cost-monitor.js        #   consulta gasto de Vercel/Upstash/Anthropic, dispara alertas
│   └── cron/                      # NUEVO
│       └── sync-scheduler.js      #   dispara Flujo B (sesión + cada 3h 7am-7pm)
├── adapters/basecamp/             # YA EXISTE (seed, sin conectar) — mismo patrón que repositories/
├── backlog.md                     # YA EXISTE (HUs de Jarvis Mode, RUN-001)
└── outputs/HU_RUN-001_2026-08-12.md
```

**Por qué esta forma y no una sola carpeta `jarvis/`**: sigue el mismo principio ya confirmado en
`SPEC.md`/`README.md` — cada responsabilidad (repos, auth, brain, chat, memoria, métricas) es un
módulo independiente que se registra donde corresponde, igual que `adapters/basecamp/` no vive
dentro de `src/server.js` sino aparte, intercambiable.

---

## 1. Adaptadores de repositorio

### 1.1 Interfaz común

Ningún consumidor (cron de digest, reconciliación, chat) debe saber si un repo es GitHub o
Bitbucket — todos implementan:

```js
// Interfaz que github-adapter.js y bitbucket-adapter.js deben cumplir
interface RepoAdapter {
  validateAccess(authProfile, owner, repo): Promise<boolean>
  listCommitsSince(authProfile, owner, repo, since: Date): Promise<Commit[]>
  listPullRequests(authProfile, owner, repo, state): Promise<PullRequest[]>
  getFileTree(authProfile, owner, repo, branch): Promise<FileNode[]>   // usado por reconciliación
  getFileContent(authProfile, owner, repo, path, branch): Promise<string>
}
```

### 1.2 Selección de adaptador

```js
// src/repositories/index.js (registry simple, mismo patrón que agents/registry.js)
const ADAPTERS = {
  github: require('./github-adapter'),
  bitbucket: require('./bitbucket-adapter'),
};
function getAdapter(provider) { return ADAPTERS[provider]; }
```

Consumido así desde cualquier flujo:
```js
const adapter = getAdapter(repo.provider);
const commits = await adapter.listCommitsSince(authProfile, repo.owner, repo.repo, since);
```

### 1.3 Librerías

- GitHub: `@octokit/rest` (REST, no GraphQL — más simple para lo que se necesita: commits, PRs,
  árbol de archivos).
- Bitbucket: `fetch` nativo contra la REST API v2.0 — reutiliza los patrones de auth ya probados
  en `adapters/basecamp/AUTH_POC.md` (misma familia de OAuth 37signals-style/Atlassian).

---

## 2. Jarvis Chat — arquitectura del loop agéntico

### 2.1 Secuencia de un turno

```
Usuaria escribe en el Panel de Chat
        │
        ▼
POST /jarvis/chat { conversationId?, message }
        │
        ▼
session-manager.js:
  - Si no hay conversationId → crea sesión nueva, exige `purpose` (HU-006-JarvisMode)
  - Si existe → carga historial de turnos + verifica si se acerca al límite de contexto
        │
        ▼
Cargar contexto: Memoria de Mar completa + lista de proyectos activos (nombre + estado resumido)
        │
        ▼
Llamada a Claude con tool-calling habilitado (tools.js expone las 5 herramientas, §2.2)
        │
        ├──> Claude decide llamar 0-N herramientas, en cualquier orden, antes de responder
        │    (loop: llamada → resultado → Claude decide si necesita otra, hasta que responde texto)
        │
        ▼
Respuesta final de Claude (cita fuentes explícitamente, o dice "no lo sé")
        │
        ▼
session-manager.js persiste el turno completo (mensaje, herramientas usadas, resultado, fuentes)
        │
        ▼
Si alguna herramienta modificó estado (ej. writeMarMemory, invokeAgent) →
el Panel de Estado se refresca con lo nuevo (mismo request/response, no un socket aparte en v1)
```

### 2.2 Las 5 herramientas (`tools.js`)

| Herramienta | Qué hace | De dónde lee/escribe |
|---|---|---|
| `readProjectBrain(projectId)` | Devuelve decisionLog + alerts + meetingLog + reconciliación | `store.js` (ya existe) |
| `readTimeline(projectId, days)` | Eventos crudos recientes | `brain/ingest.js` (nuevo) |
| `readReconciliation(projectId)` | Gaps abiertos/cerrados | `brain/reconciliation.js` (nuevo) |
| `invokeAgent(agentName, input)` | Invoca un agente real (ej. "pídele a Gabi que reestime esto") | `agent-evaluator.js` + `agents/registry.js` (ya existen, reusados tal cual) |
| `writeMarMemory(entry)` | Guarda/actualiza una entrada de Memoria de Mar | `mar-memory/memory.js` (nuevo) |

Ninguna herramienta nueva "inventa" acceso a datos — todas leen de los stores que ya se definieron
en `SPEC_JARVIS.md` §6, solo se exponen como funciones invocables por Claude en el loop.

### 2.3 Modelo de sesiones — versionado para no romper la ventana de contexto

```
sesión "Crear HUs de Jarvis Mode" (v1)
  ├── turno 1, 2, 3... turno N
  └── al acercarse al límite de contexto:
        → se resume el contenido relevante de v1
        → se cierra v1 (status: closed)
        → se abre v2 con el mismo `purpose`, el resumen como primer mensaje de contexto
        → la usuaria sigue sin notar el corte (continuidad conversacional)
```

Criterio de "cerca del límite": umbral de tokens acumulados en la sesión (a calibrar en
implementación — no es una decisión de arquitectura, es un número que se ajusta con uso real,
igual que se decidió para el umbral de autoevaluación en `SPEC_JARVIS.md` §6.8).

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
Provider redirige de vuelta con un token → se guarda en auth-profiles/profiles.js:
  { id, provider, account (email visible), scope (org o personal), tokenRef (nunca el token en claro) }
        │
        ▼
Ese perfil queda disponible como opción en Flujo A (HU-001-JarvisMode) para cualquier proyecto
```

**Nota de seguridad**: el token real nunca se guarda en el JSON del store — `tokenRef` apunta a
una env var o a un secreto en el proveedor de storage (Redis con TTL/rotación, a definir en
implementación). Mismo principio que ya aplica a `accessTokenRef` en `SPEC_JARVIS.md` §6.1.

---

## 4. Autoevaluación — dónde se conecta con `agent-evaluator.js` existente

`AgentEvaluator` ya calcula una rúbrica ponderada por agente (completeness, clarity, adherence,
actionability, alignment). Jarvis Mode no la reemplaza — la envuelve:

```js
// Pseudocódigo del wrapper (no reemplaza AgentEvaluator, lo llama)
async function evaluateInvocation(agentName, output, context) {
  const calidad = await agentEvaluator.evaluate(agentName, output, context); // YA EXISTE
  const eficiencia = await scoreEficiencia(output, context);   // NUEVO — heurística simple v1
  const acertividad = await scoreAcertividad(output, context); // NUEVO
  const formato = await scoreFormato(agentName, output);       // NUEVO — valida contrato esperado
  await metrics/collector.recordEvaluation({ agentName, calidad, eficiencia, acertividad, formato });
  return { calidad, eficiencia, acertividad, formato };
}
```

Se invoca automáticamente después de cada `invokeAgent` (tanto desde el chat como desde
"Invocar Agente" manual) — no es un paso opcional que alguien tenga que disparar.

---

## 5. Reconciliación — de dónde saca los Acceptance Criteria

```
reconciliation.js
    │
    ├─ 1. Lee el/los archivo(s) de HUs del proyecto (backlog.md + outputs/*.md, mismo formato
    │     que Gimena ya usa — ver este mismo repo como ejemplo real)
    │
    ├─ 2. Parsea cada checkbox `- [ ]` de Acceptance Criteria como una unidad reconciliable
    │
    ├─ 3. Por cada AC, busca un test asociado:
    │     - convención de nombre/tag a definir en implementación (ej. un comentario `@ac:HU-004-2.2`
    │       en el archivo de test que lo vincula al AC exacto)
    │     - si no encuentra ninguno → status "sin test"
    │
    ├─ 4. Si encuentra un test, lo ejecuta (o lee el resultado de la última corrida CI) contra el
    │     estado actual del repo (vía RepoAdapter.getFileContent / CI status API)
    │
    └─ 5. Escribe gaps[] a project.memory.projectBrain.reconciliation, dispara alerta si status="gap"
```

**Nota importante (ya en el spec, se reafirma aquí)**: sin test real por AC, nunca se afirma
cumplimiento — es "sin test", no "cumple". Esto significa que el valor de la reconciliación crece
con el tiempo, a medida que se desarrollan tests reales (Fase Calidad del modelo de §6) — no es
todo o nada desde el día uno.

---

## 6. Fases — cómo `phaseContracts.js` se extiende sin romper lo existente

`phaseContracts.js` hoy modela 5 fases con `id: 1-5`. El modelo ampliado de `SPEC_JARVIS.md` §4
no reemplaza esos IDs — los envuelve en una jerarquía superior:

```js
// Extensión propuesta, no reemplazo
const PROJECT_LIFECYCLE = {
  iniciacion: {
    subfases: ['kick_off', 'planning'],
    mapeoAFasesExistentes: { planning: 1 }   // kick_off es nuevo, sin fase numérica hoy
  },
  ejecucion: {
    subfases: ['desarrollo_backend', 'desarrollo_frontend', 'desarrollo_devops', 'calidad', 'seguimiento'],
    mapeoAFasesExistentes: { desarrollo_backend: 2, desarrollo_frontend: 3, calidad: 4 }
    // desarrollo_devops mapea a fase 5 (Deploy) — hoy sin agentes, gap heredado
    // seguimiento es nuevo — lo cubre el propio Jarvis Mode (Brain vivo + reconciliación)
  },
  cierre: {
    subfases: ['entregas_parciales', 'entregas_finales', 'renovacion', 'garantia'],
    mapeoAFasesExistentes: {}   // totalmente nuevo, gap total (pilar "Delivery" de SPEC_FOLLOWUP.md)
  }
};
```

Los endpoints existentes (`GET /phases`, `POST /orchestrate`) siguen funcionando igual — esta capa
es solo metadata adicional para que el dashboard/chat puedan hablar de "en qué fase del ciclo de
vida completo está el proyecto", no un cambio de contrato.

---

## 7. Monitoreo de costos — de dónde saca los números

```
cost-monitor.js (cron, corre junto al ciclo de sincronización de §2 del spec)
    │
    ├─ Vercel: API de uso/facturación del proyecto (requiere token de cuenta de Vercel)
    ├─ Upstash: API de métricas de la base de datos Redis (comandos, almacenamiento)
    └─ Anthropic: costo ya se registra por invocación (metrics/collector.js) — aquí se sólo agrega
       el total de cuenta, no por output individual (eso ya está en Analítica P1)
    │
    ▼
Si algún proveedor sale de free tier o supera un umbral (a definir en implementación) →
alerta por el mismo canal que las alertas del Brain (chat + Panel de Estado)
```

---

## 8. Lo que esta elaboración técnica NO decide todavía (correcto dejarlo así)

- Umbral exacto de tokens para versionar una sesión de chat (§2.3) — se calibra con uso real.
- Convención exacta de vínculo test↔AC en `reconciliation.js` (§5) — decisión de implementación,
  no de arquitectura.
- Umbral de alerta de costos (§7) — depende de cuánto presupuesto mensual defina Mar, no es una
  decisión técnica.
- Detalle del flujo OAuth de Auth Profiles con SSO de Google (§3) — bloqueado por la
  investigación pendiente ya registrada en `SPEC_JARVIS.md` §11.

Estas son decisiones de **implementación**, no de arquitectura — se resuelven cuando se escriba
el código real, no antes.
