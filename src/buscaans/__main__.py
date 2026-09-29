"""Execução: python -m buscaans"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import config, feed
from .ans_client import ClienteANS, ErroANS
from .estado import Estado
from .filtro import excluido
from .identidade import IdentidadeConflitante, chave, conferir_conteudo, guid_rss
from .normalizar import data_dou, status_legivel, texto_sem_html
from .protecao import LoteSuspeito, validar

log = logging.getLogger("buscaans")


def atualizar_estado(estado: Estado, atos: list[dict], cliente, cfg: dict, agora: datetime,
                     eventos: list[dict], reenviar_numeros: list[str]) -> list[str]:
    """Incorpora atos ainda não vistos ao estado. Retorna os Autonumbers novos."""
    fuso = cfg["ans"]["fuso"]
    conhecidos = estado.por_guid()
    numeros = estado.por_numero()
    identidades = {v["identidade"]: k for k, v in estado.itens.items()}
    solicitados = set(reenviar_numeros)
    atendidos = set()
    novos = []
    for ato in atos:
        dou = data_dou(ato.get("DataDOU"), fuso)
        titulo = ato.get("Titulo") or ""
        recebido = {
            "guid": ato["guid"],
            "titulo": titulo,
            "ementa": texto_sem_html(ato.get("Ementa")),
            "dou": dou.date().isoformat() if dou else None,
            "status": status_legivel(ato.get("Status")),
            "visto_em": agora.isoformat(timespec="seconds"),
            "excluido": excluido(titulo, cfg["coleta"]["tipos_excluidos"]),
            # Na primeira execução, os atos já existem no SharePoint: ficam fora do feed para
            # o Power Automate não recriá-los.
            "pre_existente": estado.novo,
        }
        identidade = chave(recebido)
        canonico = conhecidos.get(ato["guid"])
        if canonico is not None:
            num = next(n for n, guids in estado.itens[canonico]["identificadores"].items()
                       if ato["guid"] in guids)
        else:
            try:
                num = cliente.autonumber(ato["guid"])
            except ErroANS as e:
                log.warning("Ato ignorado nesta execução: %s", e)
                continue
            canonico = numeros.get(num) or identidades.get(identidade)
        acao = None
        if canonico is not None:
            item = estado.itens[canonico]
            conferir_conteudo(item, recebido)
            aliases = item["identificadores"]
            if ato["guid"] not in aliases.get(num, []):
                aliases.setdefault(num, []).append(ato["guid"])
                aliases[num].sort()
                item["guid"] = ato["guid"]
                item["link"] = cliente.link(num)
                acao = "novo_identificador"
            item["status"] = recebido["status"]
        else:
            canonico = num
            item = recebido
            item.update(identidade=identidade, rss_guid=guid_rss(identidade),
                        identificadores={num: [ato["guid"]]}, link=cliente.link(num))
            estado.itens[canonico] = item
            novos.append(canonico)
            acao = "novo"
        pedidos = solicitados.intersection(item["identificadores"])
        if pedidos:
            item["visto_em"] = agora.isoformat(timespec="seconds")
            item["pre_existente"] = False
            atendidos.update(pedidos)
            if canonico not in novos:
                novos.append(canonico)
            # Reenvio explícito dispensa o alerta de DOU antigo, mas não o de troca de IDs.
            if acao in (None, "novo"):
                acao = "reenvio"
        if acao:
            eventos.append({"acao": acao, "numero": num, "guid": ato["guid"],
                            "identidade": identidade, "titulo": titulo, "ementa": recebido["ementa"],
                            "link": cliente.link(num),
                            "dou": recebido["dou"], "status": recebido["status"],
                            "excluido": recebido["excluido"]})
        conhecidos[ato["guid"]] = canonico
        numeros[num] = canonico
        identidades[identidade] = canonico
    for n in solicitados - atendidos:
        log.warning("Reenvio: ato %s não foi encontrado entre os atos lidos", n)
    return novos


def registrar_resumo(texto: str) -> None:
    log.warning("%s", texto)
    if caminho := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(texto + "\n")


def itens_do_feed(estado: Estado, quantidade: int) -> list[dict]:
    validos = [(int(k), v) for k, v in estado.itens.items()
               if not v["excluido"] and not v.get("pre_existente")]
    validos.sort(key=lambda kv: (kv[1]["visto_em"], kv[1].get("dou") or "", kv[0]), reverse=True)
    return [v for _, v in validos[:quantidade]]


def executar(cfg: dict, cliente=None, agora: datetime | None = None, reenviar_numeros: list[str] = (),
             aprovar_lote: str = "") -> int:
    fuso = ZoneInfo(cfg["ans"]["fuso"])
    agora = (agora or datetime.now(timezone.utc)).astimezone(fuso)
    arq_estado = config.caminho(cfg["estado"]["arquivo"])
    arq_feed = config.caminho(cfg["feed"]["arquivo"])

    estado = Estado.ler(arq_estado)
    for n in reenviar_numeros:
        if not n.isdigit():
            raise ValueError(f"Autonumber inválido para reenvio: {n!r}")
    estado.consolidar()
    antes = deepcopy(estado.itens)
    eventos: list[dict] = []
    cliente = cliente or ClienteANS(cfg["ans"])
    try:
        cliente.abrir()
        atos = cliente.listar(cfg["coleta"]["quantidade"])
        log.info("queryId em uso: %s (candidatos: %d)", cliente.query_id, len(cliente.candidatos))
        novos = atualizar_estado(estado, atos, cliente, cfg, agora, eventos, list(reenviar_numeros))
    finally:
        cliente.fechar()

    if not estado.novo:
        try:
            resumo = validar(antes, eventos, cfg, agora.date(), aprovar_lote)
        except LoteSuspeito as e:
            registrar_resumo(e.resumo)
            raise
        if resumo:
            registrar_resumo(resumo)
    elif aprovar_lote:
        raise ValueError("Não é possível aprovar lote durante a semeadura inicial")
    for n in novos:
        i = estado.itens[n]
        rotulo = "PRE-EXISTENTE" if i["pre_existente"] else "IGNORADO" if i["excluido"] else "NOVO"
        log.info("%s %s | %s", rotulo, n, i["titulo"])
    estado.podar(cfg["estado"]["maximo"])
    texto_feed = feed.montar(itens_do_feed(estado, cfg["feed"]["itens"]), cfg["feed"])
    mudou_estado = estado.gravar(arq_estado)
    mudou_feed = feed.gravar(texto_feed, arq_feed)
    log.info("%d atos lidos, %d novos; estado %s; feed %s", len(atos), len(novos),
             "gravado" if mudou_estado else "sem mudança", "gravado" if mudou_feed else "sem mudança")
    return len(novos)


def conciliar_estado(cfg: dict) -> int:
    """Repara apenas os arquivos locais; não consulta a ANS nem atribui datas atuais."""
    arq_estado = config.caminho(cfg["estado"]["arquivo"])
    estado = Estado.ler(arq_estado)
    if estado.novo:
        raise ValueError("Estado não encontrado para conciliação")
    quantidade = estado.consolidar()
    texto = feed.montar(itens_do_feed(estado, cfg["feed"]["itens"]), cfg["feed"])
    estado.gravar(arq_estado)
    feed.gravar(texto, config.caminho(cfg["feed"]["arquivo"]))
    log.info("%d registros duplicados conciliados; %d normas preservadas", quantidade, len(estado.itens))
    return quantidade


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="buscaans", description="Coleta novas legislações da ANS e gera o feed RSS.")
    p.add_argument("--reenviar", default="",
                   help="Autonumbers separados por vírgula que devem voltar ao feed como novos (ex.: 23651)")
    p.add_argument("--aprovar-lote", default="", help="Código exato exibido no bloqueio do lote revisado")
    p.add_argument("--conciliar-estado", action="store_true", help="Conciliar estado/feed locais, sem acessar a ANS")
    args = p.parse_args(argv)
    if args.conciliar_estado and (args.reenviar or args.aprovar_lote):
        p.error("Conciliação local não pode ser combinada com reenvio ou aprovação de lote")
    numeros = [n.strip() for n in args.reenviar.split(",") if n.strip()]
    try:
        if args.conciliar_estado:
            conciliar_estado(config.carregar())
        else:
            executar(config.carregar(), reenviar_numeros=numeros, aprovar_lote=args.aprovar_lote.strip())
    except IdentidadeConflitante as e:
        registrar_resumo(f"## Coleta bloqueada por conflito de identidade\n\n{e}\n\n"
                         "Estado e feed não foram gravados. Este conflito exige conciliação do conteúdo; "
                         "a aprovação de lote não o libera.")
        return 1
    except (ErroANS, OSError, ValueError) as e:
        log.error("Falha na coleta: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
