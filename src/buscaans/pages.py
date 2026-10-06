"""Garante que o GitHub Pages publique o feed: reexecuta a publicação que falhou.

Uso no workflow:
  python -m buscaans.pages verificar            # no início: corrige falha de publicação anterior
  python -m buscaans.pages aguardar --sha SHA   # após o push: espera a publicação deste commit
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

import requests

from . import config

log = logging.getLogger("buscaans.pages")
FALHAS = {"failure", "cancelled", "timed_out", "startup_failure"}


class ErroGitHub(RuntimeError):
    pass


class GitHub:
    def __init__(self, cfg_pages: dict, repo: str, token: str):
        self.cfg = cfg_pages
        self.base = f"{cfg_pages['api_url'].rstrip('/')}/repos/{repo}"
        self.http = requests.Session()
        self.http.headers.update({"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"})
        self._workflow_id: int | None = None

    def _pedir(self, metodo: str, caminho: str, **kw) -> dict:
        r = self.http.request(metodo, self.base + caminho, timeout=self.cfg["timeout_segundos"], **kw)
        if r.status_code >= 400:
            raise ErroGitHub(f"{metodo} {caminho} retornou HTTP {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def execucoes(self) -> list[dict]:
        """Execuções recentes da publicação do Pages na branch configurada."""
        if self._workflow_id is None:
            fluxos = self._pedir("GET", "/actions/workflows", params={"per_page": 100})["workflows"]
            achados = [f["id"] for f in fluxos if f["path"] == self.cfg["workflow"]]
            if not achados:
                raise ErroGitHub(f"Workflow {self.cfg['workflow']!r} não encontrado")
            self._workflow_id = achados[0]
        dados = self._pedir("GET", f"/actions/workflows/{self._workflow_id}/runs",
                            params={"branch": self.cfg["branch"], "per_page": 10})
        return dados["workflow_runs"]

    def reexecutar(self, run_id: int) -> None:
        self._pedir("POST", f"/actions/runs/{run_id}/rerun-failed-jobs")


def ultima(execucoes: list[dict], sha: str | None = None) -> dict | None:
    candidatas = [e for e in execucoes if sha is None or e["head_sha"] == sha]
    return max(candidatas, key=lambda e: e["created_at"], default=None)


def falhou(execucao: dict | None) -> bool:
    return bool(execucao) and execucao["status"] == "completed" and execucao["conclusion"] in FALHAS


def verificar(gh) -> bool:
    """Se a publicação mais recente falhou, pede a reexecução. Retorna True se pediu."""
    execucao = ultima(gh.execucoes())
    if not falhou(execucao):
        return False
    log.warning("Publicação %s do commit %s terminou como %s; reexecutando",
                execucao["id"], execucao["head_sha"][:7], execucao["conclusion"])
    gh.reexecutar(execucao["id"])
    return True


def aguardar(gh, sha: str, espera_s: float, intervalo_s: float,
             dormir=time.sleep, relogio=time.monotonic) -> bool:
    """Espera a publicação do commit; reexecuta uma vez se falhar. True se publicou."""
    prazo = relogio() + espera_s
    tentativa_reexecutada = None
    while True:
        execucao = ultima(gh.execucoes(), sha)
        if execucao and execucao["status"] == "completed":
            nova = tentativa_reexecutada is None or execucao["run_attempt"] > tentativa_reexecutada
            if nova and execucao["conclusion"] == "success":
                log.info("Feed publicado (commit %s, tentativa %s)", sha[:7], execucao["run_attempt"])
                return True
            if nova and falhou(execucao):
                if tentativa_reexecutada is not None:
                    log.error("Publicação do commit %s falhou de novo (%s)", sha[:7], execucao["conclusion"])
                    return False
                log.warning("Publicação do commit %s terminou como %s; reexecutando",
                            sha[:7], execucao["conclusion"])
                gh.reexecutar(execucao["id"])
                tentativa_reexecutada = execucao["run_attempt"]
        if relogio() >= prazo:
            log.error("Publicação do commit %s não concluiu em %.0f minutos", sha[:7], espera_s / 60)
            return False
        dormir(intervalo_s)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="buscaans.pages", description=__doc__.splitlines()[0])
    p.add_argument("modo", choices=["verificar", "aguardar"])
    p.add_argument("--sha", default="", help="Commit cuja publicação deve ser aguardada")
    args = p.parse_args(argv)
    if args.modo == "aguardar" and not args.sha:
        p.error("--sha é obrigatório no modo aguardar")
    cfg = config.carregar()["pages"]
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        log.error("GH_TOKEN/GITHUB_TOKEN e GITHUB_REPOSITORY são obrigatórios")
        return 1
    gh = GitHub(cfg, repo, token)
    try:
        if args.modo == "verificar":
            verificar(gh)
            return 0
        return 0 if aguardar(gh, args.sha, cfg["espera_minutos"] * 60, cfg["intervalo_segundos"]) else 1
    except (ErroGitHub, requests.RequestException) as e:
        log.error("Falha ao consultar o GitHub: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
