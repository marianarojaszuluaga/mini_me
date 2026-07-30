# SPEC — Orquestrador 360
> **Status**: MVP construido y desplegado — pendiente de credenciales reales para uso en producción
> **Creado**: Julio 2026

---

## Overview

**Qué es**: Un orquestador que invoca los 19 agentes Claude definidos por la metodología
`ia-hybrid-teams` (5 agentes de gestión de proyecto + 14 del spec-kit técnico) a través de las
5 fases del SDLC (Planeación → Backend → Frontend → Integración/Calidad → Deploy), con evaluación
de calidad real por output y un Project Brain que se mantiene actualizado a partir de actas de
reunión.

**Por qué**: `ia-hybrid-teams` es documentación pura — define agentes, fases y contratos pero
"no implementa código" (textual en `spec-kit/README.md`). No existía ninguna implementación
runtime de esa metodología. Existía además un prototipo (`minime_AKA_jarvis/outputs/`) con la
idea correcta pero tres versiones duplicadas y sin conectar, autenticación placebo, y sin relación
con los agentes/fases de `ia-hybrid-teams`.

**Quién lo usa**: equipo de Imagine Apps, vía dashboard web o invocación directa por API.

---

## Scope

### In scope (esta versión)
- Invocar cualquiera de los 19 agentes con su prompt canónico (los 14 de spec-kit se leen
  verbatim de `agents/*.md`, no se reinterpretan).
- Modelar las 5 fases del SDLC y qué agente(s) participa(n) en cada una, según
  `spec-kit/PHASE_CONTRACTS.md`.
- Evaluar la calidad de un output de agente con una rúbrica real y ponderada.
- Recibir actas de reunión (manual vía Santi, o automático vía el Apps Script externo
  "Proyecto Actas") y que Gabriela extraiga decisiones/alertas hacia el Project Brain de un
  proyecto.
- Dashboard web para operar todo lo anterior sin usar `curl`.
- Desplegable en Vercel (serverless) o en un host persistente (Railway/Render/EC2) sin cambiar
  código de negocio.

### Out of scope (por ahora)
- Fase 5 (Deploy) no tiene agentes — ni siquiera en el `ia-hybrid-teams` original, que reconoce
  el hueco y sugiere a futuro un "Deployment Operator Agent". No se inventó uno aquí.
- Multi-tenant / roles y permisos granulares (hoy es un solo nivel de acceso vía API key).
- Tests automatizados (unit/integration) — la verificación de esta versión fue manual (ver
  "Estado actual").
- El proyecto "Bancecamp" (Scrum Assistant sobre Basecamp) que vive en la raíz de
  `minime_AKA_jarvis/` es un proyecto **no relacionado**, fuera de este spec.

---

## Features

### F1 — Registro e invocación de agentes

**US-01**: Como usuaria, quiero invocar cualquiera de los 19 agentes con un input libre, para
obtener su output sin tener que copiar/pegar su prompt manualmente.

**US-02**: Como usuaria, quiero que los 14 agentes de spec-kit usen exactamente el `.md` de
`ia-hybrid-teams/agents/` como su comportamiento, para no tener dos fuentes de verdad divergentes.

**Acceptance Criteria**
- [x] `GET /agents` lista los 19 agentes con su familia (`pm` o `spec-kit`).
- [x] `POST /agents/:name/invoke` rechaza agentes desconocidos (400).
- [x] Los 14 agentes spec-kit cargan su prompt desde archivo, no hardcodeado.
- [ ] **Verificado con una respuesta real de Claude** — todas las pruebas de esta sesión usaron
  una API key falsa; el flujo llega hasta la llamada a Anthropic pero nunca se confirmó un
  output real coherente.

### F2 — Orquestación por fases

**US-03**: Como usuaria, quiero que el sistema sepa qué agente corresponde a cada paso de cada
fase, para no tener que recordarlo yo.

**US-04**: Como usuaria, quiero que el sistema rechace invocar un agente que no está asignado a
esa fase según el contrato documentado, para no desviarme del proceso acordado.

**Acceptance Criteria**
- [x] `GET /phases` refleja `PHASE_CONTRACTS.md` (5 fases, inputs/outputs/agentes reales).
- [x] `POST /orchestrate` valida phase+step contra un mapa explícito y contra
  `phaseContract.agents` antes de invocar.
- [x] El progreso y el timeline del proyecto se actualizan tras cada invocación.
- [ ] Cobertura completa de pasos por fase — hoy `STEP_TO_AGENT` cubre un subconjunto
  representativo de pasos, no exhaustivo de cada fase.

### F3 — Evaluación de calidad

**US-05**: Como usuaria, quiero una puntuación objetiva y ponderada del output de un agente, no
solo "se ve bien", para poder confiar en el resultado antes de usarlo.

**Acceptance Criteria**
- [x] `POST /evaluate` usa `AgentEvaluator` (rúbrica real por dimensión, no una versión inline
  duplicada).
- [x] Los 14 agentes spec-kit (sin rúbrica propia) caen a una rúbrica genérica en vez de fallar.
- [ ] Verificado con un output real evaluado por Claude (mismo bloqueo que F1: sin key real).

### F4 — Project Brain (actas → decisiones/alertas)

**US-06**: Como usuaria, quiero que el contenido de un acta de reunión (generada manualmente o
por el Apps Script de Calendar) termine reflejada como decisiones y alertas del proyecto, para no
perder ese contexto en un documento suelto.

**Acceptance Criteria**
- [x] `POST /brain/ingest-acta` crea el proyecto si no existe, invoca a Gabriela con un prompt
  dedicado, y persiste `decisionLog`/`alerts`/`meetingLog`.
- [x] Validación de input (400 si falta `projectName` o `actaContent`).
- [x] Dashboard muestra el Brain del proyecto seleccionado (Decision Log + Alerts).
- [ ] Integración real con el Apps Script — se entregó el snippet (`enviarActaAlBrain`), pero
  **no está instalado en el script en producción** todavía.
- [ ] Extracción real verificada — mismo bloqueo de API key falsa que F1/F3.

### F5 — Acceso vía dashboard

**US-07**: Como usuaria, quiero operar todo lo anterior desde una interfaz web, sin depender de
`curl` o Postman.

**Acceptance Criteria**
- [x] Login con App API Key propia (nunca la key de Anthropic — no vive en el navegador).
- [x] Fases, agentes, proyectos y Brain cargan de la API real, no de datos hardcodeados.
- [x] Panel para invocar cualquier agente y evaluar su output desde la UI.
- [ ] Probado en producción contra el backend desplegado (solo probado localmente, frontend
  y backend en el mismo equipo).

---

## Arquitectura (resumen — detalle completo en README.md)

- **MAP** (`src/server.js`): invocación de agentes, proyectos, evaluación, ingestión de actas.
- **Master Orchestrator** (`src/orchestrator.js`): registry de "tools" (hoy solo `map`),
  toolchains, workflows guardados.
- **Storage** (`src/store.js`): archivos localmente; Redis (Upstash vía Vercel Marketplace) en
  serverless — sin Redis, el estado no sobrevive entre invocaciones en Vercel.
- **Dashboard** (`dashboard/`): React + Vite.
- **Despliegue**: un proyecto Vercel para MAP+Orchestrator (prefijos `/map` y `/orchestrator`),
  otro para el dashboard. Alternativa sin cambios de código: host persistente + `npm start`.

---

## Estado actual — qué funciona y qué falta

### Funciona y está verificado (con pruebas reales durante esta sesión)
- Backend consolidado arranca sin errores (local y en Vercel), auth real rechaza/acepta tokens
  correctamente, health checks públicos.
- Los 19 agentes y las 5 fases se listan correctamente y coinciden con `ia-hybrid-teams`.
- CRUD de proyectos end-to-end (API + dashboard en navegador).
- `/orchestrate` valida fase/step contra el contrato y ya no depende de `localhost` internamente.
- Dashboard: login, fases, agentes, proyectos, Brain panel — todo probado en navegador contra el
  backend local.
- Backend desplegado en Vercel responde en `/map/health` y `/orchestrator/health` (tras corregir
  un crash real: el filesystem de las funciones es de solo lectura salvo `/tmp`).
- Dashboard desplegado en Vercel (`VITE_API_URL` ya apunta al backend desplegado).
- Push al repo canónico en GitHub (`marianarojaszuluaga/mini_me`).

### Construido pero NO verificado con una API key real
- Ningún agente ha producido todavía un output real de Claude en este build completo — todas las
  pruebas usaron `ANTHROPIC_API_KEY` falsa a propósito. La lógica llega hasta la llamada a
  Anthropic y falla ahí (esperado), pero la calidad/formato real del output no se ha confirmado.
- `/evaluate` y `/brain/ingest-acta` (parseo del JSON que devuelve Claude) — mismo bloqueo.

### Pendiente, acción tuya requerida
- **`ANTHROPIC_API_KEY` y `APP_API_KEYS` en Vercel** — no los configuré yo (entrar API keys
  reales no es algo que yo deba hacer, ni aunque me las pases). Sin esto, el backend desplegado
  solo puede responder `/health`.
- **Redis (Upstash) en el proyecto de Vercel** — sin esto, cada invocación pierde el estado
  (proyectos, decisiones, alertas) del anterior. Puede tener costo según uso/tier: revisar antes
  de confirmar la integración.
- **Snippet de Apps Script** — entregado, no instalado en el script real todavía.
- **Push a Bitbucket** de la copia en `ia-hybrid-teams` — commiteado localmente, no pusheado (a
  la espera de tu confirmación, es un repo compartido con el equipo).

### Gaps conocidos, no bloqueantes
- Sin tests automatizados — toda la verificación de este MVP fue manual.
- `npm audit`: vulnerabilidad moderada de `esbuild` (solo dev server de Vite, no el build de
  producción) — requiere Vite 8 (breaking) para resolver.
- `STEP_TO_AGENT` cubre pasos representativos por fase, no exhaustivos.
- Fase 5 (Deploy) sin agentes — hueco heredado de `ia-hybrid-teams`, no de esta implementación.

---

## Open Questions

- [NEEDS CLARIFICATION] ¿Qué pasos adicionales por fase (más allá de los ya mapeados en
  `STEP_TO_AGENT`) quieres que cubra `/orchestrate`?
- [NEEDS CLARIFICATION] ¿Redis vía Vercel Marketplace es aceptable en costo, o prefieres validar
  el flujo completo en un host persistente (sin costo de Redis) antes de decidir?
- [NEEDS CLARIFICATION] ¿Quién más del equipo va a tener una `APP_API_KEY` propia (dashboard vs.
  Apps Script vs. otros clientes futuros)?
