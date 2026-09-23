"""Estado persistido: atos já vistos, indexados pelo Autonumber da ANS."""

from __future__ import annotations

import json
from pathlib import Path

VERSAO = 1


class Estado:
    def __init__(self, itens: dict[str, dict] | None = None, novo: bool = False):
        self.itens: dict[str, dict] = itens or {}
        self.novo = novo  # True quando o arquivo não existia (primeira execução)

    @classmethod
    def ler(cls, arquivo: Path) -> "Estado":
        if not arquivo.exists():
            return cls(novo=True)
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        return cls(dados.get("itens", {}))

    def por_guid(self) -> dict[str, str]:
        return {v["guid"]: k for k, v in self.itens.items() if v.get("guid")}

    def podar(self, maximo: int) -> None:
        if len(self.itens) <= maximo:
            return
        ordem = sorted(self.itens, key=lambda k: (self.itens[k].get("dou") or "", self.itens[k]["visto_em"]))
        for k in ordem[: len(self.itens) - maximo]:
            del self.itens[k]

    def gravar(self, arquivo: Path) -> bool:
        """Grava só se o conteúdo mudou. Retorna True se gravou."""
        texto = json.dumps({"versao": VERSAO, "itens": dict(sorted(self.itens.items(), key=lambda kv: int(kv[0])))},
                           ensure_ascii=False, indent=1) + "\n"
        if arquivo.exists() and arquivo.read_text(encoding="utf-8") == texto:
            return False
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(texto, encoding="utf-8", newline="\n")
        return True
