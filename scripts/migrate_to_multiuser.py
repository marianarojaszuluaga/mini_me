"""
Migración a multi-usuario — asigna TODOS los proyectos y Auth Profiles
existentes al usuario real de la dueña del producto.

Uso:
    python scripts/migrate_to_multiuser.py --email rojaszuluagamariana@gmail.com
    python scripts/migrate_to_multiuser.py --email ... --password "..."   # no interactivo
    python scripts/migrate_to_multiuser.py --email ... --name "Mariana Rojas"

Si no se pasa --password, la pide interactivamente por getpass (no queda en
el historial de shell ni en logs).

Idempotente:
- Si el usuario ya existe (por email), lo reutiliza en vez de fallar o
  duplicarlo.
- Solo asigna owner_user_id/user_id a proyectos/auth-profiles que NO lo
  tengan ya asignado (no pisa asignaciones previas a otro usuario).
- Correrlo varias veces no cambia el resultado tras la primera corrida
  exitosa.

IMPORTANTE: este script usa el mismo Storage/auth_service que la app (mismo
storage/*.json en dev, o Redis si está configurado) — no hardcodea rutas ni
reimplementa la persistencia. NO se ejecuta contra el storage real como
parte de este cambio: la usuaria debe correrlo ella misma (ver
PLAN-i18n-multiusuario.md, sección de comando exacto).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.storage import Storage, get_storage  # noqa: E402
from app.services import auth_service  # noqa: E402
from app.services.auth_service import AuthError  # noqa: E402


def get_or_create_user(
    storage: Storage, email: str, password: str | None, name: str | None
) -> dict:
    email = email.lower()
    existing = auth_service.get_user_by_email(storage, email)
    if existing:
        print(f"Usuario ya existe: {email} (id={existing['id']}) — reutilizando.")
        return existing

    user = auth_service.create_user(storage, email=email, password=password, name=name)
    print(f"Usuario creado: {email} (id={user.id})")
    return user.model_dump()


def migrate_projects(storage: Storage, user_id: str) -> int:
    projects = storage.read_projects()
    changed = 0
    for project in projects:
        if not project.get("owner_user_id"):
            project["owner_user_id"] = user_id
            changed += 1
    if changed:
        storage.write_projects(projects)
    print(f"Proyectos actualizados: {changed}/{len(projects)}")
    return changed


def migrate_auth_profiles(storage: Storage, user_id: str) -> int:
    profiles = storage.read_auth_profiles()
    changed = 0
    for profile in profiles:
        if not profile.get("user_id"):
            profile["user_id"] = user_id
            changed += 1
    if changed:
        storage.write_auth_profiles(profiles)
    print(f"Auth Profiles actualizados: {changed}/{len(profiles)}")
    return changed


def run_migration(
    storage: Storage, email: str, password: str | None, name: str | None
) -> dict:
    user = get_or_create_user(storage, email, password, name)
    projects_changed = migrate_projects(storage, user["id"])
    profiles_changed = migrate_auth_profiles(storage, user["id"])
    return {
        "user_id": user["id"],
        "email": user["email"],
        "projects_changed": projects_changed,
        "auth_profiles_changed": profiles_changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email del usuario dueño")
    parser.add_argument(
        "--password",
        default=None,
        help="Password (si se omite, se pide interactivamente vía getpass)",
    )
    parser.add_argument("--name", default=None, help="Nombre a mostrar")
    args = parser.parse_args()

    password = args.password
    if password is None:
        password = getpass.getpass(f"Password para {args.email}: ")

    storage = get_storage()
    try:
        result = run_migration(storage, args.email, password, args.name)
    except AuthError as exc:
        print(f"Error: {exc.detail}", file=sys.stderr)
        sys.exit(1)

    print("Migración completa:", result)


if __name__ == "__main__":
    main()
