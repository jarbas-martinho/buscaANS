"""Bloqueia lotes suspeitos antes de gravar estado/feed. Aprovação vinculada ao conteúdo."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta


class LoteSuspeito(ValueError):
    def __init__(self, motivos: list[str], resumo: str, codigo: str):
        self.codigo = codigo
        self.resumo = resumo
        super().__init__("Coleta bloqueada: " + "; ".join(motivos) + f". Código de revisão: {codigo}")


def validar(antes: dict, eventos: list[dict], cfg: dict, hoje: date, aprovacao: str = "") -> str:
    limites = cfg["protecao"]
    if any(not isinstance(v, int) or v < 1 for v in limites.values()):
        raise ValueError("Os limites de proteção devem ser inteiros positivos")
    novos = [e for e in eventos if e["acao"] == "novo"]
    trocas = {e["identidade"] for e in eventos if e["acao"] == "novo_identificador"}
    antigos = [e for e in novos if not e["excluido"] and (
        not e["dou"] or date.fromisoformat(e["dou"]) < hoje - timedelta(days=limites["atraso_dou_dias"])
    )]
    motivos = []
    if len(trocas) >= limites["limite_trocas"]:
        motivos.append(f"{len(trocas)} normas com troca de identificador")
    if len(novos) >= limites["limite_novos"]:
        motivos.append(f"{len(novos)} atos desconhecidos no mesmo lote")
    if antigos:
        motivos.append(f"{len(antigos)} normas desconhecidas com DOU antigo ou ausente")
    # Não inclui a hora da execução: permite revisar e repetir o MESMO lote depois.
    base = {"estado": antes, "eventos": sorted(eventos, key=lambda e: json.dumps(e, sort_keys=True)),
            "limites": limites, "motivos": motivos}
    codigo = hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    if not motivos:
        if aprovacao:
            raise ValueError("Código de aprovação fornecido, mas este lote não é o lote suspeito revisado")
        return ""
    linhas = ["## Revisão da coleta", "", *[f"- {m}" for m in motivos], "",
              "| Ação | ID recebido | Norma | DOU | Fora do feed |", "|---|---|---|---|---|"]
    for e in eventos:
        titulo = e["titulo"].replace("|", "\\|").replace("\n", " ").replace("<", "&lt;")
        linhas.append(f"| {e['acao']} | [{e['numero']}]({e['link']}) | {titulo} | "
                      f"{e['dou'] or 'ausente'} | {e['excluido']} |")
    linhas += ["", f"Código do lote: `{codigo}`", "",
               "Após revisar os registros, execute manualmente com `aprovar_lote` igual a esse código.",
               "Se o estado ou os candidatos mudarem, será necessária outra revisão."]
    resumo = "\n".join(linhas) + "\n"
    if aprovacao != codigo:
        raise LoteSuspeito(motivos, resumo, codigo)
    return "Lote aprovado explicitamente.\n\n" + resumo
