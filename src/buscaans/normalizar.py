"""Conversões de campos vindos da ANS."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_TAG = re.compile(r"<[^>]+>")
_ESPACOS = re.compile(r"\s+")


def texto_sem_html(valor: str | None) -> str:
    if not valor:
        return ""
    return _ESPACOS.sub(" ", html.unescape(_TAG.sub(" ", valor))).strip()


def data_dou(epoch_ms: int | str | None, fuso: str) -> datetime | None:
    """DataDOU vem em epoch ms representando meia-noite no fuso de São Paulo."""
    if epoch_ms in (None, ""):
        return None
    return datetime.fromtimestamp(int(epoch_ms) / 1000, tz=timezone.utc).astimezone(ZoneInfo(fuso))


def status_legivel(valor: str | None) -> str:
    """Enumeração do Mendix ('NaoVigente') para o texto exibido no portal ('Não vigente')."""
    if not valor:
        return ""
    texto = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", valor).capitalize()
    return re.sub(r"\bNao\b", "Não", texto)
