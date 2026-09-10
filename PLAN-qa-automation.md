# PLAN — QA Automation (SonarQube + higiene de repos)

Origen: reunión CTO Angela Forero, QA/KPI, 2026-09-10. Este documento cubre
las dos piezas de esa reunión que se dejan **solo como diseño** en esta
sesión (Tareas 4 y 5 del pedido) — sin código de integración todavía.

---

## Tarea 4 — SonarQube / SonarCloud (diseño, bloqueado por credenciales)

### Cómo se integraría
1. SonarCloud/SonarQube corre su análisis (en CI o en un job propio) y, al
   terminar, dispara un **webhook** hacia un endpoint nuevo de este backend
   (p.ej. `POST /qa/sonar-webhook`).
2. Ese endpoint traduce el payload de Sonar (issues por severidad
   BLOCKER/CRITICAL/MAJOR/MINOR/INFO) al esquema ya existente en
   `app/schemas/qa.py` (`Finding` con `severity: S1..S5`), con un mapeo fijo,
   por ejemplo:
   - BLOCKER/CRITICAL -> S1/S2 (bloqueante, mismo gate que el QA sweep)
   - MAJOR -> S3
   - MINOR/INFO -> S4/S5
3. Los `Finding` resultantes se anexan al `QaSweepReport` del proyecto/release
   correspondiente — **mismo esquema, mismo gate mecánico**, sin un reporte
   paralelo.

### Variables de entorno necesarias
- `SONAR_TOKEN` — token de autenticación contra la API de Sonar.
- `SONAR_HOST_URL` — URL del servidor (SonarQube self-hosted) o de la API de
  SonarCloud.
- `SONAR_ORGANIZATION` — solo aplica a SonarCloud (organización del proyecto).

### Estado
**Bloqueado** hasta que la dueña del producto (Mariana) provea esas
credenciales/cuenta. No se escribe código de integración en esta sesión —
solo este diseño.

---

## Tarea 5 — Agente de higiene de repos + rotación de credenciales (diseño)

### 5.1 Agente de higiene de repos (resumen semanal)

Arquitectura propuesta:
1. Recorre los **Auth Profiles** ya conectados (`app/schemas/auth_profile.py`,
   GitHub/Bitbucket) — reusa el mismo mecanismo de autenticación que ya usan
   `repositories.py`/`orchestrator`, no credenciales nuevas.
2. Por cada repo conectado, vía la API de GitHub/Bitbucket:
   - lista PRs abiertos hace más de 24h sin aprobación,
   - lista ramas sin commits recientes (umbral configurable, ej. 30 días).
3. Compone un resumen semanal (texto corto, por repo y agregado) y lo publica:
   - **Basecamp**, reusando `app/services/basecamp_publisher.py` (ya existe,
     ya tiene retry/idempotencia) — opción recomendada, cero infraestructura
     nueva; o
   - un canal alternativo (Slack/email) si Basecamp no es el lugar donde el
     equipo mira esto — a decidir con la dueña del producto según a quién va
     dirigido el resumen.
4. Corre en un scheduler ya existente en el proyecto (o un cron externo) —
   no requiere un servicio nuevo, solo un job periódico que llama al agente.

Este agente se implementaría como un módulo nuevo en `app/services/`
(análogo a `basecamp_publisher.py`), no como agente LLM en
`agent_registry.py` — es lógica determinística sobre datos de la API de
GitHub/Bitbucket, no un prompt.

**Estado:** diseño únicamente en esta sesión, no implementado.

### 5.2 Rotación de credenciales en ~135 repos (fuera de alcance de una sesión)

Esto es un proyecto propio, no una tarea de una sesión. Approach documentado:

1. **Inventario primero**: antes de rotar nada, generar un inventario real de
   qué credencial/token/secret vive en cada uno de los ~135 repos y dónde
   (GitHub Secrets, Bitbucket variables, `.env` committeado por error, CI
   config). Sin esto, "rotar" es a ciegas.
2. **Clasificar por riesgo**: credenciales expuestas en código > credenciales
   en CI sin rotación reciente > el resto. Priorizar rotación por riesgo, no
   repo por repo en orden alfabético.
3. **Rotación asistida, no automática de entrada**: un primer agente que
   proponga (no ejecute) el plan de rotación por repo — qué credencial, quién
   es el dueño/aprobador, y el paso manual necesario en el proveedor (GitHub/
   Bitbucket/servicio externo) — porque la rotación real de muchos secrets no
   tiene una API uniforme entre proveedores.
4. Automatizar la ejecución solo después de validar el proceso manualmente
   en un subconjunto pequeño (5-10 repos de bajo riesgo).

**Estado:** fuera de alcance de esta sesión — solo se documenta el approach,
sin código.
