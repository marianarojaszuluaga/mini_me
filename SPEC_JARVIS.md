# SPEC — Jarvis Mode (chat conversacional, multi-repo, memoria de Mar, autoevaluación, analítica)
> **Status**: Draft para aprobación — sin código todavía
> **Creado**: Agosto 2026
> **Depende de**: `SPEC.md` (Orquestrador 360 base — MAP + Orchestrator + 22 agentes + 5 fases)
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

> **Regla de `.claude` (confirmada por Mar)**: las HUs siempre se generan con el agente
> **Gimena**, nunca escritas a mano por fuera del sistema. Las que siguen abajo son un
> **borrador de Claude, no HUs reales** — quedan marcadas `[DRAFT-BY-CLAUDE]` y deben
> **regenerarse invocando a Gimena** (`POST /agents/gimena/invoke`) apenas haya una
> `ANTHROPIC_API_KEY` real configurada — hoy el `.env` tiene una key falsa (confirmado en la
> auditoría de la sesión anterior), así que Gimena no puede invocarse todavía. Ver pregunta
> abierta en §11.

### F1 — Multi-repo por proyecto [DRAFT-BY-CLAUDE — pendiente de regenerar con Gimena]

**HU-JARVIS-01**: Como usuaria, quiero asociar uno o varios repositorios a un proyecto, para que
Jarvis lea señales reales de trabajo sin que yo las reporte a mano.

**Acceptance Criteria**
- [ ] `POST /projects/:id/repositories` agrega `{provider, owner, repo}`.
- [ ] Un proyecto admite N repos de distintos providers.
- [ ] Valida acceso de lectura antes de guardar.
- [ ] `DELETE /projects/:id/repositories/:repoId` desconecta sin borrar historial ya ingerido.

**HU-JARVIS-02**: Como usuaria, quiero ver qué repos están conectados y cuándo sincronizaron por
última vez.

---

### F2 — Project Brain vivo con el código como fuente de verdad [DRAFT-BY-CLAUDE — pendiente de regenerar con Gimena]

**HU-JARVIS-03**: Como usuaria, quiero que la actividad de cada repo se sincronice al iniciar
sesión y periódicamente durante mi horario de trabajo, distinguiendo prod de develop, para que el
Brain no dependa de que yo pegue actas a mano ni mezcle ambientes.

**Acceptance Criteria**
- [ ] Trigger: al iniciar sesión del chat, y cada 3 horas entre 7am–7pm — no en horario nocturno.
- [ ] Cada repo conectado declara su `environment` (`prod` | `develop`); el digest y cualquier
  alerta de reconciliación quedan etiquetados con ese ambiente.
- [ ] `POST /brain/ingest-event` generaliza `/brain/ingest-acta` (se mantiene como alias).
- [ ] Sin actividad → sin entrada (no hay ruido).

**HU-JARVIS-04**: Como usuaria, quiero que el sistema **reconcilie** lo que el backlog/actas
declaran como hecho contra lo que el repo realmente tiene, y me alerte cuando no coincida.

**Acceptance Criteria**
- [ ] El Auditor corre la reconciliación como parte del ciclo diario (o on-demand desde el chat).
- [ ] Un gap detectado genera **siempre** una alerta explícita en el Brain — nunca se diluye en
  el resumen general.
- [ ] La alerta identifica qué HU/backlog item y qué evidencia (o ausencia de ella) en el repo.
- [ ] Falso positivo conocido y aceptado inicialmente: trabajo hecho fuera del repo rastreado
  (ej. configuración manual) se marcará como gap aunque esté bien — se documenta como limitación,
  no se intenta resolver en v1.

**HU-JARVIS-05**: Como usuaria, quiero un timeline unificado por proyecto (actas + commits + PRs
+ reconciliación) para auditar de dónde salió cada decisión del Brain.

---

### F3 — Jarvis Chat (conversacional, no formulario) [DRAFT-BY-CLAUDE — pendiente de regenerar con Gimena]

**HU-JARVIS-06**: Como usuaria, quiero hablarle a Jarvis en una conversación de ida y vuelta
(como este chat), no llenar un formulario de una sola pregunta, para poder profundizar con
preguntas de seguimiento sin repetir contexto.

**Acceptance Criteria**
- [ ] `POST /jarvis/chat` acepta `{conversationId?, message}` — si no hay `conversationId`, crea
  una sesión nueva.
- [ ] El historial de la conversación se persiste y se reinyecta en cada turno (no es stateless).
- [ ] Dentro de un turno, Jarvis puede invocar herramientas (leer Brain, leer timeline, invocar
  un agente) antes de responder — es un loop agéntico, no una sola llamada a Claude.
- [ ] Cada afirmación cita su fuente; si falta información, lo dice explícitamente.
- [ ] Una pregunta sin proyecto explícito ("¿qué está bloqueado esta semana?") se resuelve
  cruzando todos los proyectos activos.

---

### F4 — Memoria de Mar [DRAFT-BY-CLAUDE — pendiente de regenerar con Gimena]

**HU-JARVIS-07**: Como usuaria, quiero que Jarvis recuerde entre conversaciones qué ya entiendo
del sistema y qué me falta decidir, para no tener que repetirle contexto sobre mí misma cada vez.

**Acceptance Criteria**
- [ ] Existe un store de Memoria de Mar separado de cada Project Brain (no por proyecto).
- [ ] El chat puede escribir ahí cuando la usuaria confirma/corrige algo sobre el sistema mismo.
- [ ] Se carga como contexto en cada conversación nueva.
- [ ] Es visible y editable manualmente en su propia pantalla — Mar puede corregir una entrada.

---

### F5 — Autoevaluación y mejora [DRAFT-BY-CLAUDE — pendiente de regenerar con Gimena]

**HU-JARVIS-08**: Como usuaria, quiero que cada output de agente se evalúe en varias dimensiones
concretas (no un solo score genérico), y que el feedback quede disponible de inmediato — no solo
como una tendencia que se nota semanas después.

**Decisión (reemplaza el modelo de "umbral de N semanas" del borrador anterior)**: la evaluación
es **multidimensional y continua**, no un disparador por tiempo transcurrido:
- **Eficiencia**: ¿el output resuelve lo pedido sin pasos/contexto de más?
- **Acertividad**: ¿la respuesta es correcta/relevante respecto a lo que se preguntó?
- **Formato**: ¿respeta el contrato esperado (JSON estricto donde aplica, estructura de HU, etc.)?
- **Calidad general**: la rúbrica ya existente de `AgentEvaluator` (completeness, clarity,
  adherence, actionability, alignment) se mantiene como quinta dimensión, no se reemplaza.

**Acceptance Criteria**
- [ ] Cada invocación de agente se evalúa en las 4 dimensiones (eficiencia, acertividad, formato,
  calidad) inmediatamente después de producirse el output — no en un job separado y posterior.
- [ ] El resultado por dimensión queda visible de inmediato en el dashboard/chat (feedback
  inmediato), además de acumularse en la serie de tiempo para Analítica (§7).
- [ ] Cuando una dimensión cae por debajo de un umbral definido en una sola invocación, se marca
  esa invocación puntual — no se espera a un patrón sostenido para que sea visible.
- [ ] El sistema puede sugerir (no aplicar solo) un ajuste de prompt cuando una dimensión se
  mantiene baja en invocaciones sucesivas — queda como propuesta para que Mar la apruebe.

**HU-JARVIS-09**: Como usuaria, quiero un changelog de mejoras del sistema mismo (qué se ajustó,
por qué, y qué cambió en las métricas después), para tener evidencia de que mejora con el tiempo.

---

### F6 — Analítica (evidencia de que esto es real) [DRAFT-BY-CLAUDE — pendiente de regenerar con Gimena]

**HU-JARVIS-10**: Como usuaria, quiero un panel de números concretos —no solo un dashboard de
estado— que demuestre uso real y mejora real del sistema, porque la retroalimentación más dura
que recibí fue que no hay evidencia de eso.

**Acceptance Criteria** — taxonomía completa aprobada en §7 (§7.1 pedido por Mar + §7.2 propuesta
aprobada + §7.3 ya definido):
- [ ] Número de usos: invocaciones totales, por agente, por proyecto, por semana.
- [ ] Número de outputs por tipo: HUs generadas, specs generados, planes de trabajo, actas
  procesadas, evaluaciones corridas, reconciliaciones ejecutadas — contador independiente por tipo.
- [ ] Tasa de aceptación por tipo de output (usado tal cual vs. descartado/regenerado).
- [ ] Costo por output (tokens/USD reales de la API de Anthropic).
- [ ] Tiempo ahorrado estimado — marcado explícitamente como aproximado, nunca como medición exacta.
- [ ] Distribución de uso por proyecto/cliente.
- [ ] Tendencia semana a semana de cada contador (no solo el acumulado).
- [ ] Calidad en el tiempo por agente, en las 4 dimensiones (§6.8), en serie.
- [ ] Reconciliación: gaps código↔spec detectados vs. cerrados, por proyecto y en el tiempo.
- [ ] Comparación "antes vs. después": mismo tipo de tarea en dos fechas, con score y tiempo.
- [ ] Ninguna métrica se muestra sin poder hacer drill-down a los eventos crudos que la componen.

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

Reemplaza el modelo de "N semanas de degradación sostenida" del borrador anterior (ver HU-JARVIS-08
para el detalle de las 4 dimensiones: eficiencia, acertividad, formato, calidad):

- Cada invocación de agente corre las 4 evaluaciones **inmediatamente**, no en un job semanal
  aparte — el feedback está disponible en el momento, no días después.
- Cada dimensión se acumula en su propia serie de tiempo (§6.5 `agentEvaluations`, ahora con
  4 sub-scores en vez de un único `avgScore`).
- Una caída puntual por debajo de un umbral en **cualquier** dimensión se marca de inmediato en
  esa invocación — no espera un patrón de varias semanas para ser visible.
- **Decidido**: **2 invocaciones seguidas** por debajo del umbral en una misma dimensión disparan
  la propuesta de ajuste de prompt — siempre pendiente de aprobación de Mar, nunca autoaplicada.
- El changelog (`HU-JARVIS-09`) registra qué se cambió y qué pasó con cada una de las 4
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
HU-JARVIS-10) — el orden de prioridad es de construcción, no de qué se le oculta a nadie.

---

## 8. Stack tecnológico

| Capa | Ya existe | Nuevo para Jarvis Mode |
|---|---|---|
| Backend | Express, `@anthropic-ai/sdk`, `@upstash/redis` | Cliente GitHub (`@octokit/rest`), cliente Bitbucket, cron, loop agéntico con tool-calling para el chat |
| Frontend | React + Vite (rediseño ya planeado) | Componente de chat multi-turno, pantalla Memoria de Mar, pantalla Analítica (gráficas de series de tiempo) |
| Storage | Redis (prod) / filesystem (local) | Nuevas keys/colecciones: memoria de Mar, métricas de series de tiempo — sin cambiar el motor de storage |
| Auth | App API Keys | OAuth Apps de GitHub/Bitbucket |

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
  al iniciar sesión del chat, y cada 3 horas entre 7am–7pm (ver Flujo B, §3, y HU-JARVIS-03
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
| Autoevaluación | **Multidimensional y continua** (eficiencia, acertividad, formato, calidad) con feedback inmediato por invocación, umbral de **2 invocaciones seguidas** en baja calidad antes de proponer ajuste (§6.8, HU-JARVIS-08) |
| Estrictez de reconciliación | **Precisión exacta contra el texto de los Acceptance Criteria**, respaldada por tests reales desarrollados en Fase 4 (§6.7) |
| Analítica | Taxonomía completa (§7.1 de Mar + propuestas de Claude) **aprobada y priorizada P0–P3**, unificada en una sola lista |
| Fases del proyecto | Modelo ampliado **Iniciación / Ejecución / Cierre** (§4), extiende (no reemplaza) las 5 fases SDLC actuales |
| HUs | Se generan **siempre con Gimena**, nunca a mano — las de §5 son borrador temporal de Claude (regla de `.claude`) |
| Infraestructura | **Vercel + Redis Marketplace (Upstash)** por ahora; migración a AWS es post-POC, fuera de este spec; se agrega monitoreo de costos (§8.2) |
| Alcance de "tocar código" | Jarvis puede escribir **documentación** en el repo (specs, HUs) — el límite real es el **código de aplicación**, no el repo en sí (§9) |
| Notificaciones | No son push proactivo v1, pero sí hay **refresh programado** (inicio de sesión + cada 3h de 7am–7pm) distinguiendo prod/develop (§9, HU-JARVIS-03) |

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
- **Regenerar todas las HUs de §5 con Gimena** en cuanto haya una `ANTHROPIC_API_KEY` real en
  `.env` (hoy es una key falsa, confirmado en la auditoría de la sesión anterior) — bloqueante
  para cerrar Fase 1 (Iniciación → Planning) de este mismo proyecto.
