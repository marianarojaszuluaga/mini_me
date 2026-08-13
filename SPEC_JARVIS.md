# SPEC — Jarvis Mode (chat conversacional, multi-repo, memoria de Mar, autoevaluación, analítica)
> **Status**: **Aprobado — primer esqueleto real implementado (2026-08-12)**. Backend FastAPI
> arranca, los 24 endpoints del spec están registrados y verificados (`GET /health` responde,
> `openapi.json` lista todas las rutas). Ver tabla de avance en §12.
> **Creado**: Agosto 2026
> **Depende de**: `SPEC.md` (Orquestrador 360 base — MAP + Orchestrator + 22 agentes + 5 fases)
> **Elaboración técnica**: ver [`ARCHITECTURE_JARVIS.md`](ARCHITECTURE_JARVIS.md) — mapa contra
> `src/` actual, secuencias del loop de chat, adaptadores de repo, reconciliación.
> **Nombres**: "Jarvis" = "mini me" = "Orquestrador 360" — es el mismo sistema, tres nombres
> según el momento (visión / repo original / nombre técnico del producto).

---

## 0. TL;DR

Orquestrador 360 hoy gestiona proyectos uno por uno, con acciones manuales por formulario (elegir
proyecto → elegir agente → elegir paso → invocar). Jarvis Mode lo convierte en un **asistente
conversacional multi-proyecto**: le hablas en un **chat real, de ida y vuelta**, como esta misma
conversación — no un formulario que dispara un único POST. El Project Brain de cada proyecto se
mantiene vivo con la **verdad del código** (el repo es la fuente de verdad, no lo que alguien
reportó que hizo). Además de la memoria por proyecto, existe una **memoria de "Mar"** — qué
entiende y qué tiene pendiente de entender la usuaria sobre el sistema mismo, independiente de
cualquier proyecto. Y el sistema **se autoevalúa y mejora con el tiempo**, con **números
verificables** que demuestren que es real y que mejoró — no solo la palabra de que funciona.

No reemplaza nada de `SPEC.md`: los 22 agentes, las 5 fases y el `toolRegistry` siguen igual.
Jarvis Mode es la capa conversacional + de verdad + de memoria + de mejora, construida encima.

---

## 1. Principios de diseño

1. **Extiende, no reemplaza.** El `toolRegistry` ya está diseñado para adaptadores
   intercambiables (confirmado agosto 2026). Los repos son un adaptador más, igual que Basecamp.
2. **Chat, no formulario.** La interacción principal con Jarvis es una **conversación multi-turno
   con memoria de la sesión** — igual que hablar con Claude Code. Nada de "llena estos 3 campos y
   dale submit" para preguntar cómo va algo. El chat puede llamar herramientas a mitad de
   conversación (leer Brain, leer repo, invocar un agente) — es agéntico, no un solo prompt.
3. **El código es la fuente de verdad.** Un Project Brain que dice "HU-005 completada" porque
   alguien lo escribió en un acta, pero el repo no tiene el código, está **mintiendo**. El repo
   manda sobre cualquier reporte humano o texto suelto. Jarvis reconcilia periódicamente lo
   declarado (HUs/backlog/actas) contra lo real (commits, archivos, tests que pasan) y señala la
   diferencia como una alerta — no la esconde ni la promedia.
4. **Un repo no es un proyecto.** Un `Project` puede tener 0, 1 o N repos (`repositories: []`).
5. **Digest, no ruido.** El Brain no se llena una entrada por commit — se agregan señales, no se
   listan.
6. **Memoria de Mar ≠ Project Brain.** El Project Brain es sobre el proyecto (decisiones,
   alertas, avance). La Memoria de Mar es sobre **la usuaria y su relación con el sistema**: qué
   todavía está entendiendo, qué le explicaron ya y no hace falta repetir, qué le falta decidir.
   Vive a nivel de sistema, no por proyecto — es la que le da a Jarvis continuidad de "quién eres
   y qué sabes ya" entre conversaciones.
7. **Nada se declara mejorado sin número.** Toda evaluación de calidad, toda reconciliación
   código↔spec, todo uso del sistema se mide y queda en una serie de tiempo consultable. La
   retroalimentación más dura que recibió este esfuerzo fue "no hay número que muestre que esto
   es real y que mejoró" — este spec la responde con una capa de analítica explícita, no como
   ocurrencia tardía.
8. **El dashboard es el centro de trabajo y decisión — no un menú de páginas.** Corrección sobre
   el borrador anterior: el sitemap original listaba pantallas como destinos separados a los que
   "se navega". La experiencia real debe ser un **command center**: el chat y el estado en vivo de
   los proyectos conviven en la misma pantalla, para que decidir sea parte de la conversación, no
   un paso aparte de "ir a ver el dashboard después de preguntar". Todo lo demás (detalle de
   proyecto, Analítica completa, Memoria de Mar, Integraciones) son *drill-downs* desde ese centro,
   no secciones de nivel igual en un menú.

---

## 2. Sitemap — organizado como Command Center, no como menú de páginas

```
🎯 Jarvis — Command Center                          ← ÚNICA pantalla de trabajo real
│
├── 💬 Panel de Chat (persistente, mitad de la pantalla — NO es "otra sección")
│   ├── Conversación multi-turno, con memoria de sesión
│   ├── Sesiones con inicio y fin por tarea (ver §6.6 — "crear HUs" abre y cierra su propia
│   │   sesión, no todo vive en un hilo infinito)
│   └── Cada respuesta cita su fuente y puede disparar una actualización visible al instante
│       en el Panel de Estado (misma pantalla, sin recargar ni navegar)
│
├── 📊 Panel de Estado (la otra mitad — se actualiza en vivo con lo que pasa en el chat)
│   ├── Semáforo por proyecto (on-track / atención / bloqueado) — click → detalle
│   ├── Top alertas de reconciliación abiertas (las más urgentes, no todas)
│   └── Snapshot de las métricas clave del momento (uso de hoy, últimos gaps, calidad reciente)
│
└── Drill-downs (se abren desde un click en el Panel de Estado — nunca es el punto de partida)
    ├── 📁 Detalle de Proyecto — fases y agentes, Project Brain (con Reconciliación),
    │   Repositorios asociados, Timeline de actividad
    ├── 📈 Analítica completa — todas las series de tiempo con drill-down a eventos crudos
    ├── 🧠 Memoria de Mar — glosario vivo, preguntas abiertas, editable manualmente
    ├── ⚙️ Invocar Agente (uso directo/manual, para cuando no quieres pasar por el chat —
    │   se corrige el bug de overlap en este rediseño)
    └── 🔌 Integraciones — Auth Profiles (§6.2), repos conectados, Basecamp
```

**Principio de UX**: nunca tienes que "ir a otro lado" para tomar una decisión — preguntas en el
chat, ves la consecuencia en el Panel de Estado de la misma pantalla, y si necesitas el detalle
completo de algo, se abre encima (drill-down), no te saca del Command Center.

---

## 3. Flujos de trabajo (ajustados al Command Center de §2 — ninguno parte de un menú, todos parten del chat o de un drill-down)

### Flujo A — Conectar un proyecto multi-repo (setup, una vez por proyecto)

1. Crear proyecto — puede pedirse desde el chat ("crea el proyecto X") o desde el drill-down
   📁 Detalle de Proyecto (ya existe).
2. Dentro de ese drill-down, en "Repositorios asociados" → "+ Conectar repo" → elegir **Auth
   Profile** (§6.2, no un login nuevo cada vez) → GitHub/Bitbucket → elegir repo(s).
3. Se registra `{provider, owner, repo, defaultBranch, authProfileId, environment}` en
   `project.repositories[]` — `environment` distingue prod/develop (ver §9.3).
4. Primer digest histórico (7 días) para poblar el Brain sin esperar el primer ciclo.
5. En cuanto termina, el Panel de Estado del Command Center refleja el proyecto con datos reales
   — sin necesidad de recargar ni salir del drill-down.

### Flujo B — Project Brain vivo, con el código como jueza final

**Cadencia (ajustada, §9.3): no es un cron diario fijo** — se sincroniza al iniciar sesión y,
además, cada 3 horas entre 7am–7pm (horario de trabajo), no en horario nocturno donde no hay
actividad que traer. Cada corrida distingue el `environment` (prod vs. develop) del repo que
está leyendo — un gap en develop no es la misma alerta que un gap en prod.

```
Trigger: inicio de sesión del chat, O cada 3h entre 7am-7pm (por proyecto con repos conectados)
    │
    ▼
Adapter de repo trae commits/PRs de 24h + estado actual de archivos relevantes
    │
    ▼
Auditor (agente ya existente, fase 2) compara HUs/backlog "declarados como hechos"
contra lo que el repo realmente tiene — no confía en el texto del acta/backlog por sí solo
    │
    ▼
POST /brain/ingest-event  { type: "commit_digest" | "reconciliation_gap", payload: {...} }
    │
    ▼
Gabriela resume → { decisions[], alerts[] } — un "reconciliation_gap" SIEMPRE genera alerta,
nunca se descarta en el resumen aunque el digest general no tenga nada relevante
    │
    ▼
project.memory.projectBrain — igual que hoy, más una sub-sección "reconciliación"
```

**Ejemplo concreto de por qué importa**: si el backlog dice "HU-005 completada" pero el repo no
tiene el archivo/test que esa HU pedía, hoy el Brain lo creería porque nadie lo contradice. Con
este flujo, el Auditor lo detecta y genera una alerta explícita — el código manda.

### Flujo C — Jarvis Chat, dentro del Command Center (la interacción principal, NO un formulario)

Esto reemplaza el `POST /jarvis/ask` de un solo turno que se planteó en el borrador anterior. El
chat **no es una pantalla a la que navegas** — es el panel izquierdo/central del Command Center
(§2), siempre visible junto al Panel de Estado.

1. Escribes en lenguaje natural, con el mismo ritmo de ida y vuelta que esta conversación:
   *"¿Cómo va Finanz Butik?"* → Jarvis responde → *"¿y qué falta de eso?"* (pregunta de
   seguimiento, sin repetir contexto) → Jarvis usa el hilo ya construido.
2. Internamente, cada turno puede disparar **llamadas a herramientas** (no una sola inyección de
   contexto): leer el Project Brain de uno o varios proyectos, leer el timeline/reconciliación,
   invocar un agente si la pregunta lo requiere ("pídele a Gabi que reestime esto").
3. **Sesiones con inicio y fin por tarea (decidido)**: la conversación NO es un hilo infinito.
   Cada tarea concreta ("crear las HUs de X", "revisar reconciliación de Y") abre una sesión con
   propósito explícito y la cierra al terminar — o se **versiona** (sesión v2, v3 del mismo tema)
   en vez de seguir acumulando turnos sin límite. Esto evita romper la ventana de contexto en
   tareas largas, igual que esta conversación se divide en "capítulos". El historial de sesiones
   cerradas queda consultable, no se borra.
4. Cualquier acción que resulte de la conversación (una alerta resuelta, un gap cerrado, un
   proyecto actualizado) se refleja **al instante en el Panel de Estado de la misma pantalla** —
   nunca hace falta recargar ni navegar a otra vista para ver la consecuencia de lo que se habló.
5. Cada afirmación de Jarvis cita su fuente (qué decisión/alerta/commit/HU la sustenta). Si no
   hay información suficiente, lo dice explícitamente — no inventa avance.
6. El chat puede, a mitad de conversación, **leer o escribir en la Memoria de Mar** (ej.: "ok,
   entendido, no hace falta que me lo repitas" → Jarvis lo anota ahí, no en el Project Brain).

### Flujo D — Memoria de Mar (independiente de cualquier proyecto)

1. Cada vez que en el chat surge algo sobre **cómo Mar entiende el sistema** (no sobre un
   proyecto puntual) — una aclaración de nombres, una decisión de alcance, una pregunta que dijo
   "eso ya lo tengo claro, no me lo repitas" — Jarvis lo guarda en la Memoria de Mar.
2. Es visible y editable en su propia pantalla — Mar puede corregir algo que Jarvis asumió mal,
   igual que se corrige una memoria mal guardada.
3. Se carga como contexto en **cada** conversación nueva del chat, sin que Mar tenga que repetir
   quién es o qué ya sabe.

### Flujo E — Trabajar proyectos en paralelo

Consecuencia de A+B+C, no una feature de UI de multitasking: el Panel de Estado del Command
Center (§2) ya muestra el semáforo de todos los proyectos activos a la vez, y el chat responde
preguntas puntuales sobre cualquiera de ellos sin cambiar de pantalla — no hace falta "entrar" a
cada proyecto para saber cómo va.

---

## 4. Fases — Gestión de Proyectos 360 (modelo ampliado, reemplaza la vista de "solo 5 fases SDLC")

Corrección importante sobre el borrador anterior: las 5 fases de `phaseContracts.js`
(Planeación/Backend/Frontend/Integración-Calidad/Deploy) son el **ciclo de ejecución técnica**,
pero no cubren todo el ciclo de vida real de un proyecto — no dicen nada del kickoff, del
seguimiento continuo, ni de cómo se cierra/entrega/renueva un proyecto. Mar definió la taxonomía
completa; esto **extiende** el modelo actual, no lo descarta.

### 4.1 Taxonomía completa

```
Gestión de Proyectos 360
├── 1. Iniciación
│   ├── 1.1 Kick off
│   └── 1.2 Planning
├── 2. Ejecución
│   ├── 2.1 Desarrollo
│   │   ├── 2.1.1 Backend
│   │   ├── 2.1.2 Frontend
│   │   └── 2.1.3 DevOps
│   ├── 2.2 Calidad
│   └── 2.3 Seguimiento
└── 3. Cierre
    ├── 3.1 Entregas parciales
    ├── 3.2 Entregas finales
    ├── 3.3 Renovación
    └── 3.4 Garantía
```

### 4.2 Mapeo contra lo que ya existe (para no reinventar lo que ya funciona)

| Fase nueva | Fase/pieza actual | Agentes | Estado |
|---|---|---|---|
| 1.1 Kick off | — | — | **Gap nuevo**: no existe hoy ni en `phaseContracts.js` ni en agentes. Candidato natural: extender a `gabriela` (Project Brain Keeper) para que el kickoff sea el primer evento que abre el Brain de un proyecto. |
| 1.2 Planning | Fase 1 actual (Planeación) | gimena, milestone-writer, dod-definer, gabi, capacity-reconciler, gina-scheduler | Ya existe, sin cambios |
| 2.1.1 Backend | Fase 2 actual | data-engineer, gabi, architect, auditor, fixed-errors, qa-integrator | Ya existe |
| 2.1.2 Frontend | Fase 3 actual | fullstack-developer, flutter-developer, auditor, fixed-errors, integration | Ya existe |
| 2.1.3 DevOps | Fase 5 actual (Deploy) | — | **Gap heredado, ya documentado en `SPEC.md`**: Deploy no tiene agente asignado ni en `ia-hybrid-teams`. Se hereda aquí con el mismo nombre de gap, ahora dentro de Ejecución en vez de al final. |
| 2.2 Calidad | Fase 4 actual (Integración y Calidad) | sonar-quality-gate, unit-test-standards-reviewer, mcp-integration-tester, test-video-recorder, quality-report-generator | Ya existe |
| 2.3 Seguimiento | Pilar "Follow Up" de `SPEC_FOLLOWUP.md` | — (spec existe, "sin código, sin agentes todavía" según ese doc) | **Se resuelve en gran parte por este mismo spec** — el Brain vivo + reconciliación + Jarvis Chat de Jarvis Mode ES la pieza de Seguimiento mecánico que `SPEC_FOLLOWUP.md` deja pendiente. La gestión de personas (1:1, planes de mejora) de ese pilar sigue fuera de alcance — no es automatizable. |
| 3.1–3.4 Cierre (Entregas parciales/finales, Renovación, Garantía) | Pilar "Delivery" de `SPEC_FOLLOWUP.md` §1 ("Delivery — pendiente: QA, Releases, Entregas Parciales/Finales, Garantía") | — | **Gap total, ya señalado como pendiente en `SPEC_FOLLOWUP.md`** — no se resuelve en este spec, pero queda formalmente registrado como la Fase 3 completa del modelo, para no perderlo de vista. Candidato a un `SPEC_CIERRE.md` propio más adelante. |

### 4.3 Cómo se construye Jarvis Mode dentro de este modelo ampliado

Jarvis Mode en sí (este spec) se construye siguiendo el ciclo de **Ejecución** de su propio
proyecto — es dogfooding: usar el modelo de fases para construirse a sí mismo.

| Fase (del modelo ampliado) | Entregable de Jarvis Mode |
|---|---|
| 1.1 Kick off | Este spec, aprobado por Mar |
| 1.2 Planning | HUs detalladas — **generadas por Gimena**, no escritas a mano (§5, regla de `.claude`) |
| 2.1.1 Backend | `repositories[]`, adaptadores de repo, `/brain/ingest-event`, `/jarvis/chat`, motor de reconciliación, Memoria de Mar, métricas |
| 2.1.2 Frontend | Jarvis Chat (Command Center), Memoria de Mar, Analítica, Repositorios/Integraciones — dentro del rediseño React |
| 2.1.3 DevOps | Cron/scheduler en Vercel, variables de Auth Profiles, monitoreo de costos (§8) |
| 2.2 Calidad | Tests reales por Acceptance Criteria (para que la reconciliación §6.7 tenga con qué comparar), probar chat multi-turno con datos reales |
| 2.3 Seguimiento | Una vez desplegado, Jarvis Mode se usa a sí mismo para seguir su propio avance — el primer proyecto en su propio Brain vivo es él mismo |

---

## 5. Historias de Usuario (HU)

> **Regla de `.claude` (confirmada por Mar)**: las HUs siempre se generan invocando al agente
> **Gimena** (perfil canónico en `src/agents/spec-kit-agents/Gimena-userstorywriter.md`), nunca
> escritas a mano por fuera del sistema. **Generadas** en esta ronda (RUN-001, 2026-08-12) —
> Mar confirmó que usar a Gimena dentro de esta conversación cuenta como invocación real, sin
> necesidad de esperar una `ANTHROPIC_API_KEY` en `.env` (que sigue siendo falsa a propósito).

**Backlog maestro**: [`backlog.md`](backlog.md) — HU-001-JarvisMode a HU-010-JarvisMode.
**HUs completas** (formato Gimena: Contexto, Criterios de Aceptación con Interfaz/Casos de
Uso/Manejo de Errores, Referencia Visual): [`outputs/HU_RUN-001_2026-08-12.md`](outputs/HU_RUN-001_2026-08-12.md).

| HU | Título | Feature |
|---|---|---|
| HU-001-JarvisMode | Conectar repositorios a un proyecto | F1 — Multi-repo |
| HU-002-JarvisMode | Ver estado de sincronización de repositorios | F1 — Multi-repo |
| HU-003-JarvisMode | Sincronización programada del Project Brain (sesión + cada 3h, prod/develop) | F2 — Brain vivo |
| HU-004-JarvisMode | Reconciliación código↔spec contra Acceptance Criteria | F2 — Brain vivo |
| HU-005-JarvisMode | Timeline unificado por proyecto | F2 — Brain vivo |
| HU-006-JarvisMode | Jarvis Chat conversacional multi-turno | F3 — Chat |
| HU-007-JarvisMode | Memoria de Mar (glosario vivo del sistema) | F4 — Memoria de Mar |
| HU-008-JarvisMode | Autoevaluación multidimensional y continua | F5 — Autoevaluación |
| HU-009-JarvisMode | Changelog de mejoras del sistema | F5 — Autoevaluación |
| HU-010-JarvisMode | Panel de Analítica de negocio | F6 — Analítica |

---

## 6. Especificación técnica

### 6.1 Modelo de datos — cambios sobre `Project`

```js
{
  // ...campos existentes...
  repositories: [
    {
      id: "repo_xxx",
      provider: "github" | "bitbucket",
      owner: "marianarojaszuluaga",
      repo: "mini_me",
      defaultBranch: "main",
      connectedAt: "2026-08-12T...",
      lastSyncAt: "2026-08-12T...",
      accessTokenRef: "env:GITHUB_TOKEN_PROJ_X"   // nunca el token en claro
    }
  ],
  memory: {
    projectBrain: {
      // ...ya existe: decisionLog, alerts, meetingLog...
      reconciliation: {
        lastRunAt: "2026-08-12T...",
        gaps: [
          { huId: "HU-005", claim: "completada", evidence: "sin archivo/test esperado", status: "open" }
        ]
      }
    }
  }
}
```

### 6.2 Auth Profiles — múltiples identidades de Mar (decidido)

No es "una OAuth App por proveedor" — es un store de **perfiles de autenticación**, cada uno una
identidad distinta que Mar ya tiene, para poder conectar cualquier combinación de cuenta↔org↔repo
sin duplicar trabajo. Confirmado viable para v1: cada proveedor (GitHub, Bitbucket) ya soporta
múltiples cuentas autorizando por separado — lo único que se construye es el store que las nombra
y las deja elegibles al conectar un repo.

```js
// storage/auth-profiles.json
{
  profiles: [
    { id: "gh_imagineapps", provider: "github", account: "mariana@imagineapps.co", scope: "personal-github" },
    { id: "bb_imagineapps_org", provider: "bitbucket", account: "mariana@imagineapps.co", scope: "org:imagineappsdev" },
    { id: "bb_personal", provider: "bitbucket", account: "mariana@gmail.com", scope: "personal-bitbucket" }
  ]
}
```

Al conectar un repo (Flujo A), Mar elige qué **perfil** usar — así la misma cuenta
`@imagineapps.co` sirve tanto para la org de Bitbucket de Imagine Apps como para su GitHub
personal, y la cuenta de Gmail conecta su Bitbucket personal, sin mezclarlas.

**Nota técnica pendiente de investigar** (Mar no tiene la respuesta, es correcto no inventarla):
su cuenta `@imagineapps.co` entra normalmente vía **SSO de Google** (Google Workspace), no con
usuario/contraseña propio. Eso significa que el "OAuth App" de GitHub/Bitbucket para ese perfil
probablemente termina delegando en un login de Google por debajo (GitHub soporta SSO/SAML por
org; Bitbucket/Atlassian soporta login con Google) — hay que confirmar en la Fase 2 (Backend) si
la org de Bitbucket de Imagine Apps ya tiene SSO de Google forzado, porque eso cambia si el flujo
es "conectar con GitHub/Bitbucket" o "conectar con Google" para ese perfil específico. Ver
Open Question en §11.

### 6.3 Nuevo store — Memoria de Mar (a nivel sistema, no por proyecto)

```js
// storage/mar-memory.json (o Redis key "mar:memory")
{
  entries: [
    {
      id: "mem_xxx",
      type: "understanding" | "open_question" | "correction",
      content: "Jarvis = mini me = Orquestrador 360, mismo sistema",
      createdAt: "2026-08-12T...",
      source: "chat" | "manual"
    }
  ]
}
```

### 6.4 Nuevo store — Métricas (serie de tiempo, no snapshot)

```js
// storage/metrics.json (o Redis con series por agente/día)
{
  agentEvaluations: [
    // 4 dimensiones (§6.8), no un único avgScore — decidido en la ronda de aprobación
    { agent: "gimena", date: "2026-08-12", eficiencia: 88, acertividad: 90, formato: 95, calidad: 84, count: 4 }
  ],
  reconciliationRuns: [
    { projectId: "...", date: "2026-08-12", gapsFound: 2, gapsClosedSinceLast: 1, sinTest: 3 }
  ],
  usage: [
    { date: "2026-08-12", chatMessages: 14, agentInvocations: 6 }
  ]
}
```

### 6.5 Nuevos endpoints (MAP, puerto 3001)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/projects/:id/repositories` | Conectar repo |
| GET | `/projects/:id/repositories` | Listar |
| DELETE | `/projects/:id/repositories/:repoId` | Desconectar |
| POST | `/brain/ingest-event` | Generaliza `ingest-acta` |
| GET/POST | `/projects/:id/reconciliation` | Ver / disparar reconciliación on-demand |
| **POST** | **`/jarvis/chat`** | **Chat multi-turno con sesión — reemplaza el `/jarvis/ask` de un solo turno del borrador anterior** |
| GET/POST | `/mar/memory` | Leer / escribir Memoria de Mar |
| GET | `/metrics/agents` | Serie de tiempo de calidad por agente |
| GET | `/metrics/reconciliation` | Serie de tiempo de gaps encontrados/cerrados |
| GET | `/metrics/usage` | Serie de tiempo de uso |
| GET | `/projects/:id/timeline` | Timeline unificado |

### 6.6 Jarvis Chat — diseño (agéntico, no un solo prompt)

`/jarvis/chat` no es "meter todo el contexto en un prompt y responder" — es un loop con
herramientas disponibles para Claude en cada turno:

```
Turno del usuario
    │
    ▼
Cargar: historial de la conversación + Memoria de Mar + lista de proyectos activos
    │
    ▼
Claude decide si necesita llamar una herramienta:
  - readProjectBrain(projectId)
  - readTimeline(projectId, days)
  - readReconciliation(projectId)
  - invokeAgent(agentName, input)     ← solo si la pregunta lo pide explícitamente
  - writeMarMemory(entry)             ← cuando la usuaria confirma/corrige algo sobre el sistema
    │
    ▼
Responde citando fuente; si falta info, lo dice explícitamente
    │
    ▼
Se persiste el turno (mensaje + herramientas usadas + fuentes citadas) en la sesión
```

Mismo modelo de "no inventar" que ya rige la extracción de actas: Gabriela/Jarvis no afirma nada
que no pueda señalar de dónde sale.

**Sesiones con inicio/fin por tarea (decidido)** — modelo de datos:

```js
// storage/jarvis-sessions.json
{
  sessions: [
    {
      id: "sess_xxx",
      purpose: "Crear HUs de Jarvis Mode",     // obligatorio — no hay sesión sin propósito
      projectId: "Proyecto_...",                // opcional, puede ser cross-proyecto
      status: "open" | "closed",
      version: 1,                                // v2/v3 si se retoma el mismo propósito después
      turns: [ /* mensajes + herramientas usadas + fuentes citadas */ ],
      openedAt: "...", closedAt: "..." 
    }
  ]
}
```

- Una sesión se cierra explícitamente al terminar la tarea, o el sistema la corta y abre una
  nueva versión si se acerca al límite de contexto (igual que la compactación de esta conversación).
- El historial de sesiones cerradas queda consultable desde el chat ("¿qué decidimos la vez que
  armamos las HUs de X?") — cerrar no es borrar.

### 6.7 Motor de reconciliación (Auditor, agente ya existente) — decidido: precisión contra el Spec + respaldo de tests reales

**Decisión**: la reconciliación no es una heurística difusa del Auditor "opinando" si algo se ve
hecho — es una comparación **precisa contra el texto exacto de la spec**: cada Acceptance
Criteria (`- [ ]`) de cada HU es la unidad que se reconcilia, no una impresión general de la HU.

- **Input**: el texto literal de los Acceptance Criteria de cada HU (de `SPEC*.md`/backlog) +
  estado real del repo (archivos, y — a partir de la Fase 4, Integración y Calidad — **tests
  reales** desarrollados específicamente para verificar cada AC).
- **Output**: `gaps[]` con `{huId, acceptanceCriterion, testRef, status}` — `testRef` apunta al
  test que efectivamente lo verifica, no a una inferencia del Auditor.
- **Relación con Fase 4**: la reconciliación depende de que exista una prueba real por AC. Hasta
  que esa prueba exista, el gap queda marcado `status: "sin test"` en vez de "cumple"/"no cumple"
  — el sistema nunca afirma un cumplimiento que no puede verificar con un test.
- Corre: (a) en el cron diario junto al digest, (b) on-demand desde el chat.
- Limitación aceptada v1: solo reconcilia ACs que ya tienen un test desarrollado. Los que no,
  quedan explícitamente como pendientes de verificación, no se ocultan ni se asumen cumplidos.

### 6.8 Autoevaluación y mejora — decidido: multidimensional y continua, no por umbral de tiempo

Reemplaza el modelo de "N semanas de degradación sostenida" del borrador anterior (ver HU-008-JarvisMode
para el detalle de las 4 dimensiones: eficiencia, acertividad, formato, calidad):

- Cada invocación de agente corre las 4 evaluaciones **inmediatamente**, no en un job semanal
  aparte — el feedback está disponible en el momento, no días después.
- Cada dimensión se acumula en su propia serie de tiempo (§6.5 `agentEvaluations`, ahora con
  4 sub-scores en vez de un único `avgScore`).
- Una caída puntual por debajo de un umbral en **cualquier** dimensión se marca de inmediato en
  esa invocación — no espera un patrón de varias semanas para ser visible.
- **Decidido**: **2 invocaciones seguidas** por debajo del umbral en una misma dimensión disparan
  la propuesta de ajuste de prompt — siempre pendiente de aprobación de Mar, nunca autoaplicada.
- El changelog (`HU-009-JarvisMode`) registra qué se cambió y qué pasó con cada una de las 4
  dimensiones después — no solo un score general.

---

## 7. Analítica — por qué es una capa de primer nivel, no un "nice to have"

La retroalimentación que motivó esto: **no hay número que muestre que el sistema es real y que
mejoró**. La instrucción explícita de Mar: cuantificar **todos los resultados**, por tipo de
output y por agente, para generar **inteligencia de negocio** — todo lo de abajo está **aprobado**
(incluidas las propuestas de Claude). Unificado en una sola lista priorizada, nada descartado.

| Prioridad | Métrica | Por qué en ese orden |
|---|---|---|
| **P0** | Número de outputs por tipo (HUs, specs, planes, actas, evaluaciones, reconciliaciones) — contador independiente por tipo, no un total mezclado | Es la base de todo lo demás — sin esto no hay con qué cruzar ninguna otra métrica |
| **P0** | Número de usos — invocaciones totales, por agente, por proyecto, por semana | Responde directo a "¿esto se usa de verdad?" |
| **P0** | Reconciliación: gaps encontrados vs. cerrados, por proyecto y en el tiempo | La métrica más contundente contra el escepticismo: demuestra que el sistema **encuentra y corrige desalineación real**, no solo que "corre" |
| **P1** | Tasa de aceptación por tipo de output (usado tal cual vs. descartado/regenerado) | Sin esto, "número de outputs" mide actividad, no valor |
| **P1** | Calidad en el tiempo — las 4 dimensiones (§6.8) por agente, en serie, no snapshot | Ya viene gratis del feedback inmediato de autoevaluación — solo hay que acumularlo |
| **P1** | Costo por output (tokens/USD reales de la API) | Da el número de negocio que cruza con "número de outputs" — cuánto cuesta producir cada tipo |
| **P2** | Comparación "antes vs. después" — mismo tipo de tarea en dos fechas, con score y tiempo | La más persuasiva en una conversación puntual, pero necesita historial acumulado primero (depende de P0/P1) |
| **P2** | Tendencia semana a semana de cada contador (no solo el acumulado) | Un acumulado siempre sube; esto es lo que distingue crecimiento real de estancamiento |
| **P2** | Distribución de uso por proyecto/cliente | Útil para decidir dónde vale la pena seguir conectando repos, pero no bloquea nada más |
| **P3** | Tiempo ahorrado estimado (baseline aproximado vs. tiempo real de invocación) | Marcado siempre como estimado, no medición exacta — es el más "blando" de todos, se construye al final |

Ninguna métrica se muestra sin poder hacer drill-down al evento crudo que la compone (ya en
HU-010-JarvisMode) — el orden de prioridad es de construcción, no de qué se le oculta a nadie.

---

## 8. Stack tecnológico

### 8.0 Corrección de arquitectura (2026-08-12) — el backend se reescribe completo en Python/FastAPI

**Decisión**: el backend actual (`src/server.js` MAP + `src/orchestrator.js` Orchestrator, Node/
Express) **se reescribe por completo en Python con FastAPI** — no es un servicio nuevo en Python
que conviva con el Node existente; es una migración total del backend. Framework confirmado:
**FastAPI** (asíncrono nativo, tipado con Pydantic — encaja con el loop agéntico del chat y con
llamadas concurrentes a herramientas/Anthropic).

Esto es un cambio de alcance mayor que "solo Jarvis Mode": el MAP+Orchestrator ya construido y
desplegado (`SPEC.md`, estado "MVP construido y desplegado") también se reescribe. Detalle
completo de la migración en [`ARCHITECTURE_JARVIS.md`](ARCHITECTURE_JARVIS.md) §0 (estructura de
capas FastAPI) — este spec deja de asumir Express como base a partir de aquí. `SPEC.md` queda
marcado con una nota de pivote (ver su cabecera) para no generar inconsistencia entre documentos.

| Capa | Antes (Node/Express, ya no vigente) | Ahora (Python/FastAPI) |
|---|---|---|
| Backend — framework | Express | **FastAPI**, con capas explícitas (routers/services/schemas/adapters — §0 de `ARCHITECTURE_JARVIS.md`) |
| Backend — Anthropic | `@anthropic-ai/sdk` (Node) | `anthropic` (SDK oficial Python) |
| Backend — Redis | `@upstash/redis` (Node) | `upstash-redis` (Python) o cliente REST directo (misma API HTTP de Upstash, agnóstica de lenguaje) |
| Backend — GitHub | — | `PyGithub` o `httpx` directo contra la REST API |
| Backend — Bitbucket | — | `httpx` directo contra la REST API v2.0 (mismo patrón de `adapters/basecamp/AUTH_POC.md`) |
| Backend — cron | — | APScheduler (in-process) o Vercel Cron llamando a un endpoint FastAPI, según cómo se despliegue (§8.2) |
| Frontend | React + Vite (rediseño ya planeado) | **Sin cambio** — el rediseño React sigue igual; solo cambia con qué backend habla (misma API REST, contrato no cambia por el lenguaje del servidor) |
| Storage | Redis (prod) / filesystem (local) | **Sin cambio de motor** — mismas colecciones/keys ya definidas en §6, solo cambia el cliente que las lee/escribe |
| Auth | App API Keys | **Sin cambio de esquema** — mismas App API Keys, verificación se reimplementa en FastAPI (dependency injection en vez de middleware Express) |

### 8.1 Canal móvil — decidido: PWA

Dashboard instalable, responsive real (con el bug de overlap ya corregido en el rediseño React),
sesión persistente. Se construye dentro del mismo esfuerzo de rediseño frontend ya planeado — no
es una pieza de infraestructura aparte como habría sido un bot.

### 8.2 Infraestructura y monitoreo de costos — decidido

**Decisión**: se despliega en **Vercel + Redis del Marketplace (Upstash)**, no una alternativa
sin Redis. Razón de Mar: ahorrar costo y evitar AWS mientras esto es un POC — cuando el POC esté
terminado, se migra a AWS (fuera de alcance de este spec, pero `src/store.js` ya soporta
filesystem/Redis intercambiable, así que la migración no debería tocar lógica de negocio).

**Nuevo, explícitamente pedido por Mar**: monitoreo de costos de todo lo que está desplegado —
"me interesa monitorearlo" fue explícito, no es un nice-to-have.

- Fuentes de costo a vigilar: Vercel (funciones + banda ancha), Upstash Redis (comandos/almacenamiento),
  Anthropic API (ya parcialmente cubierto por "costo por output" en §7, pero aquí es el costo
  **total** de la cuenta, no por invocación individual).
- Alertas: si un proveedor empieza a cobrar (se sale del free tier) o el gasto supera un umbral
  definido, Jarvis debe avisar — mismo canal que las alertas del Brain (chat + Panel de Estado),
  no un email aparte que se pierde.
- Esto vive naturalmente junto a la Analítica (§7) — es "costo de infraestructura" en vez de
  "costo por output de agente", misma filosofía de número auditable, no una estimación.

---

## 9. Fuera de alcance (por ahora) — refinado con el rol real de Mar en el proyecto

- **Escribir/modificar código de aplicación en los repos conectados** (solo lectura de señales de
  código). *Aclaración de Mar*: la documentación (specs, HUs, actas) **sí** vive y se escribe en
  el repo — eso no es "tocar código", es exactamente lo que ya está pasando hoy con
  `SPEC_JARVIS.md` en este mismo repo. El límite es el código de la aplicación, no el repo como
  contenedor de documentación.
- **Notificaciones proactivas — ajustado, ya no es 100% "fuera de alcance"**: no se construye
  push/alertas espontáneas de v1, pero sí se agrega un **refresh programado** (no reactivo puro):
  al iniciar sesión del chat, y cada 3 horas entre 7am–7pm (ver Flujo B, §3, y HU-003-JarvisMode
  actualizada). Además, cada sincronización debe **distinguir el ambiente** (`prod` vs.
  `develop`/`development`) del repo que está leyendo — Mar suele trabajar en un entorno de
  pruebas, y un gap de reconciliación en develop no debe tratarse igual que uno en prod.
- Multi-usuario / permisos por proyecto.
- Aplicar automáticamente los ajustes de prompt que sugiere la autoevaluación — siempre pasan por
  aprobación de Mar en v1.
- El bug de overlap CSS y el rediseño React — hallazgo separado, se resuelve en ese esfuerzo (Mar
  ya reconoce que debe ese rediseño/sistema de diseño).

---

## 10. Decisiones resueltas (rondas de aprobación 2026-08-12)

| Tema | Decisión |
|---|---|
| Canal móvil | **PWA** — dentro del rediseño React (§8.1) |
| Auth de repos | **Auth Profiles** — múltiples identidades de Mar (`@imagineapps.co` → Bitbucket org + GitHub personal; `@gmail.com` → Bitbucket personal), no una sola OAuth App ni un PAT manual (§6.2) |
| Autoevaluación | **Multidimensional y continua** (eficiencia, acertividad, formato, calidad) con feedback inmediato por invocación, umbral de **2 invocaciones seguidas** en baja calidad antes de proponer ajuste (§6.8, HU-008-JarvisMode) |
| Estrictez de reconciliación | **Precisión exacta contra el texto de los Acceptance Criteria**, respaldada por tests reales desarrollados en Fase 4 (§6.7) |
| Analítica | Taxonomía completa (§7.1 de Mar + propuestas de Claude) **aprobada y priorizada P0–P3**, unificada en una sola lista |
| Fases del proyecto | Modelo ampliado **Iniciación / Ejecución / Cierre** (§4), extiende (no reemplaza) las 5 fases SDLC actuales |
| HUs | Se generan **siempre con Gimena**, nunca a mano — las de §5 son borrador temporal de Claude (regla de `.claude`) |
| Infraestructura | **Vercel + Redis Marketplace (Upstash)** por ahora; migración a AWS es post-POC, fuera de este spec; se agrega monitoreo de costos (§8.2) |
| Alcance de "tocar código" | Jarvis puede escribir **documentación** en el repo (specs, HUs) — el límite real es el **código de aplicación**, no el repo en sí (§9) |
| Notificaciones | No son push proactivo v1, pero sí hay **refresh programado** (inicio de sesión + cada 3h de 7am–7pm) distinguiendo prod/develop (§9, HU-003-JarvisMode) |

## 11. Pendientes técnicos (no son preguntas para Mar — son tareas de preparación antes/durante la implementación)

- **Investigar el flujo real de Auth Profiles con SSO de Google**: la cuenta `@imagineapps.co` de
  Mar entra vía SSO de Google, no usuario/contraseña propio — hay que confirmar en Fase 2
  (Backend) si eso significa "conectar con Google" en vez de "conectar con GitHub/Bitbucket"
  directamente para ese perfil, y si la org de Bitbucket de Imagine Apps fuerza SSO (§6.2).
- **Registrar o localizar las credenciales de OAuth App** (GitHub/Bitbucket) antes de poder
  implementar Auth Profiles — Mar no tiene esa respuesta today, es tarea de Fase 2.
- **Retención de conversaciones del chat**: sin definir todavía si el historial de sesiones
  cerradas (§6.6) se conserva indefinidamente o expira — no bloquea el diseño, se decide al
  implementar el store de sesiones.
- ~~Regenerar las HUs de §5 con Gimena~~ — **Resuelto** (RUN-001, 2026-08-12): generadas
  invocando el perfil canónico de Gimena dentro de la conversación, sin depender de la
  `ANTHROPIC_API_KEY` del `.env` (sigue falsa a propósito, no es un bloqueo real). Ver
  [`backlog.md`](backlog.md) y [`outputs/HU_RUN-001_2026-08-12.md`](outputs/HU_RUN-001_2026-08-12.md).

---

## 12. Avance de implementación (se actualiza según se construye, no solo al aprobar)

**Backend FastAPI — primer esqueleto (2026-08-12, commit `ffca64a`)**

Verificado por mí (no solo por el reporte del agente que lo construyó): `uvicorn app.main:app`
arranca sin errores, `GET /health` responde `200`, y los 24 endpoints del spec están registrados
en `openapi.json` (confirmado comparando la lista real contra §6.5 de `ARCHITECTURE_JARVIS.md`).

| HU | Estado | Nota |
|---|---|---|
| HU-001/002-JarvisMode (multi-repo) | 🟡 Esqueleto real | Adaptadores GitHub/Bitbucket con `httpx` real (no mocks); falta ejercitarlos contra un repo real y el flujo de Auth Profiles con SSO de Google (§11). **QA 2026-08-13**: se encontraron y corrigieron 2 bugs en `connect_repository` — `environment` faltante ya no se aceptaba silenciosamente server-side (rechaza con `400`), y el mismo repo/environment ya no podía conectarse dos veces (rechaza con `409`) |
| HU-003-JarvisMode (sync programada) | 🟢 Implementado | `app/cron/sync_scheduler.py` — `sync_now()` on-demand + `start_scheduler()` con APScheduler (`hour="7-19/3"`), corre al iniciar la app. Watermark: usa `lastSyncAt` del repo, o ventana de 24h si nunca sincronizó |
| HU-004-JarvisMode (reconciliación) | 🟢 Implementado (matching real) | Parsea `backlog.md` + `outputs/*.md` (formato real de Gimena), unidad = Acceptance Criteria individual, busca `# @ac:HU-XXX-N` / `// @ac:HU-XXX-N` en archivos de test vía los adaptadores de repo. Sin CI conectado: estado `con_test_sin_resultado`, nunca inventa pass/fail. **QA 2026-08-13**: corregido para que un proyecto sin repos conectados devuelva `gaps:[]` con nota explícita, en vez de fabricar gaps sintéticos sobre HUs que ningún repo real respalda |
| HU-005-JarvisMode (timeline) | 🟢 Implementado | `GET /projects/{id}/timeline` |
| HU-006-JarvisMode (Jarvis Chat) | 🟢 Implementado | Loop agéntico completo con las 5 herramientas, versionado de sesión por límite de contexto (umbral 120k tokens, marcado para calibrar). **QA 2026-08-13**: corregidos 2 bugs — `_run_agentic_loop` no envolvía `client.messages.create` en try/except (mismo tipo de regresión que `/agents/invoke`, ahora igualado); el `ChatPanel` del dashboard nunca enviaba `purpose`, por lo que el primer mensaje de cualquier sesión nueva era rechazado con `400` desde la UI real — ambos corregidos y reverificados con curl real |
| HU-007-JarvisMode (Memoria de Mar) | 🟢 Implementado | Dedup por similitud Jaccard (umbral 0.6, marcado para calibrar) |
| HU-008-JarvisMode (autoevaluación) | 🟢 Implementado | Las 4 dimensiones se disparan automáticamente en `invoke_agent_core` (usada por `/agents/{name}/invoke` **y** `/orchestrate`), envuelto en try/except propio para no tumbar la respuesta si la evaluación falla. Detector de 2 invocaciones seguidas bajas conectado a la propuesta de changelog |
| HU-009-JarvisMode (changelog de mejoras) | 🟢 Implementado | `POST /changelog` (propuesta), `POST /changelog/{id}/approve` (aprobación manual, nunca automática), ventana antes/después simétrica, scores reales del `collector`, nunca inventados |
| HU-010-JarvisMode (Analítica) | 🟢 Implementado | `GET /metrics/events` + cada serie agregada trae `eventIds`/`eventsAvailable`; los agregados de antes de este cambio devuelven explícitamente "sin eventos crudos disponibles" en vez de inventar un desglose |
| Auth Profiles (§6.2) | 🟢 CRUD implementado | Falta resolver la investigación de SSO de Google antes de que el flujo de conexión sea real |
| Reescritura completa a Python/FastAPI (§8.0) | 🟢 Completa (MAP + Orchestrator) | El Orchestrator (`orchestrator.js` original: `toolRegistry`, `/toolchain/execute`, `/workflows`, `/system/state`) migró bajo el prefijo `/orchestrator/*` — 9 rutas verificadas, `GET /orchestrator/tools` responde con el tool `map` real |

**Verificado por mí (2026-08-13)**, no solo por el reporte de los agentes: reinstalé dependencias
(`apscheduler` incluido), arranqué `uvicorn` de nuevo, confirmé `/health` y `/orchestrator/tools`
respondiendo con datos reales.

**Nota operativa real encontrada** (no es un bug de código, es un detalle de despliegue a
recordar): `MAP_URL` se autocalcula como `http://localhost:{PORT}` desde `Settings.PORT` (default
heredado de Node: 3001) cuando no se fija explícitamente. Si se arranca `uvicorn` con un puerto
distinto vía `--port` sin también fijar la env var `PORT` al mismo valor, el Orchestrator
llamaría al puerto equivocado al invocarse a sí mismo. Recordar fijar `PORT` en `.env`/entorno de
despliegue igual al puerto real donde corre el servicio.

**Bug real encontrado y corregido (2026-08-13)**: `POST /agents/{name}/invoke` (y por lo tanto
`/orchestrate`, que comparte la misma función interna) no envolvía la llamada al SDK de Anthropic
en manejo de errores — cualquier falla ahí (key inválida, rate limit, timeout) se propagaba como
un `500 Internal Server Error` genérico sin cuerpo JSON, en vez del `{"error": message}` con
status code real que sí devolvía el Express original. Verificado con una invocación real contra
la key falsa del `.env`: antes del fix, `500` sin detalle; después del fix, `401` con el mensaje
exacto de Anthropic. Corregido envolviendo la llamada en `try/except` sobre
`anthropic.APIStatusError`/`anthropic.APIError`.
