"""Proteção da publicação no GitHub Pages, com GitHub e relógio simulados."""

import pytest

from buscaans.pages import aguardar, verificar

SHA = "e0405d4a1b2c"


def execucao(id_, conclusao, sha=SHA, status="completed", tentativa=1, criada="2026-10-06T11:19:39Z"):
    return {"id": id_, "head_sha": sha, "status": status, "conclusion": conclusao,
            "run_attempt": tentativa, "created_at": criada}


class GitHubFalso:
    """Devolve, a cada consulta, o próximo retrato da lista de execuções."""

    def __init__(self, *retratos):
        self.retratos = list(retratos)
        self.reexecutadas = []

    def execucoes(self):
        return self.retratos.pop(0) if len(self.retratos) > 1 else self.retratos[0]

    def reexecutar(self, run_id):
        self.reexecutadas.append(run_id)


class Relogio:
    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora

    def dormir(self, segundos):
        self.agora += segundos


def esperar(gh, espera_s=1200):
    r = Relogio()
    return aguardar(gh, SHA, espera_s, 15, dormir=r.dormir, relogio=r), r.agora


@pytest.mark.parametrize("conclusao", ["failure", "cancelled", "timed_out"])
def test_verificar_reexecuta_publicacao_mais_recente_que_falhou(conclusao):
    gh = GitHubFalso([execucao(2, conclusao, criada="2026-10-05T20:45:17Z"),
                      execucao(1, "success", sha="antigo", criada="2026-10-03T00:32:17Z")])
    assert verificar(gh) is True
    assert gh.reexecutadas == [2]


@pytest.mark.parametrize("execucoes", [
    [],
    [execucao(2, "success", criada="2026-10-06T11:19:39Z"),
     execucao(1, "cancelled", sha="antigo", criada="2026-10-05T20:45:17Z")],  # falha já superada
    [execucao(2, None, status="in_progress")],  # ainda publicando
])
def test_verificar_nao_mexe_quando_nao_ha_falha_vigente(execucoes):
    gh = GitHubFalso(execucoes)
    assert verificar(gh) is False
    assert gh.reexecutadas == []


def test_aguardar_espera_a_execucao_do_commit_aparecer_e_concluir():
    gh = GitHubFalso([], [execucao(5, None, status="queued")], [execucao(5, "success")])
    ok, decorrido = esperar(gh)
    assert ok and gh.reexecutadas == [] and decorrido == 30


def test_aguardar_ignora_publicacoes_de_outros_commits():
    gh = GitHubFalso([execucao(4, "success", sha="outro")], [execucao(5, "success")])
    assert esperar(gh)[0] is True


def test_publicacao_cancelada_e_reexecutada_uma_vez_e_conclui():
    # Caso real de 05/10: publicação travada, cancelada pelo GitHub; a reexecução publicou.
    gh = GitHubFalso([execucao(5, "cancelled")],
                     [execucao(5, "cancelled")],                     # API ainda mostra a tentativa 1
                     [execucao(5, None, status="in_progress", tentativa=2)],
                     [execucao(5, "success", tentativa=2)])
    ok, _ = esperar(gh)
    assert ok and gh.reexecutadas == [5]


def test_segunda_falha_encerra_com_erro_sem_reexecutar_de_novo():
    gh = GitHubFalso([execucao(5, "failure")], [execucao(5, "failure", tentativa=2)])
    ok, _ = esperar(gh)
    assert ok is False and gh.reexecutadas == [5]


def test_prazo_esgotado_encerra_com_erro():
    gh = GitHubFalso([execucao(5, None, status="in_progress")])
    ok, decorrido = esperar(gh, espera_s=60)
    assert ok is False and decorrido == 60
