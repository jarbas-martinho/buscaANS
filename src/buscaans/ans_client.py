"""Cliente do portal da ANS (aplicação Mendix) via endpoint /xas/, com sessão anônima."""

from __future__ import annotations

import json
import re

import requests


class ErroANS(RuntimeError):
    pass


def descobrir_query_ids(pagina_xml: str, entidade: str) -> list[str]:
    """queryIds dos datasources da lista: entidade informada, ordenados por DataDOU e com o filtro de revogadas.
    A página tem várias grades equivalentes (variações de layout); todas devolvem o mesmo resultado."""
    padrao = re.compile(
        r'"entity":"' + re.escape(entidade) + r'"[^{}]*?"queryId":"([^"]+)"[^{}]*?"sort":\[\["DataDOU","desc"\]\],'
        r'"arguments":\{[^{}]*?"currentObject\$RevogadasIncluir"'
    )
    return list(dict.fromkeys(padrao.findall(pagina_xml)))


class ClienteANS:
    def __init__(self, cfg_ans: dict, sessao: requests.Session | None = None):
        self.cfg = cfg_ans
        self.base = cfg_ans["base_url"].rstrip("/")
        self.timeout = cfg_ans["timeout_segundos"]
        self.http = sessao or requests.Session()
        self.http.headers["User-Agent"] = cfg_ans["user_agent"]
        self.csrf: str | None = None
        self.candidatos: list[str] = []
        self.query_id: str | None = None

    def _xas(self, corpo: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.csrf:
            headers["X-Csrf-Token"] = self.csrf
        r = self.http.post(f"{self.base}/xas/", data=json.dumps(corpo), headers=headers, timeout=self.timeout)
        if r.status_code != 200:
            raise ErroANS(f"/xas/ {corpo.get('action')} retornou HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def abrir(self) -> None:
        self.http.get(f"{self.base}/index.html", timeout=self.timeout).raise_for_status()
        dados = self._xas({
            "action": "get_session_data",
            "params": {
                "hybrid": False, "offline": False, "referrer": None, "profile": "Responsive",
                "timezoneoffset": 180, "timezoneId": self.cfg["fuso"],
                "preferredLanguages": ["pt-BR"], "version": 2,
            },
        })
        self.csrf = dados.get("csrftoken")
        if not self.csrf:
            raise ErroANS("Sessão anônima sem csrftoken")
        r = self.http.get(f"{self.base}{self.cfg['pagina_xml']}", timeout=self.timeout)
        r.raise_for_status()
        candidatos = descobrir_query_ids(r.text, self.cfg["entidade"])
        self.candidatos = list(dict.fromkeys(candidatos + [self.cfg["query_id_reserva"]]))

    def listar(self, quantidade: int) -> list[dict]:
        """Atos mais recentes por data do DOU. Retorna [{guid, Titulo, Ementa, DataDOU, Status}].
        Tenta cada queryId candidato até um responder com itens."""
        erros = []
        for qid in self.candidatos:
            try:
                itens = self._listar(qid, quantidade)
            except ErroANS as e:
                erros.append(f"{qid}: {e}")
                continue
            self.query_id = qid
            return itens
        raise ErroANS("Nenhum queryId funcionou (página da ANS alterada?): " + " | ".join(erros))

    def _listar(self, query_id: str, quantidade: int) -> list[dict]:
        dados = self._xas({
            "action": "retrieve",
            "params": {
                "queryId": query_id,
                "params": {"currentObject$RevogadasIncluir": {"value": self.cfg["incluir_revogadas"]}},
                "options": {
                    "offset": 0, "amount": quantidade, "sort": [["DataDOU", "desc"]],
                    "wantCount": True, "extraXpath": "",
                },
            },
            "changes": {}, "objects": [],
        })
        objetos = dados.get("partialObjects") or dados.get("objects") or []
        if not objetos:
            raise ErroANS("Lista de legislações veio vazia (queryId inválido ou página alterada?)")
        return [_achatar(o) for o in objetos]

    def autonumber(self, guid: str) -> str:
        dados = self._xas({"action": "retrieve_by_ids", "params": {"ids": [guid], "schema": {}}})
        objs = dados.get("objects") or []
        if not objs:
            raise ErroANS(f"Objeto {guid} não encontrado")
        valor = objs[0]["attributes"].get("Autonumber", {}).get("value")
        if not valor or str(valor) == "0":
            raise ErroANS(f"Objeto {guid} sem Autonumber")
        return str(valor)

    def link(self, autonumber: str) -> str:
        return self.base + self.cfg["link_legislacao"].format(autonumber=autonumber)

    def fechar(self) -> None:
        try:
            if self.csrf:
                self._xas({"action": "logout"})
        except Exception:  # logout é cortesia; falha não compromete a coleta
            pass
        self.http.close()


def _achatar(obj: dict) -> dict:
    saida = {"guid": obj["guid"]}
    for nome, attr in obj.get("attributes", {}).items():
        if isinstance(attr, dict) and "value" in attr:
            saida[nome] = attr["value"]
    return saida
