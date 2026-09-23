"""Exclusão de atos pelo tipo, identificado pelo início do título."""

from __future__ import annotations


def excluido(titulo: str, tipos_excluidos: list[str]) -> bool:
    t = (titulo or "").strip().casefold()
    return any(t.startswith(tipo.strip().casefold()) for tipo in tipos_excluidos if tipo.strip())
