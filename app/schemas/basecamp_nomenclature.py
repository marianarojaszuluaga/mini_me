"""Autobasecamp SPEC §3.1 — reglas de rango de nomenclatura de cards,
guardadas a nivel de cuenta de Basecamp (no por proyecto de Minime), pero
siempre keyed por card_table_key, lo que ya da independencia por
cliente/proyecto (decisión de producto §7.1, 2026-09-11)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BasecampNomenclatureRule(BaseModel):
    account_id: str
    card_table_key: str  # "{project_id}:{card_table_id}"
    label: str
    reserved_ranges: list[tuple[int, int]] = Field(default_factory=list)
    types: list[str] = Field(default_factory=lambda: ["HU", "BUG", "HOTFIX"])
    # §7.3: apagado por default — sugerencia opcional, nunca automática.
    translate_to_english: bool = False
