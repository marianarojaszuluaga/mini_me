"""Autobasecamp SPEC §4.2 — puerto de la lógica armada a mano el
2026-09-11 (`analyze_dev_kanban2.py` / `build_report_v3.py`) a funciones
puras y testeables, sin tocar la red.

Formato esperado: `TYPE-NUM-Modulo: descriptor` (ej. `HOTFIX-217-Login:
arregla el timeout del refresh token`), pero la nomenclatura real en
Basecamp es muy inconsistente (typos: HORFIX, FotFix, "Hot Fix",
"%Hotfix%", sin guión, mayúsculas mezcladas) — el parser es tolerante a eso,
y deja campos en None (no adivina) cuando no puede reconocer algo con
confianza, en vez de forzar una clasificación falsa.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.basecamp_nomenclature import BasecampNomenclatureRule

# Alias conocidos -> tipo canónico. Comparados tras normalizar (mayúsculas,
# sin espacios/guiones) así "Hot Fix", "HOT-FIX", "hotfix" y "%Hotfix%"
# caen todos en HOTFIX; HORFIX/FotFix son los typos reales encontrados hoy.
_TYPE_ALIASES: dict[str, str] = {
    "HU": "HU",
    "HISTORIADEUSUARIO": "HU",
    "BUG": "BUG",
    "BUGFIX": "BUG",
    "HOTFIX": "HOTFIX",
    "HORFIX": "HOTFIX",
    "FOTFIX": "HOTFIX",
    "HOTIFX": "HOTFIX",
}


def _normalize_type_token(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z]", "", raw).upper()
    return cleaned


class ParsedTitle(BaseModel):
    raw: str
    type: str | None = None
    number: int | None = None
    module: str | None = None
    descriptor: str | None = None

    @property
    def confident(self) -> bool:
        """Reconocido con confianza: tipo canónico + número. Módulo/
        descriptor son deseables pero su ausencia no invalida el
        reconocimiento (muchas cards reales del hoy no traían módulo)."""
        return self.type is not None and self.number is not None


class Card(BaseModel):
    id: str
    title: str
    card_table_key: str  # "{project_id}:{card_table_id}"
    url: str | None = None


class AuditFinding(BaseModel):
    card: Card
    parsed: ParsedTitle
    reason: str
    suggested_title: str | None = None
    suggested_translation: str | None = None


class AuditResult(BaseModel):
    duplicates: list[AuditFinding] = Field(default_factory=list)
    missing: list[AuditFinding] = Field(default_factory=list)
    cross_table_violations: list[AuditFinding] = Field(default_factory=list)


# Regex tolerante: tipo (letras/espacios/guiones, sin dígitos) seguido de un
# número, seguido de resto libre. No exige separador exacto ("-", " ", "").
_TITLE_RE = re.compile(r"^\s*[%\s]*([A-Za-z][A-Za-z\s\-]*?)[\s\-]*[:.]?\s*(\d+)\s*[\-:]?\s*(.*)$")


def parse_card_title(title: str) -> ParsedTitle:
    """Parsea `TYPE-NUM-Modulo: descriptor`, tolerante a typos conocidos.
    Devuelve None por campo (nunca un valor inventado) cuando no se pudo
    reconocer con confianza."""
    if not title or not title.strip():
        return ParsedTitle(raw=title or "")

    # "%Hotfix%" (typo real de hoy) usa "%" como delimitador decorativo, no
    # parte del tipo — se descarta antes de matchear, no solo al principio.
    cleaned_title = title.replace("%", " ")
    match = _TITLE_RE.match(cleaned_title)
    if not match:
        return ParsedTitle(raw=title)

    raw_type, raw_number, rest = match.groups()
    canonical_type = _TYPE_ALIASES.get(_normalize_type_token(raw_type))

    try:
        number = int(raw_number)
    except ValueError:
        number = None

    module: str | None = None
    descriptor: str | None = None
    rest = rest.strip().lstrip("-").strip()
    if rest:
        if ":" in rest:
            module_part, descriptor_part = rest.split(":", 1)
            module = module_part.strip() or None
            descriptor = descriptor_part.strip() or None
        else:
            descriptor = rest or None

    return ParsedTitle(
        raw=title,
        type=canonical_type,
        number=number,
        module=module,
        descriptor=descriptor,
    )


def next_available_number(rule: BasecampNomenclatureRule, used_numbers: set[int]) -> int:
    """Primer número libre dentro de los rangos reservados de esta tabla,
    recorridos en el orden en que se configuraron."""
    for start, end in rule.reserved_ranges:
        candidate = start
        while candidate <= end:
            if candidate not in used_numbers:
                return candidate
            candidate += 1
    raise ValueError(f"No hay números disponibles en los rangos reservados de '{rule.label}'.")


def _rule_for_table(rules: list[BasecampNomenclatureRule], card_table_key: str) -> BasecampNomenclatureRule | None:
    return next((r for r in rules if r.card_table_key == card_table_key), None)


def _in_ranges(number: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= number <= end for start, end in ranges)


def audit_card_tables(
    cards_by_table: dict[str, list[Card]],
    rules: list[BasecampNomenclatureRule],
) -> AuditResult:
    """Recibe las cards YA LEIDAS de N Card Tables + las reglas de rango.
    Nunca aplica nada — solo calcula (aplicar es POST .../apply, aparte)."""
    result = AuditResult()

    # number -> [(card, parsed, table_key), ...] across ALL tables passed in
    # (never auto-cross-referencing tables not explicitly included by the
    # caller, per decision §7.1).
    by_number: dict[int, list[tuple[Card, ParsedTitle]]] = {}
    used_per_table: dict[str, set[int]] = {key: set() for key in cards_by_table}

    all_parsed: list[tuple[Card, ParsedTitle]] = []
    for table_key, cards in cards_by_table.items():
        for card in cards:
            parsed = parse_card_title(card.title)
            all_parsed.append((card, parsed))
            if parsed.confident:
                by_number.setdefault(parsed.number, []).append((card, parsed))
                used_per_table[table_key].add(parsed.number)

    for card, parsed in all_parsed:
        if not parsed.confident:
            rule = _rule_for_table(rules, card.card_table_key)
            suggestion = None
            if rule is not None:
                try:
                    suggested_number = next_available_number(rule, used_per_table.get(card.card_table_key, set()))
                    used_per_table[card.card_table_key].add(suggested_number)
                    type_guess = parsed.type or (rule.types[0] if rule.types else "HU")
                    module_part = f"{parsed.module}: " if parsed.module else ""
                    descriptor_part = parsed.descriptor or parsed.raw
                    suggestion = f"{type_guess}-{suggested_number}-{module_part}{descriptor_part}"
                except ValueError:
                    suggestion = None
            result.missing.append(
                AuditFinding(
                    card=card,
                    parsed=parsed,
                    reason="No se pudo reconocer TYPE-NUM-Modulo: descriptor con confianza.",
                    suggested_title=suggestion,
                )
            )

    for number, entries in by_number.items():
        if len(entries) < 2:
            continue
        for card, parsed in entries:
            rule = _rule_for_table(rules, card.card_table_key)
            suggestion = None
            if rule is not None:
                try:
                    suggested_number = next_available_number(rule, used_per_table.get(card.card_table_key, set()))
                    used_per_table[card.card_table_key].add(suggested_number)
                    module_part = f"{parsed.module}: " if parsed.module else ""
                    suggestion = f"{parsed.type}-{suggested_number}-{module_part}{parsed.descriptor or ''}".strip()
                except ValueError:
                    suggestion = None
            result.duplicates.append(
                AuditFinding(
                    card=card,
                    parsed=parsed,
                    reason=f"Número {number} repetido en {len(entries)} cards.",
                    suggested_title=suggestion,
                )
            )

    for card, parsed in all_parsed:
        if not parsed.confident:
            continue
        own_rule = _rule_for_table(rules, card.card_table_key)
        if own_rule is None:
            continue
        if _in_ranges(parsed.number, own_rule.reserved_ranges):
            continue
        # Fuera del rango de su propia tabla — ¿colisiona con el rango de
        # otra tabla, o simplemente está fuera de todo rango conocido?
        colliding = next(
            (
                r
                for r in rules
                if r.card_table_key != card.card_table_key and _in_ranges(parsed.number, r.reserved_ranges)
            ),
            None,
        )
        if colliding is not None:
            reason = (
                f"Número {parsed.number} está dentro del rango reservado de "
                f"'{colliding.label}' ({card.card_table_key} no es esa tabla)."
            )
        else:
            reason = f"Número {parsed.number} está fuera de los rangos reservados de '{own_rule.label}'."
        result.cross_table_violations.append(AuditFinding(card=card, parsed=parsed, reason=reason))

    return result


_TRANSLATE_MODEL = "claude-sonnet-4-6"

# Heurística barata para no llamar al LLM en cada card: si el texto no tiene
# ninguna señal de español, ni siquiera se intenta traducir.
_SPANISH_HINTS = re.compile(
    r"\b(el|la|los|las|de|que|para|con|una|uno|arregla|corrige|agrega|"
    r"pantalla|usuario|cliente|error|falla|módulo|modulo)\b",
    re.IGNORECASE,
)


def looks_spanish(text: str | None) -> bool:
    if not text:
        return False
    return bool(_SPANISH_HINTS.search(text))


async def suggest_translation(text: str, *, client: Any = None) -> str | None:
    """§7.3 (decisión de producto 2026-09-11): sugerencia OPCIONAL de
    traducción ES->EN, nunca automática/forzada — solo se llama cuando
    `translate_to_english` está prendido para esa tabla (toggle desde UI,
    §5.3) y `looks_spanish` detectó español. Usa el mismo cliente Anthropic
    ya integrado en el proyecto (mismo patrón que evaluate_invocation.py /
    agents.py) — nunca un cliente nuevo. Devuelve None ante cualquier falla
    real (nunca fabrica una traducción)."""
    from anthropic import AsyncAnthropic

    from app.core.config import get_settings

    own_client = client is None
    if own_client:
        settings = get_settings()
        client = AsyncAnthropic(**settings.anthropic_client_kwargs)

    try:
        response = await client.messages.create(
            model=_TRANSLATE_MODEL,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Traducí este título de card de Basecamp de español a inglés, "
                        "manteniendo el mismo formato TYPE-NUM-Modulo: descriptor si lo tiene. "
                        f"Devolvé SOLO el título traducido, sin comillas ni explicación.\n\n{text}"
                    ),
                }
            ],
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        translated = "".join(parts).strip()
        return translated or None
    except Exception:  # noqa: BLE001 - traducción es best-effort, nunca rompe el audit
        return None
    finally:
        if own_client:
            await client.close()
