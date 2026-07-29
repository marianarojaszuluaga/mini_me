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

- **Dashboard → Vercel.** Es un build estático (Vite). Configurar `VITE_API_URL` apuntando al
  host donde corra el backend. `dashboard/vercel.json` ya define build/output.
- **API (MAP + Orchestrator) → host persistente** (Railway, Render, EC2). Vercel es serverless
  con límite de tiempo de ejecución por función — no es buen fit para un orquestador que puede
  encadenar varias invocaciones de agentes en una sola request. `STORAGE_DIR` debe apuntar a un
  volumen persistente en ese host: si es efímero, `projects.json`/`activity.log`/`workflows.json`
  se pierden en cada redeploy.

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
