"""Tests de app/services/basecamp_nomenclature.py — parser tolerante a
typos reales (HORFIX, FotFix, "Hot Fix", "%Hotfix%"), auditoría de
duplicados/faltantes/cruces entre tablas, y next_available_number.
Sin red: son las funciones puras del SPEC §4.2."""

from __future__ import annotations

import pytest

from app.schemas.basecamp_nomenclature import BasecampNomenclatureRule
from app.services.basecamp_nomenclature import (
    Card,
    audit_card_tables,
    next_available_number,
    parse_card_title,
)

# ---------------------------------------------------------------------------
# parse_card_title — typos reales encontrados el 2026-09-11 (SPEC §1.3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,expected_type,expected_number",
    [
        ("HOTFIX-217-Login: arregla timeout", "HOTFIX", 217),
        ("HORFIX-217-Login: arregla timeout", "HOTFIX", 217),
        ("FotFix 45 Pagos: descriptor libre", "HOTFIX", 45),
        ("Hot Fix-12-Modulo: desc", "HOTFIX", 12),
        ("%Hotfix% 5 - blah", "HOTFIX", 5),
        ("HU-10-Perfil: cambia avatar", "HU", 10),
        ("BUG-3: sin modulo", "BUG", 3),
    ],
)
def test_parse_card_title_tolera_typos_conocidos(title, expected_type, expected_number):
    parsed = parse_card_title(title)
    assert parsed.type == expected_type
    assert parsed.number == expected_number
    assert parsed.confident is True


def test_parse_card_title_sin_nomenclatura_no_adivina():
    parsed = parse_card_title("Reunión con el cliente sobre alcance")
    assert parsed.confident is False
    assert parsed.type is None
    assert parsed.number is None


def test_parse_card_title_vacio():
    parsed = parse_card_title("")
    assert parsed.confident is False


def test_parse_card_title_extrae_modulo_y_descriptor():
    parsed = parse_card_title("HU-10-Perfil: cambia el avatar por defecto")
    assert parsed.module == "Perfil"
    assert parsed.descriptor == "cambia el avatar por defecto"


# ---------------------------------------------------------------------------
# next_available_number
# ---------------------------------------------------------------------------


def test_next_available_number_primer_hueco():
    rule = BasecampNomenclatureRule(
        account_id="acc1", card_table_key="p:1", label="Dev Kanban", reserved_ranges=[(1, 5)]
    )
    assert next_available_number(rule, {1, 2, 3}) == 4


def test_next_available_number_salta_a_segundo_rango():
    rule = BasecampNomenclatureRule(
        account_id="acc1", card_table_key="p:1", label="Dev Kanban", reserved_ranges=[(1, 2), (10, 12)]
    )
    assert next_available_number(rule, {1, 2}) == 10


def test_next_available_number_sin_huecos_levanta():
    rule = BasecampNomenclatureRule(
        account_id="acc1", card_table_key="p:1", label="Dev Kanban", reserved_ranges=[(1, 2)]
    )
    with pytest.raises(ValueError):
        next_available_number(rule, {1, 2})


# ---------------------------------------------------------------------------
# audit_card_tables — duplicados, faltantes, cruces entre tablas, rango libre
# ---------------------------------------------------------------------------


def _rules() -> list[BasecampNomenclatureRule]:
    return [
        BasecampNomenclatureRule(
            account_id="acc1",
            card_table_key="p1:dev",
            label="Development Kanban",
            reserved_ranges=[(1, 199), (302, 1000)],
        ),
        BasecampNomenclatureRule(
            account_id="acc1",
            card_table_key="p1:fb",
            label="FB Migration",
            reserved_ranges=[(200, 299)],
        ),
    ]


def test_audit_detecta_duplicados_mismo_numero_entre_tablas():
    cards_by_table = {
        "p1:dev": [Card(id="1", title="HOTFIX-50-Login: fix", card_table_key="p1:dev")],
        "p1:fb": [Card(id="2", title="HOTFIX-50-Migracion: fix", card_table_key="p1:fb")],
    }
    result = audit_card_tables(cards_by_table, _rules())
    duplicate_ids = {f.card.id for f in result.duplicates}
    assert duplicate_ids == {"1", "2"}


def test_audit_detecta_missing_sin_nomenclatura():
    cards_by_table = {"p1:dev": [Card(id="1", title="Card sin formato", card_table_key="p1:dev")]}
    result = audit_card_tables(cards_by_table, _rules())
    assert len(result.missing) == 1
    assert result.missing[0].card.id == "1"


def test_audit_detecta_cross_table_violation_hotfix_299_en_dev_kanban():
    """Caso real encontrado el 2026-09-11 (SPEC §1.3): Hotfix-299 en Dev
    Kanban cae dentro del rango 200-299 dedicado a FB Migration."""
    cards_by_table = {
        "p1:dev": [Card(id="1", title="HOTFIX-299-Algo: desc", card_table_key="p1:dev")],
    }
    result = audit_card_tables(cards_by_table, _rules())
    assert len(result.cross_table_violations) == 1
    assert "FB Migration" in result.cross_table_violations[0].reason


def test_audit_free_range_sin_hallazgos():
    cards_by_table = {
        "p1:dev": [Card(id="1", title="HU-10-Perfil: cambia avatar", card_table_key="p1:dev")],
        "p1:fb": [Card(id="2", title="HOTFIX-250-Migracion: fix", card_table_key="p1:fb")],
    }
    result = audit_card_tables(cards_by_table, _rules())
    assert result.duplicates == []
    assert result.missing == []
    assert result.cross_table_violations == []


def test_audit_solo_opera_sobre_tablas_pasadas_explicitamente():
    """§7.1 — nunca cruza automáticamente con tablas no incluidas en el
    dict pasado por el caller."""
    cards_by_table = {"p1:dev": [Card(id="1", title="HOTFIX-250-X: y", card_table_key="p1:dev")]}
    result = audit_card_tables(cards_by_table, _rules())
    # 250 está fuera del rango de dev (1-199, 302-1000) y colisiona con FB
    # (200-299) — pero como solo se pasó p1:dev, debe detectarse igual
    # porque la regla de FB SIGUE conociéndose (viene en `rules`), aunque
    # sus cards no se leyeron. Esto es intencional: las reglas son
    # metadata de config, no requieren leer las cards de esa tabla.
    assert len(result.cross_table_violations) == 1
