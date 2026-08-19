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

**Rediseño de IA (2026-08-14, resuelto vía mockup HTML revisado con Mariana antes de tocar
código — ver HU-011-JarvisMode en §5).** El sitemap de abajo reemplaza el anterior: la marca pasa
a **"Mar en internet"** (subtítulo: "Mini me with her smarts and AI"), "Hablar con Jarvis" deja de
ser un ítem de navegación más y se vuelve el **call-to-action principal** del sidebar, y tres
secciones cambian de comportamiento (Proyectos gana un flujo real de listado+creación+detalle,
Analítica pasa a pantalla completa en vez de drill-down flotante, Memoria de Mar pasa a vista
inline en vez de modal):

```
🎯 Mar en internet — sidebar + vistas                ← navegación real, no un menú de páginas sueltas
│
├── [CTA] Hablar con Jarvis — botón destacado arriba del todo, no un ítem más de la lista
│
├── 💬 Vista: Jarvis Chat (default al abrir la app)
│   ├── Conversación multi-turno, con memoria de sesión e inicio/fin explícitos (§6.6)
│   ├── Panel de Estado visible al costado (métricas clave, alertas top) — no desaparece
│   │   mientras chateás, solo se oculta cuando entrás a Analítica (ver abajo)
│   └── Cada respuesta cita su fuente
│
├── 📁 Vista: Proyectos (antes: solo un contador en el Panel de Estado)
│   ├── Estado de lista: grid de tarjetas, una por proyecto — cada tarjeta muestra su propio
│   │   estado (semáforo) y sus propias stats enfocadas (gaps, alertas, decisiones), no un
│   │   número global. Incluye una tarjeta "+ Nuevo proyecto" en la misma grilla — crear un
│   │   proyecto es una acción de esta vista, no algo que solo se pide por chat.
│   └── Estado de detalle (drill-down real, click en una tarjeta): stats de ESE proyecto en
│       grande, reconciliación reciente, repositorios asociados — vuelve a la grilla con un
│       back-link, nunca te saca de la vista Proyectos hacia otra pantalla.
│
├── 📈 Vista: Analítica (antes: drill-down flotante encima del chat)
│   └── Al entrar, la vista Jarvis Chat se cierra por completo (no queda detrás, no hay overlay)
│       y el área principal entera pasa a mostrar todas las series/estadísticas. "Volver al chat"
│       es la única forma de salir — refuerza que es un modo de lectura, no una capa flotante.
│
├── 🧠 Vista: Memoria de Mar (antes: modal)
│   └── Vista propia, siempre visible al entrar (no un modal que tapa el resto) — entendimiento
│       acumulado, preguntas abiertas y correcciones, con creación manual de entradas.
│
└── 🔌 Integraciones — se mantiene como modal (Auth Profiles §6.2, OAuth real §11) — es una
    acción de configuración puntual, no un lugar donde se pasa tiempo, a diferencia de las
    cuatro de arriba.
```

**Decisión explícita (2026-08-13)**: se elimina el drill-down "Invocar Agente" (uso directo/manual
de agentes). El chat de Jarvis es ahora el **único punto de entrada** para invocar agentes — no
una alternativa más. El panel correspondiente (`AgentInvokePanel` en `App.jsx`) era código muerto
sin renderizar (QA T-DS-07) y fue borrado junto con esta referencia del sitemap.

**Principio de UX**: nunca tienes que "ir a otro lado" para tomar una decisión — preguntas en el
chat, ves la consecuencia en el Panel de Estado de la misma pantalla; Proyectos y Memoria de Mar
son vistas de primera clase con su propio flujo, no cosas escondidas detrás de un modal; y
Analítica es intencionalmente el único lugar que **sí** te saca del chat, porque leer 15 series de
tiempo y sostener una conversación compiten por la misma atención.

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
| HU-011-JarvisMode | Rediseño de IA — sidebar, CTA de Jarvis, Proyectos/Memoria de Mar/Dashboard como vistas | F7 — UX/Design system |
| HU-012-JarvisMode | Renombre de los 22 ids de agente a nombres cortos en inglés | F7 — UX/Design system |

**HU-011-JarvisMode — Criterios de Aceptación** (mockup HTML iterado con Mariana en 7 rondas,
2026-08-14, antes de implementar — ver §2 para el sitemap completo). Cada ronda de feedback quedó
resuelta en el mockup antes de tocar código; esto documenta el estado FINAL acordado:

- **2.1 — Interfaz general**
  1. El header del sidebar muestra "Mar en internet" como H1 y "Mini me with her smarts and AI"
     como subtítulo, reemplazando "Orquestrador 360 / 19 agentes · 5 fases del SDLC".
  2. "Hablar con Jarvis" es un botón destacado (color de acento) arriba de las secciones de
     navegación del sidebar — no un ítem más de la lista.
  3. El banner degradado morado/azul del header se elimina por completo — cero `linear-gradient`
     en la navegación principal.
  4. Ningún emoji se usa como ícono funcional en sidebar, chat, tarjetas o modales — todos los
     íconos son SVG de línea del mismo set.
  5. Toda sección (Dashboard, drill-down de Proyectos, estados vacíos) es UN contenedor/card con
     el título adentro — nunca un título flotando arriba de tarjetas sueltas; los stats internos
     de esa sección no llevan su propio borde (evita doble-caja).
  6. El color principal (acento) es configurable, no fijo en código: verde oscuro por default,
     con azul/púrpura/naranja como alternativas — **sin rojo** (reservado para estados de error).
     El control vive en un modal de "Configuración" (ícono de rueda al pie del sidebar, no
     controles sueltos), con tema (auto/claro/oscuro) + color, y un botón "Guardar" explícito —
     el cambio no se aplica hasta confirmar.
  7. El indicador de estado del sidebar (antes un punto estático "Operativo") refleja salud real
     de la plataforma con 3 estados posibles: Operativo (verde), Novedades (ámbar, ej. latencia
     elevada), Caído (rojo) — cada uno con su texto explícito, no solo un color.
- **2.2 — Navegación y vistas**
  1. "Proyectos": grid de tarjetas (semáforo + stats propias: gaps/alertas/decisiones) + tarjeta
     "+ Nuevo proyecto" en la misma grilla.
  2. Click en una tarjeta abre el detalle de ESE proyecto dentro de la misma vista (back-link a
     la grilla, nunca una URL ni un modal distinto).
  3. "Dashboard" (renombrado de "Analítica") oculta por completo la vista de Jarvis Chat al
     entrar — "Volver al chat" es la única salida. Orden fijo de secciones: (1) Estadísticas del
     proyecto, (2) Últimos agentes usados + desglose de outputs, (3) Salud del sistema. Un
     selector de proyecto arriba gobierna las secciones 1 y 2; cada título de sección lleva un
     badge de alcance ("Proyecto X" vs. "Todos los proyectos") para que nunca se confunda un
     número por-proyecto con uno global — Salud del Sistema es la única sección deliberadamente
     global.
  4. "Memoria de Mar" es una vista simple (sin categorías por tipo) con un badge fijo de respaldo:
     "Respaldado automáticamente en Obsidian — carpeta `Orquestrador 360 - Memoria de la App`,
     cada 3h" (ver §11, sync ya implementado).
  5. "Integraciones" se mantiene como modal — incluye GitHub, Bitbucket, Google (OAuth real) y
     **Basecamp**.
- **2.3 — Jarvis Chat**
  1. Soporta múltiples conversaciones abiertas a la vez, mostradas como tabs arriba del chat;
     cada tab lleva un chip visible con el proyecto al que pertenece.
  2. El panel de estado lateral separa visualmente "Esta conversación" (turnos, tokens de ESTA
     sesión) de "Sistema" (gaps totales, alertas — todos los proyectos) con un divisor claro —
     nunca mezclados en la misma lista.
- **2.4 — Proyectos: repos, ramas y estados vacíos**
  1. Un proyecto puede tener **N repositorios**, cada uno con **N ramas monitoreadas** — ambos
     listados vienen de `project.repositories[]` real (no un solo repo/rama quemado). Botón
     "Agregar repositorio" siempre visible en la sección.
  2. Un proyecto sin repos ni Basecamp vinculado muestra dos CTAs explícitos — "Integrar Repo" e
     "Integrar Basecamp" — en vez de secciones vacías o en blanco.
  3. El modal de "Conectar repositorio" exige un **Proyecto** (campo obligatorio, marcado `*`) —
     un repo SIEMPRE pertenece a un proyecto, nunca queda suelto — además de proveedor, Auth
     Profile, `owner/repo`, ambiente, y un selector de **múltiples ramas** (chips, no una sola).
  4. El modal de "Nuevo proyecto" incluye nombre, descripción, vínculo opcional a Basecamp, y
     referencia al mismo flujo de conectar repositorio (sin duplicar sus campos).
  5. En el drill-down de proyecto, "Sprint abierto" incluye un link "Ver en Basecamp".
- **2.5 — Manejo de errores / estados vacíos**
  1. Un proyecto sin gaps/alertas/decisiones muestra `0` explícito en cada stat, nunca la tarjeta
     oculta ni un guion genérico.
  2. La vista Proyectos sin proyectos todavía muestra solo la tarjeta "+ Nuevo proyecto".

**HU-012-JarvisMode — Criterios de Aceptación** (resuelto en código, no solo mockup — 2026-08-14):

- **2.1** Los 22 agentes tienen un id corto en inglés por defecto: `gime` (ex-gimena), `gabi`
  (sin cambio), `gaby` (ex-gabriela), `santi` (sin cambio), `dani` (ex-daniel), `sofi`
  (ex-architect), `mafe` (ex-fullstack-developer), `isa` (ex-flutter-developer), `fer`
  (ex-data-engineer), `vale` (ex-auditor), `lore` (ex-fixed-errors), `gina`
  (ex-gina-scheduler), `moni` (ex-qa-integrator), `rena` (ex-integration), `sara`
  (ex-sonar-quality-gate), `tami` (ex-mcp-integration-tester), `vane` (ex-test-video-recorder),
  `xime` (ex-unit-test-standards-reviewer), `pau` (ex-quality-report-generator), `mila`
  (ex-milestone-writer), `diana` (ex-dod-definer), `cami` (ex-capacity-reconciler).
- **2.2** Los archivos `.md` fuente en `src/agents/spec-kit-agents/`/external agents NO cambian
  de nombre — el id es solo la clave de lookup (`agent_registry.py`'s `SPEC_KIT_FILES`/
  `EXTERNAL_AGENT_FILES`), no el archivo en disco.
- **2.3** El id viejo ya no funciona: `POST /agents/{id_viejo}/invoke` responde `400 Unknown
  agent`, no un fallback silencioso al nuevo id.

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

- ~~Investigar el flujo real de Auth Profiles con SSO de Google~~ / ~~Registrar credenciales de
  OAuth App~~ — **Resuelto en código (2026-08-14), pendiente de credenciales reales de Mariana.**
  Respuesta de Mariana a "¿SSO de Google o OAuth directo?": **"AMBOS"** — implementado un flujo
  real de Authorization Code para **los tres** proveedores en paralelo (GitHub, Bitbucket, Google),
  no uno en vez del otro. Nuevo `app/routers/oauth.py`:
  `GET /auth-profiles/oauth/{provider}/start` (redirige a la pantalla real de login/consentimiento
  del proveedor; autentica por `?app_key=` ya que una navegación de nivel superior no puede llevar
  el header `Authorization`) y `GET /auth-profiles/oauth/{provider}/callback` (intercambia el
  `code` real por un token vía `httpx`, resuelve la identidad real de la cuenta, y hace upsert de
  un `AuthProfile` con `auth_method="oauth"`). `AuthProfile` ahora separa `access_token`/
  `refresh_token` (nunca expuestos por `GET /auth-profiles` — `to_public_dict()` los excluye) del
  `token_ref` del formulario manual, que sigue existiendo como fallback para cualquier proveedor
  sin OAuth App configurado. Los adaptadores de GitHub/Bitbucket ahora resuelven el token real de
  un `AuthProfile` OAuth en vez de solo leer una env var por nombre.
  **Verificado en vivo real** (no solo `py_compile`): con `GITHUB_OAUTH_CLIENT_ID/SECRET` sin
  configurar (todavía no los tenemos), el botón real "Conectar con GitHub" del dashboard navega de
  verdad a `http://localhost:3001/auth-profiles/oauth/github/start` y el backend responde un `501`
  real y explícito (`"OAuth App for 'github' is not configured yet..."`) — no un éxito fingido.
  `app_key` inválido → `403` real. `GET /auth-profiles` confirmado sin `access_token`/
  `refresh_token` en el JSON de respuesta.
  **Basecamp agregado como 4to proveedor (2026-08-14)**, mismo patrón real de Authorization Code —
  Mariana pasó la doc real de `bc-api` (github.com/basecamp/bc-api). Basecamp usa OAuth de
  37signals Launchpad, distinto de un OAuth2 genérico en dos puntos: `type=web_server` es
  obligatorio tanto en el redirect de autorización como en el intercambio de token (no es parte
  del estándar, es específico de 37signals), y no hay concepto de `scope` — en su lugar, hace
  falta un paso extra real, `GET https://launchpad.37signals.com/authorization.json`, para
  resolver el `account_id` que toda llamada futura a la API de Basecamp necesita
  (`https://3.basecampapi.com/{account_id}/...`), eligiendo la cuenta con `product == "bc3"`. Ese
  `account_id` se guarda en el campo `scope` del `AuthProfile` (`"account_id:{id}"`) — no hay un
  campo dedicado y es el único lugar real donde ese valor pertenece. Verificado en vivo: con
  `BASECAMP_OAUTH_CLIENT_ID/SECRET` sin configurar, el botón real "Conectar con Basecamp" pega
  contra el backend real y devuelve el mismo `501` explícito que los otros tres, no un éxito
  fingido.
  **Acción pendiente de Mariana** (bloqueante solo para probar el flujo completo, no para el
  código): registrar 4 OAuth Apps reales — GitHub OAuth App, Bitbucket OAuth consumer, Google
  OAuth 2.0 Client, y un Basecamp integration en launchpad.37signals.com/integrations — cada uno
  con su callback apuntando a `{BACKEND_PUBLIC_URL}/auth-profiles/oauth/{provider}/callback`
  (`BACKEND_PUBLIC_URL` en `Settings`, hoy `http://localhost:3001` por default) y pasarme los 8
  valores (`GITHUB_OAUTH_CLIENT_ID/SECRET`, `BITBUCKET_OAUTH_CLIENT_ID/SECRET`,
  `GOOGLE_OAUTH_CLIENT_ID/SECRET`, `BASECAMP_OAUTH_CLIENT_ID/SECRET`) para conectarlos y volver a
  verificar en vivo con un login real, igual que se hizo con la key de DeepSeek.
  **Nota sobre sprints/estadísticas de proyecto (§2, Dashboard) — Resuelto (Fase E, post-2026-08-14)**:
  `app/services/basecamp_client.py`'s `get_active_sprint()` + `GET /projects/{id}/sprint`
  (`app/routers/projects.py`) ya leen el to-do list activo real de Basecamp vía el `AuthProfile`
  OAuth vinculado, devolviendo `501` explícito (nunca datos fabricados) si falta el link o el
  profile. Consumido por `AnalyticsDrillDown.jsx` (tiles reales `tasks_done`/`tasks_total`, o un
  `sprintError` explícito en vez de un número inventado).
- ~~Retención de conversaciones del chat~~ — **Reinterpretado y resuelto (2026-08-14).** Mariana
  pidió, en vez de una política de expiración: "obligame a comenzar y terminar de forma digital
  en el programa" — el chat ahora fuerza un inicio y un cierre deliberados, en vez de dejar
  sesiones abiertas indefinidamente o cortadas solo por límite de contexto (§6.6 versionado por
  tokens sigue existiendo, es un mecanismo aparte). Cambios: `session_manager.open_or_resume`
  ahora rechaza reanudar un `conversation_id` con `status="closed"` (antes lo permitía
  silenciosamente); nuevo `POST /jarvis/chat/{conversation_id}/close` (`session_manager.close_session`,
  idempotente); `ChatPanel.jsx` ya no deriva el `purpose` del primer mensaje — exige una pantalla
  de "dale un propósito a esta conversación" antes de habilitar el input, y agrega un botón
  "Terminar sesión" siempre visible que llama al nuevo endpoint y bloquea el panel hasta que se
  defina un propósito nuevo. Verificado en vivo con `uvicorn`+`vite` reales: `curl` confirmó que
  postear a una sesión recién cerrada devuelve `400` con el mensaje explícito; en el navegador
  real, "Iniciar sesión" → mensaje real respondido por `claude-sonnet-4-6` → "Terminar sesión" →
  el panel vuelve a exigir un propósito nuevo antes de aceptar más texto. La retención en sí
  (cuánto tiempo se guardan sesiones `closed`) sigue sin definirse — no bloquea nada, es limpieza
  de storage a futuro, no parte de esta HU.
- ~~Sincronizar memorias de forma permanente en Obsidian, en un nuevo espacio~~ — **Resuelto
  (2026-08-14).** Aclarado con Mariana: "ambos y las de los proyectos" — cubre tanto la memoria
  del asistente Claude (ya vivía en `Obsidian Vault/Claude Memory/`, sin tocar) como la memoria
  PROPIA de la app (Memoria de Mar + Project Brain por proyecto), que hasta ahora solo existía
  dentro de `storage/*.json`, sin ningún reflejo durable fuera del repo. Nuevo
  `scripts/sync_memories_to_obsidian.py`: lee `storage/mar-memory.json` y `storage/projects.json`
  directamente (sin necesidad de levantar el servidor) y regenera markdown en un espacio nuevo y
  separado, `Obsidian Vault/Orquestrador 360 - Memoria de la App/` (`mar-memory.md` + un archivo
  por proyecto bajo `projects/` con decision log, alertas, meeting log y el desglose real de gaps
  de reconciliación por status). Es un exportador de snapshot, idempotente — cada corrida
  regenera los archivos desde el estado actual, no algo para editar a mano. **Verificado en
  vivo**: corrido contra el `storage/` real de este repo, generó 6 archivos de proyecto reales
  (con datos reales, ej. 98 gaps reales de "Proyecto Demo UI") + `mar-memory.md` (0 entradas hoy,
  correcto — Mar Memory está vacía en este momento) — confirmado leyendo los archivos ya escritos
  en el vault, no solo el mensaje de éxito del script. **Pendiente, no bloqueante**: no está
  conectado a un scheduler todavía — se corre a mano por ahora; conectarlo al cron de 3h de
  `app/cron/sync_scheduler.py` es un paso razonable una vez que se confirme que este formato de
  snapshot es el que Mariana quiere usar, no algo que asumí que hacía falta ya.
- ~~Regenerar las HUs de §5 con Gimena~~ — **Resuelto** (RUN-001, 2026-08-12): generadas
  invocando el perfil canónico de Gimena dentro de la conversación, sin depender de la
  `ANTHROPIC_API_KEY` del `.env` (sigue falsa a propósito, no es un bloqueo real). Ver
  [`backlog.md`](backlog.md) y [`outputs/HU_RUN-001_2026-08-12.md`](outputs/HU_RUN-001_2026-08-12.md).
- ~~Conectar DeepSeek para el tier barato de modelos~~ — **Resuelto (2026-08-14).** Mariana pasó
  la key correcta (`sk-jw0yWgYF4FONeY73NOWDbw`), válida en `admin-llm.imagineapps.co` para el
  modelo `deepseek-chat`. `agent_registry.py`'s `MODEL_IDS` vuelve a separar tiers
  (`"haiku": "deepseek-chat"`, `"sonnet": "claude-sonnet-4-6"`). **Hallazgo técnico real**: cada
  virtual key de Mariana en ese proxy solo autoriza un modelo (confirmado por el propio `403` del
  proxy) — el primer intento de resolverlo pasando `extra_headers={"x-api-key": ...}` en la
  llamada a `client.messages.create()` **no funciona**, verificado en vivo (403 persistente) y
  reproducido con un script standalone fuera de FastAPI. La solución real es instanciar un
  `AsyncAnthropic` **separado** por key/modelo (`Settings.api_key_for_model()` en
  `app/core/config.py`, usado en `invoke_agent_core` de `app/routers/agents.py`). Verificado en
  vivo end-to-end contra el servidor real: `POST /agents/test-video-recorder/invoke` (tier haiku)
  respondió con `"model":"deepseek-chat"` y salida real; `POST /agents/gimena/invoke` (tier
  sonnet) respondió con `"model":"claude-sonnet-4-6"` real, ambos en la misma sesión de prueba.

---

## 12. Avance de implementación (se actualiza según se construye, no solo al aprobar)

**HU-011-JarvisMode (rediseño de IA) — 🟢 Implementado.**
Mariana reportó "el UI está super inconsistente" y pidió comparar contra el sistema Geist real
(Figma) antes de tocar código — el Dev Mode MCP Server de Figma no estaba disponible en esa
sesión (requiere la app de escritorio con Dev Mode habilitado), así que se usó `design-tokens.css`
(ya extraído de Geist en una ronda anterior) como fuente de verdad en su lugar. Encontrado y
confirmado como causa raíz de la inconsistencia: `dashboard/src/styles.css`'s `.btn-primary` estaba
pintado en verde (`--ds-green-800`) y se reusaba para navegación, creación y aprobación por igual —
en Geist real el color "primary" es neutro (texto/fondo invertidos) y el verde queda solo para
estados de éxito. Se construyó un mockup HTML autocontenido (sin React) con la IA revisada — sidebar
reemplaza el banner degradado, "Hablar con Jarvis" como CTA, Proyectos con grid+creación+detalle,
Analítica a pantalla completa, Memoria de Mar inline, iconos SVG en vez de emoji — aprobado tras 7
rondas de feedback (config de color, reorden del Dashboard, multi-repo/ramas, CTAs de integración
faltante, chats múltiples, etc.). El refactor real sobre `dashboard/src/` **ya está completo y
verificado en vivo** (varias rondas posteriores, hasta 2026-08-19): `Sidebar.jsx` con badge de
conteo + los 6 íconos lineales reales (`icons.jsx`, sin emoji en toda la app); `AppShell.jsx` +
`app-shell.css` (max-width 1600px centrado, ya no se estira en monitores anchos); `ProjectsView.jsx`
(grid + subtítulo dinámico "N bloqueados" + CTAs de integración faltante); `ProjectDetailDrillDown.jsx`
con 3 tabs reales (Fases y agentes, Project Brain, Repositorios asociados), cada uno con tarjetas
reales (no texto plano — se corrigió una regresión real donde una limpieza de CSS anterior había
borrado por error los estilos de `.phase-nav-item`/`.agent-tag`); componente `Modal/Modal.jsx`
compartido migrado a Integraciones, Configuración, Nuevo proyecto, Conectar repositorio y Vincular
Basecamp (antes 3 implementaciones de modal distintas); tipografía de dos niveles Nunito/Inter
agregada 2026-08-19 (Mariana: tamaños grandes en Nunito, ≤11px en Inter); chat con pestañas de
sesión reales (ver HU-006 abajo). Los criterios de aceptación completos están en la HU de arriba
(§5).

**HU-012-JarvisMode (renombre de agentes) — 🟢 Implementado (2026-08-14).** A diferencia de
HU-011, esto sí se implementó directamente en el backend real (Mariana: "sí reemplazalos"), no
solo en el mockup. Cambiados los 22 ids en `agent_registry.py` (`PM_AGENT_PROMPTS`,
`SPEC_KIT_FILES`, `EXTERNAL_AGENT_FILES`, `AGENT_MODEL_CONFIG`), `phase_contracts.py` (agente por
fase/sub-fase), `agents.py`'s `STEP_TO_AGENT`, `projects.py`'s ingesta de actas,
`agent_evaluator.py`'s `EVALUATION_CRITERIA`, `jarvis_chat/tools.py`'s descripción de
`invoke_agent`, y `evaluate_invocation.py`'s sets de contrato JSON/HU-format. Los archivos `.md`
fuente NO se renombraron (es solo el id de lookup). **Verificado en vivo**: `GET /agents` devuelve
los 22 ids nuevos; `POST /agents/gimena/invoke` (id viejo) responde `400 Unknown agent`; `POST
/agents/vale/invoke` (renombrado de `auditor`) completó una llamada real a `claude-sonnet-4-6` con
salida y evaluación reales.

**Analítica robustecida — outputs reales por agente/proyecto (2026-08-14).** A pedido de Mariana
("debemos tener outputs de todos los agentes"), investigué `record_output()`
(`app/services/metrics/collector.py`) y encontré que **no tenía ningún caller en todo el
sistema** — el contador de outputs (HU/plan/acta/QA) era código muerto, así que "# de outputs" en
el Dashboard solo podía estar vacío o inventado. Corregido: `OutputCount` ahora lleva
`project_id`/`agent_name`; `OutputType` se amplió con `qa_run` y `pull_request`; y
`invoke_agent_core` (`app/routers/agents.py`) llama `record_output()` de verdad después de cada
invocación exitosa (`gime`→hu, `gabi`→plan, `santi`→acta, `vale`/`sara`/`xime`→qa_run). `GET
/metrics/output-counts` y `/metrics/summary` aceptan `?project_id=` para escopar el resultado a UN
proyecto (antes solo devolvían el total global — el mismo gap que Mariana señaló para
"Estadísticas de Proyectos"). **Pendiente, documentado explícitamente en vez de fingido**:
`pull_request` quedó en el enum pero SIN wiring desde `sync_scheduler.py` — los adapters de
GitHub/Bitbucket traen TODAS las PRs del repo (sin filtro "desde la última sync" como sí tienen los
commits), así que sumar ese conteo cada 3h duplicaría/triplicaría el número en vez de reflejar PRs
nuevas; hace falta que el adapter soporte un delta real antes de conectarlo. Verificado en vivo:
`POST /agents/gime/invoke` + `/agents/vale/invoke` contra un `project_id` real, seguido de `GET
/metrics/output-counts?project_id=...`, devolvió `hu=1` y `qa_run=1` reales, cada uno con
`eventIds` reales para drill-down.

**Backend FastAPI — primer esqueleto (2026-08-12, commit `ffca64a`)**

Verificado por mí (no solo por el reporte del agente que lo construyó): `uvicorn app.main:app`
arranca sin errores, `GET /health` responde `200`, y los 24 endpoints del spec están registrados
en `openapi.json` (confirmado comparando la lista real contra §6.5 de `ARCHITECTURE_JARVIS.md`).

| HU | Estado | Nota |
|---|---|---|
| HU-001/002-JarvisMode (multi-repo) | 🟢 Implementado | Adaptadores GitHub/Bitbucket con `httpx` real (no mocks), CRUD completo en `app/routers/repositories.py` (conectar/listar/sync/borrar/agregar rama). Falta el flujo de Auth Profiles con SSO de Google (§11). **QA 2026-08-13**: se encontraron y corrigieron 2 bugs en `connect_repository` — `environment` faltante ya no se aceptaba silenciosamente server-side (rechaza con `400`), y el mismo repo/environment ya no podía conectarse dos veces (rechaza con `409`). **BUG-009**: `sync_one_repository`/`sync_now` ahora comparten la misma sincronización real entre connect, retry manual y el cron de 3h |
| HU-003-JarvisMode (sync programada) | 🟢 Implementado | `app/cron/sync_scheduler.py` — `sync_now()` on-demand + `start_scheduler()` con APScheduler (`hour="7-19/3"`), corre al iniciar la app. Watermark: usa `lastSyncAt` del repo, o ventana de 24h si nunca sincronizó |
| HU-004-JarvisMode (reconciliación) | 🟢 Implementado (matching real) | Parsea `backlog.md` + `outputs/*.md` (formato real de Gimena), unidad = Acceptance Criteria individual, busca `# @ac:HU-XXX-N` / `// @ac:HU-XXX-N` en archivos de test vía los adaptadores de repo. Sin CI conectado: estado `con_test_sin_resultado`, nunca inventa pass/fail. **QA 2026-08-13**: corregido para que un proyecto sin repos conectados devuelva `gaps:[]` con nota explícita, en vez de fabricar gaps sintéticos sobre HUs que ningún repo real respalda |
| HU-005-JarvisMode (timeline) | 🟢 Implementado | `GET /projects/{id}/timeline` |
| HU-006-JarvisMode (Jarvis Chat) | 🟢 Implementado | Loop agéntico completo con las 5 herramientas, versionado de sesión por límite de contexto (umbral 120k tokens, marcado para calibrar). **QA 2026-08-13**: corregidos 2 bugs — `_run_agentic_loop` no envolvía `client.messages.create` en try/except (mismo tipo de regresión que `/agents/invoke`, ahora igualado); el `ChatPanel` del dashboard nunca enviaba `purpose`, por lo que el primer mensaje de cualquier sesión nueva era rechazado con `400` desde la UI real — ambos corregidos y reverificados con curl real. **2026-08-19**: pestañas de sesión reales agregadas — `GET /jarvis/sessions` + `GET /jarvis/sessions/{conversation_id}` listan/cargan sesiones reales; `ChatPanel.jsx` renderiza un `chat-tabs` real por sesión (no tabs client-only fingidos) |
| HU-007-JarvisMode (Memoria de Mar) | 🟢 Implementado | Dedup por similitud Jaccard (umbral 0.6, marcado para calibrar). **2026-08-19**: `MarMemoryDrillDown.jsx` agrupa las entradas por día real (Hoy/Ayer/fecha) en vez de lista plana |
| HU-008-JarvisMode (autoevaluación) | 🟢 Implementado | Las 4 dimensiones se disparan automáticamente en `invoke_agent_core` (usada por `/agents/{name}/invoke` **y** `/orchestrate`), envuelto en try/except propio para no tumbar la respuesta si la evaluación falla. Detector de 2 invocaciones seguidas bajas conectado a la propuesta de changelog |
| HU-009-JarvisMode (changelog de mejoras) | 🟢 Implementado | `POST /changelog` (propuesta), `POST /changelog/{id}/approve` (aprobación manual, nunca automática), ventana antes/después simétrica, scores reales del `collector`, nunca inventados |
| HU-010-JarvisMode (Analítica) | 🟢 Implementado | `GET /metrics/events` + cada serie agregada trae `eventIds`/`eventsAvailable`; los agregados de antes de este cambio devuelven explícitamente "sin eventos crudos disponibles" en vez de inventar un desglose. **2026-08-14**: `record_output()` conectado a invocaciones reales (antes sin callers) y `OutputCount` escopado por `project_id` — ver detalle abajo. **Post-2026-08-14**: `GET /projects/{id}/sprint` + `basecamp_client.py` agregan el sprint real de Basecamp (tareas hechas/total) al panel de Analítica, ya no solo eventos internos |
| HU-011-JarvisMode (rediseño de IA) | 🟢 Implementado | Sidebar + AppShell + 3 tabs reales en el drill-down de proyecto + `Modal` compartido + tokens Nunito/Inter (2026-08-19) — ver detalle en §12 arriba |
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

**Verificación final end-to-end post-QA Round 1 (2026-08-13, misma sesión — CORRECTIONS-PLAN P0 y
design system)**, ejecutada leyendo el código en disco y corriendo el sistema real, no solo
confiando en los resúmenes de los 3 trabajos paralelos:

- **P0 reconciliación — RESUELTO y confirmado en vivo.** Leí `app/services/brain/reconciliation.py`
  completo: ya no existe `_AC_CHECKBOX_RE`; el parser real recorre las subsecciones `### 2.1`/`2.2`/`2.3`
  de Gimena (`_extract_bullets` para 2.1/2.2, `_extract_table_rows` para la tabla de 2.3) y genera
  `acId = "{huId}-2.{subsección}.{índice}"`. Arranqué `uvicorn app.main:app --port 8099` y corrí
  `POST /projects/Proyecto_1786462085119/reconciliation/run` con curl real (`HTTP 200`): **98 gaps**
  cubriendo las 10 HUs (16, 7, 12, 11, 6, 13, 9, 8, 5, 11 ACs por HU-001..010), **0 `no_reconciliable`**,
  los 98 en `sin_test` (correcto: aún no hay tests con `# @ac:`/`// @ac:` en los repos conectados). Antes
  del fix esto habría sido 10 gaps `no_reconciliable` en bloque — confirmado que el P0 del
  `CORRECTIONS-PLAN-2026-08-13.md` está cerrado, no solo "reportado como cerrado".
- **Design system unificado — RESUELTO y confirmado en vivo.** `design-tokens.css:126` define
  `--font-sans: "Inter", GeistSans, ...`; `dashboard/index.html` trae el `<link>` real a Google Fonts
  para Inter 400/500/600/700. `npm run build` compiló limpio (`45 modules transformed`). Levanté
  `npm run dev` (puerto 5173) y con el navegador real: `document.fonts.check('16px Inter')` → `true`,
  y `getComputedStyle(h1).fontFamily` → `"Inter, GeistSans, \"GeistSans Fallback\", -apple-system, sans-serif"`
  (Inter cargada y de hecho aplicada, no solo referenciada). El "Failed to fetch" visible en pantalla es
  solo porque el backend de esta verificación corría en el puerto 8099 y no en el puerto que el dashboard
  llama por defecto — no relacionado con el fix.
- **"Solo chat" como punto de entrada — RESUELTO.** Grep de `AgentInvokePanel` en todo el repo: cero
  referencias en código (`App.jsx`, `dashboard/src`); solo aparece en la nota de decisión de este mismo
  archivo (línea ~94) y en los documentos históricos de QA. Confirmado también en el DOM real renderizado
  (`document.body.innerHTML` sin match de `AgentInvokePanel`/"Invocar Agente").
- **ENV-006 y GAP-005 — RESUELTOS (2026-08-13, ronda posterior).** Se conectó una
  `ANTHROPIC_API_KEY` real (proxy LiteLLM de Mariana, `admin-llm.imagineapps.co`, modelo
  `claude-sonnet-4-6`), probada en vivo con una llamada real que devolvió respuesta real —
  `ANTHROPIC_BASE_URL` nuevo en `Settings`, usado por los 6 sitios donde se instancia
  `AsyncAnthropic`/`AgentEvaluator` (antes fijos a la API directa de Anthropic). Todos los modelos
  hardcodeados (`claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`) se unificaron a
  `claude-sonnet-4-6` — la key de Mariana solo tiene acceso a ese modelo, así que el tier
  barato/caro de `agent_registry.py` queda colapsado hasta que haya una key con más alcance o se
  conecte un segundo proveedor (DeepSeek, mencionado pero bloqueado por una key inválida en el
  proxy — pendiente de que Mariana la regenere). `check_degradation()` (GAP-005) verificado en
  vivo: sembradas 2 evaluaciones bajas reales, devolvió `True`; una tercera evaluación (buena)
  reseteó la racha correctamente — la conexión a `changelog.create_proposal()` ya estaba en el
  código de una ronda anterior, solo faltaba probarla con datos reales.

**BUG-009 — RESUELTO (2026-08-13).** `Repository` (app/schemas/project.py) ahora tiene
`syncStatus: "never"|"synced"|"error"` y `lastError`, actualizados por
`app/cron/sync_scheduler.py` (nueva función reusable `sync_one_repository`, compartida entre
conectar-repo, "Reintentar" y el cron de 3h). Conectar un repo dispara el digest histórico real de
inmediato (ya no un TODO) y el resultado real queda en la respuesta. Verificado en vivo con la API
de GitHub real (sin mocks): un repo público sincronizó de verdad (`syncStatus:"synced"`); un repo
inexistente devolvió `syncStatus:"error"` con el mensaje real de GitHub (`404 Not Found`), y
"Reintentar" repitió la misma llamada real. Confirmado también visualmente en el navegador: pill
"⚠️ Error de sincronización" con el mensaje real + botón "Reintentar", y "Sin sincronizar todavía"
para repos conectados antes de este fix (default `syncStatus="never"`, no fabricado).
