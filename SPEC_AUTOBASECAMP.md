# SPEC — Autobasecamp dentro de Minime (Card Table write-access + auditoría de nomenclatura)

> **Status**: Plan — sin código todavía. Para implementar después de esta sesión.
> **Origen**: sesión 2026-09-11, trabajo manual con scripts sueltos (`auto_basecamp/`) sobre
> Development Kanban, Product Kanban y FB Migration (proyecto Finanz Butik). Todo lo que se
> hizo ahí a mano/por script debe quedar disponible desde el UI de Minime.
> **Relacionado**: `SPEC_JARVIS.md` §6.2 (Auth Profiles), `app/services/basecamp_client.py`,
> `app/routers/projects.py` (endpoints `basecamp-*`), `dashboard/src/components/ProjectDetail/
> BasecampPublishSettings.jsx`.

---

## 0. TL;DR

Minime ya sabe **leer** Basecamp (Card Tables, columnas, cards, Message Board) y **publicar
mensajes**. No sabe **crear ni renombrar cards**. Todo lo de hoy (crear 49 cards, auditar y
corregir la nomenclatura de 252 cards, verificar números duplicados entre 3 tableros) se hizo
con Python + curl directo a la API de Basecamp, fuera de Minime.

Esta spec agrega a Minime:
1. **Crear cards** en cualquier columna de un Card Table vinculado, desde el UI.
2. **Renombrar/editar cards** existentes, desde el UI.
3. **Auditoría de nomenclatura** (`TYPE-###-Módulo: descriptor`) con detección de duplicados y
   cards sin nomenclatura, más un pool de números disponible por tabla — reproduciendo el
   trabajo manual de hoy como una función reutilizable, no un one-off.
4. **Creación masiva** de cards desde una fuente estructurada (para el caso "milestones + steps
   + ciclos de QA como cards").
5. Todo accesible desde `ProjectDetailDrillDown` / `IntegrationsDrillDown` — no solo desde
   scripts.

---

## 1. Estado actual vs. gap

### 1.1 Ya existe (`app/services/basecamp_client.py`)
| Función | Qué hace |
|---|---|
| `list_basecamp_projects` | Lista proyectos reales de la cuenta de Basecamp |
| `list_card_tables` | Lista Card Tables (kanban boards) de un proyecto |
| `get_card_table_snapshot` | Lee columnas + cards de una Card Table |
| `get_active_sprint` | Lee el todolist activo (legacy, previo a Card Tables) |
| `resolve_message_board_id`, `list_categories`, `list_recent_messages`, `publish_message` | Publicar en el Message Board (maduro, con reintentos — `basecamp_publisher.py`) |

### 1.2 No existe — el gap que cerramos a mano hoy
- Crear una card (`POST .../card_tables/lists/{id}/cards.json`)
- Renombrar/editar una card (`PUT .../card_tables/cards/{id}.json`)
- Mover una card entre columnas
- Cualquier lógica de nomenclatura (parseo `TYPE-NUM-Módulo: descriptor`, detección de
  duplicados, pool de números disponibles, verificación cruzada entre Card Tables/proyectos)
- Cualquier UI para lo anterior — todo el trabajo de hoy fue Python + curl manual con un token
  de una segunda app de Basecamp registrada solo para esto (no la que usa Minime en producción)

### 1.3 Detalle no trivial encontrado hoy (debe quedar reflejado en el diseño)
- El pool de números **no es por Card Table aislado** — Mariana lo definió como **compartido
  entre varios Card Tables** (Development Kanban, Product Kanban, FB Migration), con **rangos
  reservados por tabla** (ej. FB Migration = 200–299, Development Kanban = todo menos 200–301).
  Verificar duplicados requiere leer las 3 tablas, no solo la que se está editando.
- Encontramos números que ya colisionaban entre tablas antes de tocar nada (`Hotfix-299` en
  Dev Kanban cae dentro del rango 200-299 "dedicado" a FB Migration) — la auditoría debe
  poder señalar esto como hallazgo, no solo prevenir nuevas colisiones.
- La nomenclatura real en Basecamp es **muy inconsistente** (typos: `HORFIX`, `FotFix`, `Hot
  Fix`, `%Hotfix%`, sin guión, con espacio, mayúsculas/minúsculas mezcladas). El parser tiene
  que ser tolerante, no un regex estricto — y aun así dejar categorías explícitas de "no pude
  clasificar esto con confianza" para revisión humana en vez de adivinar.

---

## 2. Alcance de esta feature

Vive dentro de un proyecto de Minime ya vinculado a Basecamp (`project.basecamp.account_id` +
`project.basecamp.project_id`, existente desde Fase E). Nueva sub-sección en
`ProjectDetailDrillDown.jsx`, junto a donde hoy vive `BasecampPublishSettings` — ej. una pestaña
o acordeón **"Basecamp Cards"**.

No requiere una nueva Auth Profile ni un nuevo OAuth App — reusa el Auth Profile de Basecamp que
el proyecto ya tiene vinculado (mismo patrón que `get_card_table_snapshot`).

---

## 3. Modelo de datos nuevo

### 3.1 Config de nomenclatura (nueva, a nivel de **cuenta de Basecamp**, no por proyecto)
Los rangos de numeración son un acuerdo del equipo sobre la cuenta completa de Basecamp
("Imagine Apps"), no de un proyecto de Minime — varios proyectos de Minime pueden apuntar a
Card Tables de la misma cuenta y deben compartir el mismo pool.

```python
class BasecampNomenclatureRule(BaseModel):
    account_id: str                 # BASECAMP_ACCOUNT_ID
    card_table_key: str             # ej. "44382327:9175270356" (project_id:card_table_id)
    label: str                      # "Development Kanban"
    reserved_ranges: list[tuple[int, int]]   # rangos QUE ESTA TABLA PUEDE USAR, ej. [(1,199),(302,1000)]
    types: list[str] = ["HU", "BUG", "HOTFIX"]
```
Guardado en el mismo storage genérico (`app/core/storage.py`), colección nueva
`basecamp_nomenclature_rules`. Se edita desde el UI (ver §5.3).

### 3.2 Nada nuevo en `Project` — reusa `project.basecamp.{account_id,project_id}` existente.

---

## 4. Servicios backend nuevos

### 4.1 `app/services/basecamp_client.py` — agregar
```python
async def create_card(auth_profile, account_id, project_id, list_id, title, content_html,
                       due_on=None, assignee_ids=None) -> dict: ...

async def update_card(auth_profile, account_id, project_id, card_id, title=None,
                       content_html=None, due_on=None) -> dict: ...

async def move_card(auth_profile, account_id, project_id, card_id, target_list_id) -> dict: ...

async def list_people(auth_profile, account_id, project_id) -> list[dict]: ...
# GET /projects/{project_id}/people.json — necesario para el picker de responsables
```
Mismo patrón de errores explícitos (`BasecampError`) que el resto del archivo — no inventar
éxito si el token expiró o el 4xx es real.

### 4.2 Nuevo `app/services/basecamp_nomenclature.py`
Puerto directo de la lógica que se armó hoy en `analyze_dev_kanban2.py` /
`build_report_v3.py`, como funciones puras y testeables (sin tocar la red):

```python
def parse_card_title(title: str) -> ParsedTitle:
    """TYPE-NUM-Modulo: descriptor, tolerante a typos conocidos (HORFIX, FotFix, Hot Fix,
    %Hotfix%, BUG FIX, sin separador...). Devuelve type/num/module/descriptor o None por campo
    si no se pudo reconocer con confianza."""

def audit_card_tables(cards_by_table: dict[str, list[Card]],
                       rules: list[BasecampNomenclatureRule]) -> AuditResult:
    """Recibe las cards YA LEIDAS de N Card Tables (vía get_card_table_snapshot ampliada a
    incluir todas las columnas) + las reglas de rango. Devuelve:
    - duplicates: mismo numero en 2+ cards (cualquier tabla)
    - missing: cards sin nomenclatura reconocible
    - cross_table_violations: numero usado fuera del rango reservado de su tabla, o
      colisionando con el rango de otra tabla
    - suggested_fixes: nuevo titulo propuesto por cada card en duplicates/missing, tomando el
      siguiente numero libre del rango de SU tabla
    Nunca aplica nada -- solo calcula. Aplicar es una llamada aparte (ver 4.3), explícita."""

def next_available_number(rule: BasecampNomenclatureRule, used_numbers: set[int]) -> int: ...
```

### 4.3 Endpoints nuevos (`app/routers/projects.py`)

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/projects/{id}/basecamp-card-tables/{table_id}/cards` | Crear una card (título, columna, contenido, due_on, assignee_ids) |
| `PUT` | `/projects/{id}/basecamp-cards/{card_id}` | Renombrar/editar una card |
| `POST` | `/projects/{id}/basecamp-cards/{card_id}/move` | Mover de columna |
| `GET` | `/projects/{id}/basecamp-people` | Lista de personas del proyecto Basecamp (picker de responsables) |
| `GET` | `/basecamp-nomenclature-rules?account_id=...` | Lee las reglas de rango configuradas para la cuenta |
| `PUT` | `/basecamp-nomenclature-rules/{card_table_key}` | Crea/edita una regla de rango |
| `POST` | `/projects/{id}/basecamp-nomenclature-audit` | Corre `audit_card_tables` sobre los Card Tables indicados (body: `card_table_ids: []`) — **solo calcula, no escribe en Basecamp** |
| `POST` | `/projects/{id}/basecamp-nomenclature-audit/apply` | Aplica una selección de `suggested_fixes` (lista de `{card_id, new_title}` elegidos a mano en el UI) vía `update_card` en batch, con reintento/rate-limit igual que `basecamp_publisher.py` |
| `POST` | `/projects/{id}/basecamp-cards/bulk` | Crea N cards desde una lista estructurada `[{list_id, title, content, due_on}]` — para el caso "milestones + steps + QA cycles" |

Todos reusan `_get_basecamp_auth_profile` (ya existe en `projects.py`) — mismo Auth Profile,
ningún token nuevo.

---

## 5. UI (dashboard)

Todo dentro de `ProjectDetail/`, junto a `BasecampPublishSettings.jsx` (mismo patrón visual:
`pd-subsection`, `field-label`/`field-select`, `btn-*`, sin paleta nueva).

### 5.1 `BasecampCardsPanel.jsx` (nuevo) — pestaña "Basecamp Cards"
- Selector de Card Table (de los ya vinculados vía `selectedCardTableIds`, existente).
- Tabla de columnas + cards (reusa `get_card_table_snapshot`, ya se pinta hoy en el "espejo").
- Botón **"+ Nueva card"** → modal: título compuesto asistido (Type dropdown HU/BUG/HOTFIX +
  número **auto-sugerido** desde `next_available_number` + módulo + descriptor libre), columna
  destino, responsable (de `list_people`), fecha límite, descripción (rich text simple).
- Botón sobre cada card existente: **"Editar"** → mismo modal, pre-llenado, hace `PUT`.

### 5.2 `BasecampNomenclatureAudit.jsx` (nuevo) — modal o vista separada, lanzada desde el panel
- Selector multi de Card Tables a auditar (cross-tabla, ej. las 3 de Finanz Butik).
- Corre `POST .../basecamp-nomenclature-audit`, pinta 3 bloques (igual que el Excel de hoy):
  **Duplicados**, **Sin nomenclatura**, **Fuera de rango / cruzados entre tablas**.
  Cada fila: título actual, título propuesto (editable a mano antes de aplicar), link a la
  card en Basecamp.
- Checkbox por fila + **"Aplicar seleccionados"** → `POST .../apply`. Nunca aplica todo por
  default — selección explícita, igual que se hizo hoy a mano revisando el Excel primero.

### 5.3 `BasecampNomenclatureRules.jsx` (nuevo, dentro de settings/integración)
- CRUD simple de `BasecampNomenclatureRule` por Card Table: label, rangos reservados, tipos
  permitidos. Vista de "qué rango tiene cada tabla" para evitar que alguien reserve rangos que
  se pisan (validación: si un rango nuevo se solapa con el de otra tabla de la misma cuenta,
  advertir antes de guardar).

### 5.4 Bulk create (milestones/steps/ciclos QA)
- Dentro de `BasecampCardsPanel`, botón **"Crear en lote"** → sube o pega una tabla simple
  (CSV/pegado desde Excel: columna, título, contenido, fecha) → preview antes de crear (igual
  patrón que el Excel de preview de hoy) → `POST .../bulk`.
- No se automatiza la *fuente* (leer milestones-v2.md, dod-by-milestone/*.md) — eso sigue
  siendo un paso manual/asistido por Mar + Claude; lo que se automatiza es la creación de cards
  una vez que la lista ya está armada.

---

## 6. Fases de implementación

1. **MVP — crear y editar cards** (§4.1 `create_card`/`update_card`, endpoints, modal simple
   en `BasecampCardsPanel`). Sin auditoría de nomenclatura todavía — resuelve "necesito crear
   una card ya" sin salir del UI.
2. **Auditoría de nomenclatura** (§4.2, §5.2) — el parser + la vista de duplicados/sin
   nomenclatura + aplicar selección. Este es el que reproduce el trabajo grande de hoy.
3. **Reglas de rango por tabla** (§3.1, §5.3) — necesario para que la auditoría cruce tablas
   correctamente en vez de asumir un solo pool global.
4. **Bulk create** (§5.4) — último porque depende de que 1-2 ya funcionen bien.

---

## 7. Decisiones abiertas (confirmar con Mariana antes de construir)

1. **Alcance de "cuenta"**: ¿las `BasecampNomenclatureRule` viven a nivel de cuenta de
   Basecamp (todas las Card Tables de "Imagine Apps" comparten catálogo de reglas) o hay que
   poder tener reglas independientes por cliente aunque compartan cuenta? (Hoy Finanz Butik ya
   tiene 3 tablas con este esquema; PESMAV/Uptracker podrían necesitar el suyo propio.)
2. **Quién puede aplicar la auditoría**: ¿cualquiera con acceso al proyecto en Minime, o solo
   quien tiene rol de PM? (Aplica un `PUT` real sobre cards de producción.)
3. **Traducción automática ES→EN**: hoy se hizo a mano, revisando caso por caso. ¿Vale la pena
   una función de traducción asistida en el audit (con LLM), o se mantiene manual porque el
   volumen de casos reales fue bajísimo (2 de 252)?
4. **Bulk create**: ¿conviene un parser que lea directamente `milestones-v2.md` /
   `dod-by-milestone/*.md` (acoplado a la estructura de Finanz Butik) o mantenerlo genérico
   (pegar una tabla) y que la lectura del plan siga siendo un paso asistido aparte?

---

## 8. Fuera de alcance (por ahora)

- Borrar cards (no se necesitó hoy, y es más riesgoso — requeriría confirmación reforzada).
- Comentarios en cards, adjuntos, subtareas (`steps` dentro de una card — no confundir con los
  "steps" de milestones de Finanz Butik).
- Cualquier automatización que dispare la creación de cards *sin* que alguien revise el preview
  primero — el patrón de hoy (preview → confirmar → aplicar) se mantiene como requisito de
  diseño, no solo como práctica de esta sesión.
