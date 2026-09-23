"""Execução: python -m buscaans"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import config, feed
from .ans_client import ClienteANS, ErroANS
from .estado import Estado
from .filtro import excluido
from .normalizar import data_dou, status_legivel, texto_sem_html

log = logging.getLogger("buscaans")


def atualizar_estado(estado: Estado, atos: list[dict], cliente, cfg: dict, agora: datetime) -> list[str]:
    """Incorpora atos ainda não vistos ao estado. Retorna os Autonumbers novos."""
    fuso = cfg["ans"]["fuso"]
    conhecidos = estado.por_guid()
    novos = []
    for ato in atos:
        if ato["guid"] in conhecidos:
            continue
        try:
            num = cliente.autonumber(ato["guid"])
        except ErroANS as e:  # um ato defeituoso não pode travar a coleta dos demais
            log.warning("Ato ignorado nesta execução: %s", e)
            continue
        if num in estado.itens:  # mesmo ato com guid diferente
            estado.itens[num]["guid"] = ato["guid"]
            continue
        dou = data_dou(ato.get("DataDOU"), fuso)
        titulo = ato.get("Titulo") or ""
        estado.itens[num] = {
            "guid": ato["guid"],
            "titulo": titulo,
            "ementa": texto_sem_html(ato.get("Ementa")),
            "dou": dou.date().isoformat() if dou else None,
            "status": status_legivel(ato.get("Status")),
            "link": cliente.link(num),
            "visto_em": agora.isoformat(timespec="seconds"),
            "excluido": excluido(titulo, cfg["coleta"]["tipos_excluidos"]),
            # Na primeira execução, os atos já existem no SharePoint: ficam fora do feed para
            # o Power Automate não recriá-los.
            "pre_existente": estado.novo,
        }
        novos.append(num)
    return novos


def reenviar(estado: Estado, numeros: list[str]) -> None:
    """Remove atos do estado para que a próxima leitura os trate como novos (entram no feed com data atual)."""
    for n in numeros:
        if not n.isdigit():
            raise ValueError(f"Autonumber inválido para reenvio: {n!r}")
        if estado.itens.pop(n, None) is None:
            log.warning("Reenvio: ato %s não consta do estado; será tratado como novo se estiver entre os lidos", n)
        else:
            log.info("Reenvio: ato %s removido do estado", n)


def itens_do_feed(estado: Estado, quantidade: int) -> list[dict]:
    validos = [(int(k), v) for k, v in estado.itens.items()
               if not v["excluido"] and not v.get("pre_existente")]
    validos.sort(key=lambda kv: (kv[1]["visto_em"], kv[1].get("dou") or "", kv[0]), reverse=True)
    return [v for _, v in validos[:quantidade]]


def executar(cfg: dict, cliente=None, agora: datetime | None = None, reenviar_numeros: list[str] = ()) -> int:
    fuso = ZoneInfo(cfg["ans"]["fuso"])
    agora = (agora or datetime.now(timezone.utc)).astimezone(fuso)
    arq_estado = config.caminho(cfg["estado"]["arquivo"])
    arq_feed = config.caminho(cfg["feed"]["arquivo"])

    estado = Estado.ler(arq_estado)
    reenviar(estado, list(reenviar_numeros))
    cliente = cliente or ClienteANS(cfg["ans"])
    try:
        cliente.abrir()
        atos = cliente.listar(cfg["coleta"]["quantidade"])
        log.info("queryId em uso: %s (candidatos: %d)", cliente.query_id, len(cliente.candidatos))
        novos = atualizar_estado(estado, atos, cliente, cfg, agora)
    finally:
        cliente.fechar()

    for n in novos:
        i = estado.itens[n]
        rotulo = "PRE-EXISTENTE" if i["pre_existente"] else "IGNORADO" if i["excluido"] else "NOVO"
        log.info("%s %s | %s", rotulo, n, i["titulo"])
    estado.podar(cfg["estado"]["maximo"])
    mudou_estado = estado.gravar(arq_estado)
    mudou_feed = feed.gravar(feed.montar(itens_do_feed(estado, cfg["feed"]["itens"]), cfg["feed"]), arq_feed)
    log.info("%d atos lidos, %d novos; estado %s; feed %s", len(atos), len(novos),
             "gravado" if mudou_estado else "sem mudança", "gravado" if mudou_feed else "sem mudança")
    return len(novos)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="buscaans", description="Coleta novas legislações da ANS e gera o feed RSS.")
    p.add_argument("--reenviar", default="",
                   help="Autonumbers separados por vírgula que devem voltar ao feed como novos (ex.: 23651)")
    args = p.parse_args(argv)
    numeros = [n.strip() for n in args.reenviar.split(",") if n.strip()]
    try:
        executar(config.carregar(), reenviar_numeros=numeros)
    except (ErroANS, OSError, ValueError) as e:
        log.error("Falha na coleta: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
