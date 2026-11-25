# Auditoría UX · Operativa · Técnica — Mini me (Orquestrador 360)

- **Fecha:** 2026-11-25
- **Audiencia:** ingeniero senior que va a llevar el producto de idea a producto replicable para empresas y PMs.
- **Público objetivo:** Forward Deployed Project Manager (supongo "Forward Deployed Project Manager"; si era otro rol, ajusto el encuadre).
- **Prioridades declaradas:** (1) todo en el mismo lugar · (2) gobernanza y observabilidad basadas en datos · (3) gestión sin esfuerzo · (4) sentirse como un superhéroe con Jarvis.
- **Método:** lectura de código (`app/`, `dashboard/src/`), suite de tests backend, build del dashboard, y recorrido visual a 1280 px y 368 px con Playwright sobre backend y Vite locales con un proyecto de prueba. **No** probé Jarvis contra la API real de Anthropic (clave falsa), ni OAuth, ni producción.

---

## 1. Veredicto

La base técnica es más sólida de lo que la UI deja ver: 108/108 tests backend pasan, el build compila, el backend tiene fallback a filesystem cuando Redis falla, y el sistema de tokens de color es semántico (cero hex en componentes).

Pero hoy **la promesa de "gobernanza con datos" se rompe en la primera pantalla**. Tres cosas lo causan:

1. **El semáforo y los "gaps" dicen "en riesgo" por falta de instrumentación, no por realidad.** Un proyecto nuevo y vacío aparece en verde.
2. **Jarvis ejecuta acciones de escritura sin confirmación** (invocar agentes, escribir memoria) y el publicador escribe en Basecamp sin revisión.
3. **El shell no funciona en teléfono** y la pantalla central del proyecto está en español literal con un selector en inglés alrededor.

Un PM que vea el semáforo verde en un proyecto sin datos, o una publicación automática a un cliente que no aprobó, deja de confiar en la herramienta. En ese punto la gobernanza deja de ser una ventaja.

---

## 2. Estado medido

| Área | Resultado | Evidencia |
|---|---|---|
| Tests backend | ✅ 108 / 108 pasan | `pytest -q` |
| Build dashboard | ✅ compila (JS 324 kB, 98 kB gzip) | `npm run build` |
| Tests frontend | ❌ ninguno; no hay scripts de test ni E2E | `dashboard/package.json` |
| CI | ❌ no existe `.github/` | `ls .github` |
| Catálogo de agentes | ⚠️ **26** en disco y en el registry; **22** en el prompt de la tool de Jarvis y en `SPEC_JARVIS.md`; **19** en `README.md` | `agent_registry.list_agents()` → 26 |
| i18n (claves ES vs EN) | ✅ 274 / 274 paridad | `i18n/locales/*.json` |
| i18n (uso real) | ❌ `ProjectDetailDrillDown.jsx` (1 166 líneas, la pantalla principal de proyecto) tiene **1** llamada a `t()` | grep |
| Reducción de movimiento | ❌ 0 reglas `prefers-reduced-motion` | grep |
| Targets táctiles ≥ 44 px | ❌ 1 coincidencia en todo el CSS | grep |
| Elementos clicables no nativos | ⚠️ tarjeta de proyecto (`pv-card`) es un `div onClick` | `ProjectsView.jsx` |
| Responsive del shell | ❌ grid fijo `232px 1fr`, 0 media queries en `app-shell.css` y `sidebar.css` | medido: en 368 px el contenido queda en **136 px** |
| Colores | ✅ 0 hex en CSS de componentes; tokens en `design-tokens.css` | grep |

**Nota sobre `apple-design`:** el CLAUDE.md pide basar toda auditoría de UX en la familia de skills `apple-design`, instaladas en `~/.claude/skills/apple-design*`. **En este entorno no están instaladas** (solo `session-start-hook` y `synced`). No pude correr el pase completo. Apliqué los criterios del restraint pass que el propio CLAUDE.md enumera: colores semánticos ✅, un solo acento ⚠️ (el acento es personalizable en Settings; hay que decidir si es una feature o ruido), producto real mostrado ✅ (sin placeholders abstractos), targets ≥ 44 pt ❌, `prefers-reduced-motion` ❌. Conviene instalar la skill y repetir esta auditoría con ella.

---

## 3. Hallazgos P0 — bloquean la promesa de gobernanza

### P0-1 · El semáforo invierte la señal
- **Causa técnica.** `app/services/brain/reconciliation.py:383-388` asigna `sin_test` si el AC no tiene enlace `@ac:` y `con_test_sin_resultado` si lo tiene. **Nunca emite `cumple` ni `no_cumple`**, porque no hay CI conectado (comentario en líneas 41-45). El resultado es que todo AC cuenta como gap.
- **Causa en UI.** `ProjectsView.jsx` `semaphoreFor`: gaps ≥ 3 → *Bloqueado*; ≥ 1 → *Atención*; 0 → *En curso* (verde). Los gaps son todo lo que no es "cumple", así que cualquier proyecto con HUs queda en rojo o ámbar por construcción. Y un proyecto **sin datos** queda en verde.
- **Evidencia.** Proyecto recién creado, sin repos ni HUs: la tarjeta muestra **"On track"** verde y `0 gaps / 0 alerts / 0 decisions` ([desktop-projects.png](./desktop-projects.png)).
- **Impacto.** El PM aprende en una semana que el semáforo no significa nada. Ese es el peor resultado posible para una herramienta de gobernanza.
- **Fix.** Separar estados: `sin datos` (gris), `sin evidencia` (ámbar suave, con conteo y enlace a qué falta), `incumple` (rojo, solo con evidencia de fallo). Nunca verde sin datos. Mostrar la regla del semáforo en un tooltip. Mientras no haya CI, la métrica debe llamarse "AC sin test enlazado", no "gaps".

### P0-2 · Jarvis escribe sin confirmación y Minime publica solo
- **Causa técnica.** En `app/services/jarvis_chat/tools.py`, `invoke_agent` (llamada a LLM, costo, escritura de outputs) y `write_mar_memory` (escritura persistente) se resuelven dentro del loop agéntico. `app/routers/jarvis_chat.py` no tiene ningún gate: la búsqueda de `confirm|approv|human` no devuelve nada.
- **Causa de publicación.** `app/services/basecamp_publisher.py` `render_sprint_started/closed` agrega "Publicado automáticamente por Minime" (líneas 112 y 132). Publica en un tablero de Basecamp, que suele ser visible para el cliente, sin revisión humana.
- **Impacto.** Una frase ambigua puede disparar agentes y reescribir la memoria del sistema. Y un cliente puede ver publicaciones que nadie aprobó. Para "gobernanza" esto es un problema de diseño, no de cosmética.
- **Fix.**
  - Patrón **propose → preview → approve** para toda acción que escriba fuera del sistema o tenga costo: Basecamp, memoria, invocaciones de agente.
  - Log de auditoría por acción: quién, qué, cuándo, con qué fuente.
  - Publicaciones en modo *borrador* por defecto, con vista previa del payload.

### P0-3 · Jarvis no tiene el catálogo real de sus agentes
- `tools.py:97` dice "22 real MAP agents" como texto fijo. El registry carga **26**. El modelo enruta con esa descripción, así que no conoce el catálogo completo.
- `README.md` dice 19. Tres números distintos para la misma cosa.
- **Fix.** Generar la descripción de la tool desde `agent_registry.list_agents()` en tiempo de ejecución. Unificar la documentación con una sola fuente.

### P0-4 · El shell no funciona en teléfono
- Medido a 368 px: sidebar **232 px fijos**, contenido **136 px**. El chat queda recortado y el botón "Start session" queda fuera de pantalla ([phone-chat.png](./phone-chat.png)).
- No hay media queries en `app-shell.css` ni en `sidebar.css`. El QA de la ronda 1 ya había probado 368 px.
- **Fix.** Por debajo de ~900 px: sidebar como drawer o barra inferior. Composer a ancho completo. Esto importa aunque el uso principal sea escritorio, porque el PM revisa el estado desde el celular en tránsito.

### P0-5 · Idioma mezclado y la pantalla central sin traducir
- En una misma pantalla conviven "Talk to Jarvis", "Dashboard", "Integrations", "Mar's Memory" (EN) con "Ciclo de vida" y "Operativo" (ES hardcoded) y "Phase 1 · iniciando" ([desktop-projects.png](./desktop-projects.png)).
- `ProjectDetailDrillDown.jsx`: **1** llamada a `t()` en 1 166 líneas. Fases, Brain, Repos, Basecamp y Timeline están en español literal. Es la pantalla que más usa un PM.
- El botón **"Eliminar proyecto"** en realidad **archiva** (lo dice el modal, `ProjectDetailDrillDown.jsx` ~línea 1114). Un PM con miedo a perder datos no va a leer el modal. Renombrar a "Archivar".
- **Fix.** Pasar todo a i18n. Agregar regla de lint `no-literal-string` (o similar) en CI para que no vuelva a pasar.

---

## 4. Hallazgos P1 — fricción y riesgo técnico

- **P1-1 · Dos modelos de auth visibles para el usuario.** Login con email/contraseña y "App API Key (avanzado)". El mensaje de error en `App.jsx` le pide al usuario "usá la opción avanzada". El botón de Google está deshabilitado (`landing-google-btn disabled`). Un PM no debería ver el concepto `APP_API_KEYS`. **Fix:** cuenta única; las API keys solo en Settings para uso técnico.
- **P1-2 · N+1 en la lista de proyectos.** `ProjectsView.load()` pide `getReconciliation` por cada proyecto en cada carga y después de cada actualización. Con 30 proyectos son 31 requests. **Fix:** endpoint `/projects/summary` con gaps, alertas y decisiones ya agregados en backend.
- **P1-3 · Tarjeta de proyecto no accesible.** `pv-card` es un `div` con `onClick`: no recibe foco por teclado ni se anuncia. `handleSelect` no tiene `catch`, así que un fallo al abrir el proyecto es silencioso. **Fix:** `<button>` o enlace; manejo de error visible.
- **P1-4 · Primer uso con fricción y sin briefing.** Jarvis arranca con "Before starting, give this conversation with Jarvis a purpose" y un composer. No hay nada que el PM vea antes de preguntar ([desktop-chat.png](./desktop-chat.png)). **Fix:** la home debería ser "Hoy" (ver §6).
- **P1-5 · Crear proyecto es pobre.** Nombre, descripción y "Asignado a" como texto libre. Fase fija en 1. Sin fechas, sin equipo, sin plantilla. El "owner" no es un miembro real, así que no hay permisos. **Fix:** miembros y roles por proyecto; fechas opcionales; plantilla.
- **P1-6 · La sincronización cada 3 h no corre en el despliegue.** `app/main.py:104` arranca APScheduler en el `startup` de FastAPI. El despliegue es Vercel serverless: `vercel.json` solo reescribe rutas y no define `crons`. El propio README reconoce que el scheduler "se beneficiaría" de un host persistente. *Verificado por lectura de configuración, no en producción.* **Fix:** Vercel Cron que llame a un endpoint, o un worker persistente.
- **P1-7 · Persistencia efímera sin aviso en UI.** Sin Redis, `app/core/storage.py` cae a filesystem, que en Vercel se pierde entre invocaciones. `/health` devuelve `"storage": "filesystem"`, pero la UI no lo muestra. **Fix:** banner o indicador de modo de almacenamiento en Settings.
- **P1-8 · La reconciliación depende de una convención de archivos.** `reconciliation.py:100-102` lee `backlog.md` y `outputs/*.md` desde `workspacePath` o `REPO_ROOT`. Solo funciona si el cliente usa el formato de HUs de este repo. **Esto es el bloqueo principal para replicar a empresas.** **Fix:** entidad *Work Item* con conector a Jira, Linear o Azure DevOps. Los archivos pasan a ser un conector más.
- **P1-9 · CORS abierto.** `main.py` usa `allow_origins=["*"]` aunque existe `FRONTEND_URL` en settings. Endpoints que escriben y JWT viajan sin restricción de origen. (Seguridad, no UX, pero va en la misma lista.)
- **P1-10 · Sin red de seguridad automática.** Cero tests de frontend, sin CI, `npm audit` con una vulnerabilidad moderada de esbuild pendiente (README). Para una herramienta que escribe en clientes, esto debe cerrarse antes de vender.

**Ya resuelto (verificado en código, no lo reporto como abierto):** el duplicado de repos al mismo proyecto devuelve 409 (`app/routers/repositories.py:150`), que era S1 en la ronda 1 de QA.

---

## 5. Comparación con herramientas de gestión de proyectos

**Lo que tienen Asana, Linear, Jira, ClickUp, Monday o Basecamp y Mini me no:**

1. **Unidad de trabajo.** Una tarea o issue con owner, estado, fecha y prioridad. Hoy no existe entidad "tarea" en la UI. Hay HUs en markdown y cards de Basecamp como espejo.
2. **Plan contra realidad.** Fechas, hitos con vencimiento, baseline y forecast. Hoy el Timeline es un log de eventos, no un plan.
3. **Roles y permisos por proyecto.** Miembros, invitados y viewers. Hoy el owner es texto libre.
4. **Vistas filtrables y guardables.** Lista, tablero y calendario. Hoy hay un grid y un kanban de fase de solo lectura.
5. **Notificaciones y bandeja "para mí".** No hay centro de notificaciones en UI.
6. **Búsqueda y filtros entre proyectos.**
7. **Integraciones con lo que ya usan las empresas.** Jira, Linear, Azure DevOps, Asana, Slack o Teams. Hoy: GitHub, Bitbucket, Basecamp y Google.
8. **Reporte exportable de estado semanal.** Parcial: actas y release notes existen, pero no un status report de portafolio.

**Lo que Mini me tiene y ninguna de esas herramientas tiene: conservarlo y explotarlo.**

- **Citas de fuente en cada respuesta de Jarvis** ("Fuentes citadas"). Es el patrón de gobernanza más útil del producto.
- **Decision log y alertas extraídos de actas** (Project Brain). Es un RAID log automático.
- **Memoria de Mar** (glosario vivo) y **evaluación de agentes** por rúbrica: observabilidad del propio sistema.
- **Trazabilidad HU ↔ test** con `@ac:`. Es un concepto potente, pero hoy no produce resultados reales por falta de CI.

---

## 6. Pensado para un FDPM: el flujo de la mañana

Lo que un FDPM necesita en los primeros 2 minutos del día: **qué cambió desde ayer, qué espera mi decisión y qué está bloqueado.** Hoy la app abre en Jarvis vacío y le pide un "propósito". Eso es trabajo para el PM.

**Propuesta de home: "Hoy".**
- **Decisiones pendientes** de aprobación (incluye P0-2).
- **Bloqueos y riesgos nuevos**, con fuente.
- **Cambios desde la última vez** por proyecto, en lenguaje de negocio, no de tokens.
- **Acciones de Jarvis esperando aprobación**, con botón aprobar o rechazar.
- Jarvis queda como barra de comandos (⌘K) y como respuesta a preguntas, no como pantalla de entrada.

**Ajustes a Jarvis para que se sienta como "Jarvis":**
- **Proactivo:** briefing diario y alerta cuando un proyecto cambia de estado.
- **Acciones con vista previa y deshacer**, no ejecución directa (P0-2).
- **Rail del estado de sesión:** reemplazar "Tokens usados" (métrica de ingeniería) por "acciones pendientes", "decisiones nuevas esta semana" y "bloqueos abiertos".
- Lo que ya hace bien: citar fuentes, decir "no lo sé" cuando la tool devuelve `found: false`. No lo pierdan al rediseñar.

---

## 7. Plan de acción

**Sprint 1 — confianza (≈ 1 semana).** Son cambios pequeños con impacto alto.
1. Semáforo con estados `sin datos` / `sin evidencia` / `incumple`; nunca verde sin datos. *(P0-1)*
2. Gate de confirmación para `invoke_agent`, `write_mar_memory` y la publicación a Basecamp, con vista previa. *(P0-2)*
3. Catálogo de agentes generado desde el registry, y una sola cifra en la documentación. *(P0-3)*
4. i18n completa de `ProjectDetailDrillDown`; "Archivar" en lugar de "Eliminar". *(P0-5)*

**Sprint 2 — uso diario.**
5. Responsive: sidebar como drawer por debajo de ~900 px; composer a ancho completo. *(P0-4)*
6. Home "Hoy" con decisiones pendientes, bloqueos y cambios.
7. Endpoint de resumen del portafolio para quitar el N+1. *(P1-2)*
8. Tarjetas como `button` o enlace; foco visible; `prefers-reduced-motion` en todo movimiento nuevo.

**Sprint 3–4 — replicable a empresas.**
9. Entidad *Work Item* con conector a Jira o Linear. Los archivos `backlog.md` pasan a ser un conector. *(P1-8, el bloqueo principal)*
10. Cuenta única, miembros y roles por proyecto; API keys solo para uso técnico. *(P1-1, P1-5)*
11. Planificación: fechas, hitos y forecast simple.
12. Scheduler en Vercel Cron o worker persistente; indicador de almacenamiento en UI. *(P1-6, P1-7)*
13. CI con tests de frontend y smoke en Playwright a 1280 px y 368 px; CORS restringido a `FRONTEND_URL`. *(P1-9, P1-10)*

---

## 8. Limitaciones de esta auditoría

- Sin probar Jarvis contra la API real de Anthropic (la clave local es falsa). Lo que dice el chat no fue verificado en ejecución real.
- Sin probar OAuth de GitHub, Bitbucket, Google ni Basecamp.
- Sin probar en producción. El punto P1-6 se basa en la configuración del repo.
- Sin sesión con usuarios reales ni entrevistas a PMs. Las recomendaciones de §5 y §6 son de análisis, no de investigación con usuarios.
- Sin el pase completo de `apple-design` por no estar instalada (ver §2).

## Evidencias

- [desktop-projects.png](./desktop-projects.png): proyecto vacío en verde, 1280 px.
- [desktop-chat.png](./desktop-chat.png): home de Jarvis, 1280 px.
- [phone-chat.png](./phone-chat.png): shell en 368 px, contenido recortado.
