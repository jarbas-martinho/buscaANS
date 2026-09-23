"""Carrega config/defaults.toml e aplica sobrescritas de ambiente BUSCAANS_<SECAO>_<CHAVE>."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_PADRAO = RAIZ / "config" / "defaults.toml"
PREFIXO = "BUSCAANS_"


def _converter(atual, bruto: str):
    if isinstance(atual, bool):
        return bruto.strip().lower() in {"1", "true", "sim", "yes"}
    if isinstance(atual, int):
        return int(bruto)
    if isinstance(atual, list):
        return [p.strip() for p in bruto.split(";") if p.strip()]
    return bruto


def carregar(arquivo: Path | None = None, ambiente: dict[str, str] | None = None) -> dict:
    arquivo = arquivo or Path(os.environ.get(f"{PREFIXO}CONFIG", ARQUIVO_PADRAO))
    ambiente = os.environ if ambiente is None else ambiente
    with open(arquivo, "rb") as f:
        cfg = tomllib.load(f)
    for secao, valores in cfg.items():
        for chave, atual in valores.items():
            nome = f"{PREFIXO}{secao}_{chave}".upper()
            if nome in ambiente:
                valores[chave] = _converter(atual, ambiente[nome])
    return cfg


def caminho(relativo: str) -> Path:
    p = Path(relativo)
    return p if p.is_absolute() else RAIZ / p
