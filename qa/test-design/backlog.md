# Backlog — Flujos de Agentes de Mini me

> Generado invocando a `gime` (Gimena) de verdad, vía `POST /agents/gime/invoke`, el 2026-09-18.
> No escrito a mano — sigue el protocolo real de Gimena (ver `gime_userstorywriter.md`).

## BACKLOG MAESTRO

| ID | Title | Output File |
| :--- | :--- | :--- |
| HU-001 | Renombrar archivos de Planning al esquema `id_función.md` | HU_RUN-001_2026-09-18.md |
| HU-002 | Renombrar archivos de Desarrollo al esquema `id_función.md` | HU_RUN-001_2026-09-18.md |
| HU-003 | Renombrar archivos de Calidad Capa 2 al esquema `id_función.md` | HU_RUN-001_2026-09-18.md |
| HU-004 | Renombrar archivos de CI/CD y PM al esquema `id_función.md` | HU_RUN-001_2026-09-18.md |
| HU-005 | Agregar header de metadata estándar a cada archivo `id_función.md` | HU_RUN-001_2026-09-18.md |
| HU-006 | Agente `cata` — crear prompt y registrar en el roster | HU_RUN-001_2026-09-18.md |
| HU-007 | Agente `leo` — consolidación + notificación real por Google Chat (`POST /agents/leo/notify`) | HU_RUN-001_2026-09-18.md |
| HU-008 | Agente `mia` — mensajera de notas de reunión vía Google Drive | HU_RUN-001_2026-09-18.md |
| HU-009 | Agente `nico` — sync diario de documentación a Google Drive | HU_RUN-001_2026-09-18.md |
| HU-010/011 | Ampliación de scope OAuth de Google + reconexión manual de cuentas existentes | HU_RUN-001_2026-09-18.md |

## REGISTRO DE CORRIDAS

| RUN_ID | Date | HU Range | Module | Feature | Output File |
| :--- | :--- | :--- | :--- | :--- | :--- |
| RUN-001 | 2026-09-18 | HU-001 to HU-011 | Flujos de Agentes Mini me | Roster consolidado, agentes nuevos, OAuth Drive | HU_RUN-001_2026-09-18.md |

## Estado real (no aspiracional)

- **HU-001 a HU-005** (renombres + metadata): documentan trabajo **ya hecho** en el repo — verificar contra el estado real de `src/agents/` antes de usarlas como pendiente de desarrollo. Gimena no tuvo acceso a leer el filesystem real (el endpoint `/invoke` no le da tools), así que estas HUs describen el *objetivo* de forma correcta pero con `[Pendiente: Definir nombre actual]` en vez de los nombres exactos — completar esos campos contra el roster real (`agentes-mini-me-input-output-handoff.xlsx`) antes de usarlas para auditoría.
- **HU-006, HU-008, HU-009** (`cata`, `mia`, `nico`): describen agentes nuevos, correctamente marcados con `[Pendiente]` en las decisiones de diseño que todavía no se tomaron (criterio de "finalizado" para nico, formato exacto de casos de cata, etc.).
- **HU-007** (`leo`): documenta funcionalidad **ya entregada y en producción** — corregida a mano el 2026-09-18 porque Gimena asumió códigos HTTP de error que no son los reales del endpoint.
- **HU-010/011** (OAuth): documentan un cambio de infraestructura ya hecho (`app/routers/oauth.py`) más el paso manual de reconexión pendiente para la usuaria.
