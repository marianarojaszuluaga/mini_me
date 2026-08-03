# Orquestrador 360

Orquestador SDLC end-to-end para Imagine Apps: 19 agentes (5 de gestión de proyecto + 14 del
spec-kit de [`ia-hybrid-teams`](../ia-hybrid-teams)) a través de las 5 fases del ciclo de
desarrollo (Planeación → Backend → Frontend → Integración/Calidad → Deploy).

Este repo consolida y corrige un prototipo previo (`minime_AKA_jarvis/outputs/`) que tenía
tres implementaciones paralelas y sin conectar entre sí. Ver "De dónde viene esto" más abajo.

---

## Arquitectura

Dos servicios Express + un dashboard React:

```
orquestrador-360/
├── src/
│   ├── server.js              # MAP: invoca agentes, gestiona proyectos, evalúa outputs
│   ├── orchestrator.js        # Master Orchestrator: registry de "tools", toolchains, workflows
│   ├── agent-evaluator.js     # Rúbrica real de evaluación (pesos por dimensión, por agente)
│   ├── middleware/auth.js     # Autenticación real por API key (no el placebo del prototipo)
│   ├── agents/
│   │   ├── registry.js        # Prompt builder: 5 agentes PM (inline) + 14 spec-kit (desde .md)
│   │   └── spec-kit-agents/   # Copia de ia-hybrid-teams/agents/*.md — ver nota de sincronía
│   └── phases/phaseContracts.js  # Transcripción de ia-hybrid-teams/spec-kit/PHASE_CONTRACTS.md
└── dashboard/                 # React + Vite — consume la API con una App API Key propia
```

**MAP** (`server.js`, puerto 3001) sabe invocar cualquiera de los 19 agentes y evaluar su
output. **Orchestrator** (`orchestrator.js`, puerto 3000) es la capa meta que registra "tools"
(hoy solo `map`) y permite encadenarlos (`/toolchain/execute`) o guardarlos como workflows
reutilizables. Si en el futuro se agregan más tools (Slack, Basecamp, etc.), se registran ahí.

### Por qué dos procesos y no uno

El propósito original del orchestrator era ser una capa neutral que pudiera enrutar a **varios**
tools, no solo a MAP. Mantenerlos separados conserva esa extensibilidad sin acoplar la lógica de
agentes (que vive en MAP) con la lógica de enrutamiento/encadenado (que vive en el orchestrator).

### Principio: agnóstico al ecosistema y al front (confirmado, agosto 2026)

El "cerebro" (agentes + reglas de negocio) no debe saber nada de qué herramienta externa
concreta se usa — Basecamp, n8n, Apps Script, WhatsApp, Slack, o lo que sea el año que viene.
Cada una es un **adaptador intercambiable** detrás de una interfaz común (`toolRegistry` de
`orchestrator.js`), no código bespoke por integración. Mismo principio para el frontend: el
dashboard React es un consumidor más de la API, no el único front posible.

---

## Project Brain: cómo llega un acta al Brain

Gabriela ("guardiana del Project Brain") mantiene, por proyecto, un **Decision Log** y unas
**Alerts** — ver `memory.projectBrain` en cada proyecto. Hay dos formas de alimentarlas, ambas
convergen en el mismo endpoint:

```
Acta creada (Santi, on-demand vía dashboard, O el Apps Script "Proyecto Actas", automático)
        │
        ▼
POST /brain/ingest-acta   { projectName, actaContent, metadata }
        │
        ▼
Gabriela extrae { decisions[], alerts[] } — JSON estricto, no inventa lo que no está en el acta
        │
        ▼
Se agregan a project.memory.projectBrain.decisionLog / .alerts / .meetingLog
```

Si `projectName` no coincide con ningún proyecto existente, se crea uno automáticamente — el
Brain no depende de que el proyecto ya exista en MAP. El dashboard muestra el Brain del proyecto
seleccionado (Decision Log + Alerts) en el panel "🧠 Project Brain".

**Integración con el Apps Script "Proyecto Actas"**: ese script (fuera de este repo, vive en
Google Apps Script) ya genera actas reales desde Calendar + Gemini. Para que también alimenten
el Brain, se le agrega una llamada a este endpoint al final de `generarActaIA()` — ver snippet
y pasos en el mensaje que te compartí, o pídemelo de nuevo si lo perdiste. Requiere 2 Script
Properties nuevas en ese proyecto de Apps Script: `ORQ_BRAIN_URL` (la URL del backend desplegado)
y `ORQ_BRAIN_API_KEY` (una `APP_API_KEY` dedicada para el Apps Script, distinta de la del
dashboard, para poder revocarla por separado).

---

## Qué se corrigió del prototipo original

- **Tres implementaciones duplicadas → una.** `map.js` y `MAP_orchestrator.js` (SQLite, nunca
  conectados a nada) se descartaron. Se consolidó sobre `server.js` + `orchestrator.js`, que eran
  los realmente usados por el frontend.
- **Autenticación real.** El prototipo aceptaba cualquier token de más de 10 caracteres, o
  literalmente `"test-key"`. Ahora `middleware/auth.js` valida contra `APP_API_KEYS` con
  comparación de tiempo constante.
- **La API key de Anthropic ya no viaja al navegador.** El dashboard original pedía la clave de
  Anthropic y la guardaba en `localStorage`. Ahora el dashboard usa una **App API Key** propia
  (una de las `APP_API_KEYS` del backend); la clave de Anthropic vive solo en el `.env` del
  servidor y nunca se acepta ni se reenvía desde el cliente.
- **`agent-evaluator.js` conectado de verdad.** `server.js` reimplementaba una versión inline en
  `/evaluate` en vez de usar esta clase. Ahora la usa directamente, con su rúbrica ponderada por
  agente (y un fallback genérico para los 14 agentes de spec-kit, que no tenían rúbrica propia).
- **Dashboard con datos reales.** `evaluations` ya no es un estado vacío que nunca se llena: hay
  un panel para invocar cualquier agente y evaluar su output, que alimenta el dashboard de calidad
  en vivo. Las fases y la lista de agentes también se cargan desde la API, no hardcodeadas.
- **`/health` sin autenticación**, en ambos servicios — necesario para que un health check de
  Railway/Render no falle con 401 y reinicie el servicio en loop.

---

## Setup local

```bash
npm install
cd dashboard && npm install && cd ..
cp .env.example .env
# editar .env: ANTHROPIC_API_KEY real + al menos un valor en APP_API_KEYS
npm run dev          # levanta MAP (3001) + Orchestrator (3000)
cd dashboard && npm run dev   # levanta el dashboard (5173)
```

El dashboard pide una **App API Key** al iniciar sesión — usa uno de los valores que pusiste en
`APP_API_KEYS`, no tu clave de Anthropic.

---

## Sincronía con ia-hybrid-teams/agents/

`src/agents/spec-kit-agents/*.md` es una **copia** de los 14 archivos canónicos en
`ia-hybrid-teams/agents/`. Se cargan verbatim como system prompt (no se reescriben), para no
inventar comportamiento que no esté documentado ahí. Si se edita un agente en `ia-hybrid-teams`,
hay que volver a copiar el archivo aquí (o apuntar `SPEC_KIT_AGENTS_DIR` en `.env` directo a esa
carpeta para desarrollo local). Nota: `AGENT_REGISTRY.md` en ia-hybrid-teams referencia
`gimena-scheduler.md`, pero el archivo real es `Gina-scheduler.md` — inconsistencia preexistente
en ese repo, no introducida aquí.

---

## Despliegue

Todo corre en Vercel — dos proyectos separados:

- **Dashboard** (`dashboard/`): build estático (Vite). `dashboard/vercel.json` ya define
  build/output. Necesita `VITE_API_URL` apuntando a `https://<backend>.vercel.app/map` (con
  rebuild después de setearla — Vite la hornea en build time, no es una env var runtime).
- **Backend** (raíz del repo, `api/map.js` + `api/orchestrator.js`): **un solo** proyecto Vercel
  sirve MAP bajo `/map/*` y el Orchestrator bajo `/orchestrator/*` (ver `vercel.json` — rewrites +
  el middleware de strip de prefijo en cada Express app). `MAP_URL` en las env vars del proyecto
  debe ser `https://<este-mismo-deployment>.vercel.app/map` para que el Orchestrator le hable al
  MAP real en vez de `localhost`.

**Requiere Redis para persistir datos entre invocaciones.** Sin esto, la app funciona
dentro de un mismo request pero cada proyecto/decisión/alerta se pierde al siguiente cold start —
no es un despliegue real, es una demo de un solo request. Pasos:

1. En el proyecto del backend en Vercel: Storage → Marketplace Database Providers → instalar una
   integración de Redis (Upstash es la más común; puede tener costo según uso/tier — revisa el
   pricing antes de confirmar la integración).
2. Eso inyecta las env vars de Redis automáticamente (`UPSTASH_REDIS_REST_URL` /
   `UPSTASH_REDIS_REST_TOKEN`, o el prefijo `KV_REST_API_*` si es una integración más antigua —
   `src/store.js` acepta ambos).
3. Redeploy para que tome las nuevas env vars.

`@vercel/kv` (el paquete nativo) está deprecado — este repo usa `@upstash/redis` directamente,
que es lo que la integración de Redis del Marketplace realmente expone.

Si en algún momento el volumen de trabajo justifica un servidor con estado real en vez de
funciones serverless (ejecuciones largas, más control), la alternativa sigue siendo un host
persistente (Railway, Render, EC2) corriendo `npm start` — el código de `src/` funciona igual ahí,
solo usa `STORAGE_DIR` (archivos) en vez de Redis y no necesita `api/`, `vercel.json` ni los
prefijos `/map`/`/orchestrator`.

---

## Pendiente conocido

- `npm audit` marca una vulnerabilidad moderada de `esbuild` (solo afecta al dev server de Vite,
  no al build de producción) — requiere subir a Vite 8 (breaking change) para resolverse. No
  bloqueante para este MVP.
- Fase 5 (Deploy) no tiene agentes asignados — ni siquiera en `ia-hybrid-teams/spec-kit`, que
  recomienda crear un "Deployment Operator Agent" a futuro. No se inventó uno aquí.

---

## De dónde viene esto

Prototipo original en `minime_AKA_jarvis/outputs/` (fuera de este repo). Metodología y specs de
agentes/fases en [`ia-hybrid-teams`](../ia-hybrid-teams) (repo de documentación, sin código).
