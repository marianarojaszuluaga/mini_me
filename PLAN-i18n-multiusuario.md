# PLAN — Multi-usuario e Internacionalización

Fecha: 2026-09-09. Estado: planeación + primera implementación (ver "Estado real
al cierre de este pase" al final — qué quedó hecho vs. qué queda pendiente).

## 1. Modelo de Usuario

`app/schemas/user.py`:

```
User:
  id: str (uuid4)
  email: EmailStr (única, case-insensitive)
  name: str | None
  password_hash: str | None   # bcrypt, None si el usuario solo usa Google
  google_id: str | None       # sub del id_token de Google, None si solo password
  role: "owner" | "admin" | "member" = "owner"
  createdAt: str (ISO)

UserPublic: igual, SIN password_hash — lo único que sale de la API.
```

Persistencia: `storage/users.json` (filesystem dev) / Redis en prod, mismo patrón
que `projects.json` / `auth-profiles.json` (`app/core/storage.py`: `read_users`/
`write_users`, agregados junto a los métodos existentes).

## 2. Autenticación

Dos caminos, un mismo JWT de salida:

- **Email + password**: `POST /auth/register` (crea usuario, hash bcrypt real —
  ver nota abajo sobre passlib vs. bcrypt directo), `POST /auth/login` (verifica
  password, emite JWT).
- **Google OAuth (login de app, no Auth Profile de integración)**:
  `POST /auth/google` recibe el `id_token` que el frontend obtiene de Google
  Identity Services (botón "Continuar con Google"), lo verifica server-side
  (firma + audience contra `GOOGLE_OAUTH_CLIENT_ID`, vía `google-auth` — pendiente
  de instalar, ver sección de pendientes) y crea/loguea el usuario correspondiente
  (matching por `google_id`, o por `email` si ya existía una cuenta password).

JWT propio: HS256, firmado con `JWT_SECRET` (nueva env var, `app/core/config.py`),
7 días de expiración, claims `{sub: user.id, email, role, iat, exp}`.
`GET /auth/me` decodifica el Bearer y devuelve `UserPublic`.

**Nota de implementación real (no solo plan)**: se intentó `passlib[bcrypt]`
primero; su backend de detección de bcrypt falla en este entorno
(`ValueError: password cannot be longer than 72 bytes` durante el self-test de
passlib, incompatibilidad conocida entre passlib y bcrypt>=4.1). Se resolvió
usando el paquete `bcrypt` directamente (`bcrypt.hashpw`/`checkpw`), truncando a
72 bytes explícitamente antes de hashear — mismo límite real de bcrypt, ahora
manejado por nuestro código en vez de fallar dentro de passlib.

## 3. Convivencia con la autenticación actual (API keys)

Hoy `authenticate_token` (`app/core/security.py`) exige una API key de
`APP_API_KEYS` para *todas* las rutas de `projects.py`/`repositories.py`. Romper
eso habría dejado sin acceso a cualquier caller server-to-server existente (cron,
CI, Apps Script). Se agregó `authenticate_api_key_or_user`: acepta **o bien** una
API key válida **o bien** un JWT de usuario válido, y se usa como dependencia de
router en `projects.py`/`repositories.py` en vez de `authenticate_token` (que se
deja intacto para quien lo siga importando directamente).
Para identificar *quién* es el usuario (no solo que el acceso es válido), los
handlers que necesitan filtrar por dueño además dependen de
`get_current_user_optional` (devuelve `User | None`, nunca lanza).

## 4. Ownership de proyectos

- `Project.owner_user_id: str | None` (nuevo campo, opcional — no rompe datos
  existentes que no lo tienen).
- `GET /projects`, `GET /projects/{id}`, `POST /projects`: cuando hay un usuario
  autenticado (JWT), filtran/asignan por `owner_user_id`. Sin usuario autenticado
  (solo API key) se preserva el comportamiento actual — ve todo — para no romper
  llamadas server-to-server.
- **Alcance de hoy: single-owner.** `owner_user_id` es un solo id, no una lista.
  **TODO (fase futura, no implementado)**: roles/equipos compartidos — varios
  usuarios con acceso a un mismo proyecto (viewer/editor/owner), probablemente
  como `owner_user_id` + `shared_with: list[{user_id, role}]`. Fuera de alcance
  de este pase a propósito.

## 5. Auth Profiles con dueño

- `AuthProfile.user_id: str | None` (nuevo, opcional).
- `GET /auth-profiles`, `POST /auth-profiles`: mismo patrón de filtrado que
  proyectos. El auth profile creado por un usuario autenticado queda con su
  `user_id`; sin usuario autenticado, sigue como antes (visible solo vía API key).

## 6. Migración de datos existentes (seed)

Pendiente de ejecutar (documentado aquí, no corrido automáticamente porque
requiere decidir la contraseña/flujo de primer login de Mariana):

1. Crear el usuario de Mariana: `auth_service.create_user(storage, email=
   "mariana.rojas@imagineapps.co", password=<ella la define en su primer
   /auth/register>, name="Mariana Rojas", role="owner")`.
2. Backfill: para cada proyecto en `storage/projects.json` sin `owner_user_id`,
   setear `owner_user_id = <id de Mariana>`. Mismo backfill para
   `storage/auth-profiles.json` → `user_id`.
3. Un script único (`scripts/migrate_users_seed.py`, no incluido en este pase —
   queda como siguiente paso concreto) que haga 1+2 de forma idempotente
   (no duplica el usuario si ya existe por email).

## 7. i18n del frontend

- Librerías: `i18next`, `react-i18next`, `i18next-browser-languagedetector`.
- Estructura:
  ```
  dashboard/src/i18n/
    index.js          # init i18next, detecta idioma del navegador, default es-ES
    locales/
      es.json          # namespace único "translation" para empezar
      en.json
  ```
- Locales iniciales: `es-ES` (default, es lo que ya habla el dashboard) y `en-US`.
- Prioridad de migración de strings (lo que ya pidió Mariana): `Sidebar.jsx`,
  `ProjectsView.jsx`, `ChatPanel.jsx` primero; el resto de `dashboard/src/components/`
  se migra de forma incremental después, namespace por namespace
  (`sidebar`, `projects`, `chat`, `landing`, ...) en vez de un único archivo gigante.
- Selector de idioma: un `<select>`/toggle ES/EN simple, visible en la Landing y
  en el Sidebar, que llama `i18n.changeLanguage(...)` y persiste en
  `localStorage` (`i18nextLng`, el default que ya usa el detector de idioma).

## 8. Landing page

Nueva ruta (antes del AppShell actual, que no tenía login): hero "Mini me" /
"Everything in one place. Orquestrador for Strategic Operations with Jarvis
Mode.", sección de features reales (GitHub/Bitbucket/Basecamp/Google, agentes,
chat Jarvis, QA), formulario de acceso con email+password y botón "Continuar con
Google". Al loguearse (`POST /auth/login` o `/auth/google` exitoso), guarda el
JWT (localStorage) y redirige al `AppShell` existente.

## Estado real al cierre de este pase (verificado, no solo planeado)

**Hecho e implementado:**
- `app/schemas/user.py`, `app/services/auth_service.py`, `app/routers/auth.py`
  (register/login/google/me), montado en `app/main.py`.
- `authenticate_api_key_or_user` + `get_current_user`/`get_current_user_optional`
  en `app/core/security.py` / `app/services/auth_service.py`.
- `Project.owner_user_id`, `AuthProfile.user_id`, filtrado en
  `app/routers/projects.py` y `app/routers/repositories.py`.
- `Storage.read_users`/`write_users` en `app/core/storage.py`.
- `JWT_SECRET` en `app/core/config.py`; `python-jose`, `bcrypt`,
  `pydantic[email]` agregados a `requirements.txt`/`pyproject.toml`.
- Tests backend en `tests/test_auth.py` (register, duplicado, login ok/mal,
  `/me` sin token, Google mockeado, aislamiento de proyectos entre usuarios) —
  7/7 pasando junto con el resto de la suite (ver reporte de verificación).
- i18next + react-i18next configurado en `dashboard/`, `dashboard/src/i18n/`
  con `es.json`/`en.json`, Sidebar/ProjectsView/AppShell usando `useTranslation`.
- `dashboard/src/pages/Landing.jsx` con hero, features, selector de idioma y
  formulario de acceso (email+password + botón Google), conectado a
  `POST /auth/login` y `/auth/register` reales; redirige al AppShell guardando
  el JWT en `localStorage`.

**Explícitamente NO implementado en este pase (documentado como pendiente, no
como "hecho parcialmente"):**
- Roles/equipos compartidos por proyecto (sección 4, TODO explícito, fuera de
  alcance a propósito).

## Pase 2 (2026-09-10) — Google login real, migración de datos, i18n ampliado

**Hecho:**
- `google-auth==2.35.0` agregado a `requirements.txt`/`pyproject.toml` e
  instalado en el entorno de este worktree. `verify_google_id_token` en
  `app/services/auth_service.py` ya llamaba a
  `google.oauth2.id_token.verify_oauth2_token` — solo faltaba la dependencia
  instalada, que ya está.
- `dashboard/src/pages/Landing.jsx`: botón "Google no configurado" reemplazado
  por integración real de Google Identity Services (carga
  `https://accounts.google.com/gsi/client`, `google.accounts.id.initialize` +
  `renderButton`, `credential` → `POST /auth/google`). Lee el client id de
  `VITE_GOOGLE_OAUTH_CLIENT_ID` (nueva env var de build del dashboard); si no
  está seteada, muestra un botón deshabilitado con el mensaje de "no
  configurado" en vez de intentar cargar el script de Google.
  **Pendiente manual de la usuaria**:
  1. Setear `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET` en el entorno
     de producción del backend (ya existen en `app/core/config.py`, solo
     faltan los valores reales).
  2. Setear `VITE_GOOGLE_OAUTH_CLIENT_ID` en el build del dashboard (mismo
     client id, variable pública del frontend).
  3. En Google Cloud Console → Credentials → el OAuth 2.0 Client ID: agregar
     como "Authorized JavaScript origins" `http://localhost:5173` (dev) y el
     dominio real de producción del dashboard.
- `scripts/migrate_to_multiuser.py`: crea (o reutiliza, por email) el usuario
  owner, y asigna `owner_user_id`/`user_id` a TODOS los proyectos y Auth
  Profiles que no lo tengan ya. Idempotente (verificado por test). Password
  interactivo (`getpass`) o `--password` para uso no interactivo.
  **NO se ejecutó contra storage real.** Comando exacto que la usuaria debe
  correr ella misma (contraseña se pide de forma interactiva, no queda en el
  historial de shell):
  ```
  python scripts/migrate_to_multiuser.py --email rojaszuluagamariana@gmail.com --name "Mariana Rojas"
  ```
  Tests: `tests/test_migrate_to_multiuser.py` (creación de usuario, backfill de
  proyectos/auth-profiles, idempotencia, no-pisa-ownership-existente) — 3/3
  pasando.
- i18n ampliado a `ProjectsView.jsx`, `ChatPanel.jsx`, `AnalyticsDrillDown.jsx`,
  `MarMemoryDrillDown.jsx` (componente de MarMemory drill-down),
  `IntegrationsDrillDown.jsx` (componente de Integrations drill-down) y
  `SettingsModal.jsx` — namespaces `projects`, `chat`, `analytics`,
  `marMemory`, `integrations`, `settings` agregados a
  `dashboard/src/i18n/locales/{es.json,en.json}`.

**Actualización (2026-09-10):** `LifecycleView.jsx` y `BasecampPublishSettings.jsx`
se copiaron desde el repo principal (donde existían como archivos `??` sin
commitear) y ya están migrados a i18next con el mismo patrón (`useTranslation`,
namespaces `lifecycle` y `basecamp` agregados a
`dashboard/src/i18n/locales/{es.json,en.json}`). `LifecycleView` no está
todavía cableado en `AppShell.jsx`/`Sidebar.jsx` (no forma parte de este pase),
pero el componente compila y está completamente traducido. Ya no quedan
componentes pendientes de i18n en este worktree.

**Explícitamente NO implementado en este pase 2:**
- El botón de Google requiere que la usuaria complete los 3 pasos manuales de
  arriba (env vars + orígenes autorizados) antes de funcionar en producción;
  en dev/CI sin esas variables, el flujo sigue degradando de forma segura
  (botón deshabilitado en frontend, 501 explícito en backend).
