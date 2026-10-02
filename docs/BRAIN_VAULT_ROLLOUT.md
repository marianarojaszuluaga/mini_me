# Rollout del vault de Obsidian por equipo — Opción B (config de despliegue)

> Decisión (2026-10-01, aprobada): la ruta del vault de Obsidian donde se
> respalda el Brain de cada proyecto la define **quien despliega** el sistema
> para un equipo, vía variable de entorno — no hay pantalla de configuración
> en el dashboard. Ver alternativa descartada en "Opción A (futura)" al final.

## Qué ya está implementado (código, no pendiente)

- `app/core/config.py` → `Settings.OBSIDIAN_VAULT_DIR` (env var opcional) +
  propiedad `obsidian_vault_dir` que cae al default histórico
  (`C:\Users\marir\OneDrive\Documentos\Obsidian Vault\...`) cuando no está seteada.
- `app/services/obsidian_sync.py` → ya no tiene la ruta hardcodeada; lee
  `get_settings().obsidian_vault_dir` en cada sync.
- `scripts/sync_memories_to_obsidian.py` → actualizado para leer la misma config.
- `.env.example.python` → documenta la variable.

Es decir: **el rollout de Opción B no requiere más código**, solo el proceso
operativo de abajo para que cada equipo quede bien configurado al desplegar.

## Plan de rollout (por equipo nuevo)

1. **Antes de desplegar**: la persona que hace el despliegue decide/crea la
   carpeta del vault de Obsidian de ese equipo (local o en un volumen montado
   del host del backend — nunca una ruta de red/SMB no garantizada).
2. **Al desplegar el backend**: setear `OBSIDIAN_VAULT_DIR=<ruta absoluta>`
   en las variables de entorno de ese deployment (mismo lugar que
   `ANTHROPIC_API_KEY` / `APP_API_KEYS`, ver tabla en `README.md`).
3. **Verificar**: tras el primer arranque, confirmar en los logs del backend
   la línea `obsidian_sync: synced N Mar Memory entries, M proyectos -> <ruta>`
   (emitida por `app/services/obsidian_sync.py`) y que esa ruta sea la
   esperada para ese equipo, no el default de otro equipo.
4. **Documentar** la ruta asignada a cada equipo en un lugar accesible para
   quien administre despliegues (ej. una entrada por equipo en el mismo
   lugar donde ya se gestionan `APP_API_KEYS` por cliente) — este repo no
   mantiene ese inventario por equipo, es responsabilidad operativa, no de
   código.

## Restricción real a comunicar (no es un detalle menor)

El sync corre como job interno del proceso backend (`APScheduler`,
`app/cron/sync_scheduler.py`), cada 3h, **mientras ese proceso esté vivo**.
Dos implicaciones directas para el rollout:

- **Requiere un backend desplegado como proceso siempre activo** (no
  serverless). El propio `README.md` (sección de despliegue en Vercel)
  confirma que el backend hoy corre ahí como función serverless — en ese
  modo el scheduler de 3h **no persiste entre invocaciones** y el vault no
  se sincroniza solo, sin importar qué ruta se configure.
- Mitigación disponible hoy sin escribir código nuevo: `scripts/sync_memories_to_obsidian.py`
  sigue funcionando como sync manual/programable externamente (ej. un cron
  del sistema operativo o una tarea programada fuera del proceso serverless)
  contra la API real desplegada — usar esa ruta para cualquier equipo cuyo
  backend corra en Vercel/serverless, hasta que exista un worker separado.

## Checklist de implementación (para quien despliegue un equipo nuevo)

- [ ] Backend corre como proceso de larga duración (no serverless), **o**
      se programó `scripts/sync_memories_to_obsidian.py` externamente.
- [ ] Carpeta del vault creada y accesible desde donde corre el sync.
- [ ] `OBSIDIAN_VAULT_DIR` seteada en las variables de entorno de ese deployment.
- [ ] Logs confirman la ruta correcta tras el primer sync.
- [ ] Ruta del equipo registrada donde se administran las demás variables
      por cliente/equipo.

## Opción A (futura, no implementada)

Si más adelante 3+ equipos necesitan cambiar su propia ruta sin pedirle a
alguien que redeploye, retomar Opción A: un endpoint que persista la ruta
por equipo (en vez de solo leerla de env var) + un campo en Settings del
dashboard. Esfuerzo estimado entonces: ~medio día — ver el hilo de la
presentación "Brain" del 2026-10-01 para el contexto completo de la decisión.
