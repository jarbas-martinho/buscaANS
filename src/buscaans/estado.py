"""Estado persistido: atos já vistos, indexados pelo Autonumber da ANS."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from .identidade import IdentidadeConflitante, chave, conferir_conteudo

VERSAO = 2


class Estado:
    def __init__(self, itens: dict[str, dict] | None = None, novo: bool = False):
        self.itens: dict[str, dict] = itens or {}
        self.novo = novo  # True quando o arquivo não existia (primeira execução)

    @classmethod
    def ler(cls, arquivo: Path) -> "Estado":
        if not arquivo.exists():
            return cls(novo=True)
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        if dados.get("versao") not in (1, VERSAO):
            raise ValueError("Versão de estado não suportada")
        return cls(dados.get("itens", {}))

    def por_guid(self) -> dict[str, str]:
        return {guid: k for k, v in self.itens.items()
                for guids in v["identificadores"].values() for guid in guids}

    def por_numero(self) -> dict[str, str]:
        return {num: k for k, v in self.itens.items() for num in v["identificadores"]}

    def consolidar(self) -> int:
        """Migra v1 e concilia duplicados sem perder IDs, pubDate ou pre_existente.

        Mantém a chave do primeiro registro e usa o link do cadastro mais recente.
        Só troca o estado em memória depois de validar todos os grupos.
        """
        resultado: dict[str, dict] = {}
        por_identidade: dict[str, str] = {}
        removidos = 0
        ordem = sorted(self.itens.items(), key=lambda kv: (datetime.fromisoformat(kv[1]["visto_em"]), int(kv[0])))
        for num, original in ordem:
            item = deepcopy(original)
            item["identidade"] = chave(item)
            item.setdefault("rss_guid", item["link"])  # Preserva GUIDs que já foram publicados.
            item.setdefault("identificadores", {num: [item["guid"]]})
            canonico = por_identidade.get(item["identidade"])
            if canonico is None:
                resultado[num] = item
                por_identidade[item["identidade"]] = num
                continue
            anterior = resultado[canonico]
            conferir_conteudo(anterior, item)
            for alias, guids in item["identificadores"].items():
                anterior["identificadores"][alias] = sorted(set(
                    anterior["identificadores"].get(alias, []) + guids
                ))
            for campo in ("guid", "link", "status"):
                anterior[campo] = item[campo]
            removidos += 1
        for campo in ("numero", "guid"):
            donos = {}
            for num, item in resultado.items():
                valores = (item["identificadores"] if campo == "numero" else
                           [g for guids in item["identificadores"].values() for g in guids])
                for valor in valores:
                    if valor in donos and donos[valor] != num:
                        raise IdentidadeConflitante(f"{campo} {valor} associado a normas diferentes")
                    donos[valor] = num
        self.itens = resultado
        return removidos

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
