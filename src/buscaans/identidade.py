"""Identidade do ato independente dos identificadores do cadastro Mendix."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date

MESES = dict(zip(
    "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro".split(),
    range(1, 13),
))
TITULO = re.compile(
    r"(.+?) (?:n|no|numero) (\d+) (?:de )?(\d{1,2}) (?:de )?([a-z]+) (?:de )?(\d{4})"
)


class IdentidadeConflitante(ValueError):
    """Exige análise do conteúdo; não pode ser liberada como simples lote volumoso."""


def normalizar_titulo(titulo: str) -> str:
    texto = unicodedata.normalize("NFKD", titulo.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", texto).split())


def chave(item: dict) -> str:
    titulo = normalizar_titulo(item["titulo"])
    if not titulo:
        raise IdentidadeConflitante("Ato sem título: identidade não verificável.")
    partes = ["titulo-v1", titulo]
    m = TITULO.fullmatch(titulo)
    if m and m[4] in MESES:
        try:
            data_ato = date(int(m[5]), MESES[m[4]], int(m[3])).isoformat()
        except ValueError:
            pass  # Título não reconhecido: comparação conservadora pelo texto completo.
        else:
            partes = ["ato-v1", m[1], str(int(m[2])), data_ato]
    # DOU distinto pode indicar republicação. Nunca fundir só pelo número/ano.
    partes.append(item.get("dou") or "")
    return json.dumps(partes, ensure_ascii=False, separators=(",", ":"))


def conferir_conteudo(anterior: dict, recebido: dict) -> None:
    def ementa(item):
        return " ".join(unicodedata.normalize("NFC", item.get("ementa") or "").split())

    if chave(anterior) != chave(recebido) or ementa(anterior) != ementa(recebido):
        raise IdentidadeConflitante(
            f"Identidade ou ementa divergente para {recebido['titulo']!r}. "
            "Possível retificação, republicação ou reutilização de ID; revisar antes de conciliar."
        )


def guid_rss(identidade: str) -> str:
    return "urn:buscaans:ato:" + hashlib.sha256(identidade.encode("utf-8")).hexdigest()
