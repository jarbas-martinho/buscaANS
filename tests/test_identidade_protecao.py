"""Regressão do incidente real e dos limites de publicação, sem chamadas à ANS."""

import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from buscaans import config, feed
from buscaans.__main__ import conciliar_estado, executar, itens_do_feed, main
from buscaans.estado import Estado
from buscaans.identidade import IdentidadeConflitante, chave
from buscaans.protecao import LoteSuspeito

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 9, 28, 22, 1, 14, tzinfo=FUSO)
INCIDENTE = Path(__file__).parent / "fixtures" / "incidente_2026_09_28.json"


@pytest.fixture
def cfg(tmp_path):
    c = config.carregar(ambiente={})
    c["estado"]["arquivo"] = str(tmp_path / "estado.json")
    c["feed"]["arquivo"] = str(tmp_path / "feed.xml")
    return c


def incidente():
    return json.loads(INCIDENTE.read_text(encoding="utf-8"))["itens"]


def preparar(cfg, itens):
    # Mantém a representação legada para provar que bloqueios nem sequer migram o arquivo.
    Path(cfg["estado"]["arquivo"]).write_text(json.dumps({"versao": 1, "itens": itens}), encoding="utf-8")
    feed.gravar(feed.montar(itens_do_feed(Estado(itens), 50), cfg["feed"]), Path(cfg["feed"]["arquivo"]))


def arquivos(cfg):
    return tuple(Path(cfg[secao]["arquivo"]).read_bytes() for secao in ("estado", "feed"))


def publicados(cfg):
    return ET.parse(cfg["feed"]["arquivo"]).findall("./channel/item")


class Cliente:
    query_id = "consulta-simulada"
    candidatos = [query_id]

    def __init__(self, itens):
        self.itens = itens
        self.encerrado = False

    def abrir(self):
        pass

    def fechar(self):
        self.encerrado = True

    def listar(self, quantidade):
        return [{"guid": i["guid"], "Titulo": i["titulo"], "Ementa": i["ementa"],
                 "DataDOU": int(datetime.fromisoformat(i["dou"]).replace(tzinfo=FUSO).timestamp() * 1000)
                 if i.get("dou") else None,
                 "Status": "NaoVigente" if i["status"] == "Não vigente" else i["status"]}
                for i in self.itens.values()][:quantidade]

    def autonumber(self, guid):
        return next(n for n, i in self.itens.items() if i["guid"] == guid)

    def link(self, num):
        return f"https://componentes-portal.ans.gov.br/link/legislacao/{num}"


def registro_novo(numero="681", dou="2026-09-28"):
    item = deepcopy(incidente()["25522"])
    item.update(titulo=f"Resolução Normativa - RN ANS nº {numero}, de 28 setembro 2026",
                dou=dou, guid=f"novo-{numero}")
    return item


def test_chave_normaliza_grafia_sem_confundir_normas():
    item = incidente()["23651"]
    variante = dict(item, titulo="  RESOLUCAO NORMATIVA - RN ANS N. 0680, de 18 de setembro de 2026  ")
    assert chave(item) == chave(variante)
    for outro in [dict(item, titulo=item["titulo"].replace("ANS", "DIPRO")),
                  dict(item, titulo=item["titulo"].replace("680", "681")),
                  dict(item, titulo=item["titulo"].replace("18 setembro", "19 setembro")),
                  dict(item, titulo=item["titulo"] + " - Retificação"),
                  dict(item, dou="2026-09-23")]:
        assert chave(item) != chave(outro)


def test_conciliacao_real_preserva_as_70_referencias_e_o_feed_original(cfg):
    origem = incidente()
    preparar(cfg, origem)
    assert conciliar_estado(cfg) == 29
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert len(e.itens) == 41
    assert set(e.por_numero()) == set(origem)
    assert set(e.por_guid()) == {i["guid"] for i in origem.values()}
    for antigo, novo in [("23651", "25522"), ("21753", "25468"), ("11892", "25460"),
                         ("12043", "25626"), ("12554", "25465")]:
        item = e.itens[antigo]
        assert item["visto_em"] == origem[antigo]["visto_em"]
        assert item["pre_existente"] == origem[antigo]["pre_existente"]
        assert item["link"] == origem[novo]["link"]
        assert item["rss_guid"] == origem[antigo]["link"]
    rss = publicados(cfg)
    assert len(rss) == 1
    assert rss[0].findtext("pubDate") == "Wed, 23 Sep 2026 17:16:45 -0300"
    assert rss[0].findtext("guid").endswith("/23651")
    assert rss[0].findtext("link").endswith("/25522")
    antes = arquivos(cfg)
    assert conciliar_estado(cfg) == 0
    assert arquivos(cfg) == antes


@pytest.mark.parametrize("numero", ["23651", "25522"])
def test_reenvio_aceita_identificador_antigo_ou_atual_sem_perder_aliases(cfg, numero):
    preparar(cfg, incidente())
    conciliar_estado(cfg)
    assert executar(cfg, Cliente({"25522": incidente()["25522"]}), AGORA, [numero]) == 1
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert len(e.itens) == 41
    assert e.por_numero()["23651"] == e.por_numero()["25522"]
    assert publicados(cfg)[0].findtext("pubDate") == "Mon, 28 Sep 2026 22:01:14 -0300"


@pytest.mark.parametrize("antigo,novo", [("23651", "25522"), ("21753", "25468")])
def test_troca_de_identificador_nao_republica_nem_perde_semeadura(cfg, antigo, novo):
    origem = incidente()
    preparar(cfg, {antigo: origem[antigo]})
    assert executar(cfg, Cliente({novo: origem[novo]}), AGORA) == 0
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert len(e.itens) == 1
    assert e.itens[antigo]["visto_em"] == origem[antigo]["visto_em"]
    assert e.itens[antigo]["pre_existente"] == origem[antigo]["pre_existente"]
    antes = arquivos(cfg)
    # O portal pode alternar entre cadastros antigos/novos sem gerar outra publicação.
    assert executar(cfg, Cliente({antigo: origem[antigo], novo: origem[novo]}), AGORA) == 0
    assert arquivos(cfg) == antes


def test_mesmo_numero_com_outro_guid_nao_republica(cfg):
    item = incidente()["23651"]
    preparar(cfg, {"23651": item})
    assert executar(cfg, Cliente({"23651": dict(item, guid="outro-guid")}), AGORA) == 0
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert e.itens["23651"]["identificadores"]["23651"] == sorted([item["guid"], "outro-guid"])


@pytest.mark.parametrize("manter_id", [True, False])
def test_ementa_divergente_exige_revisao_sem_gravar(cfg, manter_id):
    origem = incidente()
    preparar(cfg, {"23651": origem["23651"]})
    antes = arquivos(cfg)
    num = "23651" if manter_id else "25522"
    item = dict(origem[num], ementa="Texto retificado, materialmente diferente")
    with pytest.raises(IdentidadeConflitante):
        executar(cfg, Cliente({num: item}), AGORA, aprovar_lote="qualquer-codigo")
    assert arquivos(cfg) == antes


def test_replay_do_lote_real_bloqueia_e_aprovacao_so_libera_o_mesmo_lote(cfg, tmp_path, monkeypatch):
    origem = incidente()
    anteriores = {n: i for n, i in origem.items() if i["visto_em"] != AGORA.isoformat()}
    recebidos = {n: i for n, i in origem.items() if i["visto_em"] == AGORA.isoformat()}
    assert len(anteriores) == 40 and len(recebidos) == 30
    preparar(cfg, anteriores)
    antes = arquivos(cfg)
    resumo = tmp_path / "resumo.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumo))
    cliente = Cliente(recebidos)
    with pytest.raises(LoteSuspeito) as erro:
        executar(cfg, cliente, AGORA)
    assert cliente.encerrado
    assert arquivos(cfg) == antes
    assert "29 normas com troca" in str(erro.value)
    assert "25522" in resumo.read_text(encoding="utf-8")
    codigo = erro.value.codigo
    for mudanca in [dict(recebidos, adicional=registro_novo()), recebidos]:
        with pytest.raises(LoteSuspeito):
            executar(cfg, Cliente(mudanca), AGORA, aprovar_lote=codigo if mudanca != recebidos else "errado")
        assert arquivos(cfg) == antes
    assert executar(cfg, Cliente(recebidos), AGORA + timedelta(minutes=5), aprovar_lote=codigo) == 1
    assert len(Estado.ler(Path(cfg["estado"]["arquivo"])).itens) == 41
    assert len(publicados(cfg)) == 1
    assert publicados(cfg)[0].findtext("pubDate") == "Wed, 23 Sep 2026 17:16:45 -0300"
    # Não há autorização persistente: código antigo também não funciona sobre o estado atualizado.
    depois = arquivos(cfg)
    with pytest.raises(ValueError, match="não é o lote"):
        executar(cfg, Cliente(recebidos), AGORA, aprovar_lote=codigo)
    assert arquivos(cfg) == depois


@pytest.mark.parametrize("dou", ["2026-07-01", None])
def test_norma_desconhecida_antiga_ou_sem_data_bloqueia(cfg, dou):
    preparar(cfg, {"23651": incidente()["23651"]})
    antes = arquivos(cfg)
    with pytest.raises(LoteSuspeito, match="DOU antigo ou ausente"):
        executar(cfg, Cliente({"30000": registro_novo(dou=dou)}), AGORA)
    assert arquivos(cfg) == antes


def test_lote_volumoso_de_normas_recentes_bloqueia(cfg):
    preparar(cfg, {"23651": incidente()["23651"]})
    antes = arquivos(cfg)
    itens = {str(30000 + n): registro_novo(str(700 + n)) for n in range(10)}
    with pytest.raises(LoteSuspeito, match="10 atos desconhecidos"):
        executar(cfg, Cliente(itens), AGORA)
    assert arquivos(cfg) == antes


def test_norma_realmente_nova_entra_uma_vez_com_guid_estavel(cfg):
    preparar(cfg, {"23651": incidente()["23651"]})
    item = registro_novo()
    assert executar(cfg, Cliente({"30000": item}), AGORA) == 1
    rss = publicados(cfg)
    assert len(rss) == 2
    guid = rss[0].findtext("guid")
    assert guid.startswith("urn:buscaans:ato:")
    assert executar(cfg, Cliente({"40000": dict(item, guid="novo-id")}), AGORA + timedelta(days=1)) == 0
    assert publicados(cfg)[0].findtext("guid") == guid
    assert publicados(cfg)[0].findtext("pubDate") == "Mon, 28 Sep 2026 22:01:14 -0300"


def test_cli_conciliacao_e_bloqueio_retornam_status_adequado(cfg, monkeypatch):
    preparar(cfg, incidente())
    monkeypatch.setattr(config, "carregar", lambda: cfg)
    monkeypatch.setattr("buscaans.__main__.ClienteANS", lambda _: pytest.fail("Conciliação acessou a rede"))
    assert main(["--conciliar-estado"]) == 0
    antes = arquivos(cfg)
    monkeypatch.setattr("buscaans.__main__.ClienteANS", lambda _: Cliente({"30000": registro_novo(dou=None)}))
    assert main([]) == 1
    assert arquivos(cfg) == antes


@pytest.mark.parametrize("mudanca", ["orgao", "dou", "retificacao"])
def test_outro_orgao_ou_republicacao_nao_e_fundido(cfg, mudanca):
    item = registro_novo()
    preparar(cfg, {"30000": item})
    recebido = dict(item, guid="outro-registro")
    if mudanca == "orgao":
        recebido["titulo"] = item["titulo"].replace("ANS", "DIPRO")
    elif mudanca == "dou":
        recebido["dou"] = "2026-09-29"
    else:
        recebido["titulo"] += " - Retificação"
    assert executar(cfg, Cliente({"40000": recebido}), AGORA + timedelta(days=1)) == 1
    assert len(Estado.ler(Path(cfg["estado"]["arquivo"])).itens) == 2
    assert len(publicados(cfg)) == 2


def test_reutilizacao_de_numero_para_outra_norma_bloqueia(cfg):
    preparar(cfg, {"23651": incidente()["23651"]})
    antes = arquivos(cfg)
    with pytest.raises(IdentidadeConflitante):
        executar(cfg, Cliente({"23651": registro_novo()}), AGORA)
    assert arquivos(cfg) == antes


def test_aprovacao_invalida_se_estado_base_muda(cfg):
    preparar(cfg, {"23651": incidente()["23651"]})
    cliente = Cliente({"30000": registro_novo(dou=None)})
    with pytest.raises(LoteSuspeito) as erro:
        executar(cfg, cliente, AGORA)
    preparar(cfg, {"23651": incidente()["23651"], "21753": incidente()["21753"]})
    antes = arquivos(cfg)
    with pytest.raises(LoteSuspeito) as outro:
        executar(cfg, cliente, AGORA, aprovar_lote=erro.value.codigo)
    assert outro.value.codigo != erro.value.codigo
    assert arquivos(cfg) == antes


def test_conciliacao_com_ementa_divergente_nao_grava(cfg):
    origem = incidente()
    origem["25522"]["ementa"] = "Retificação que precisa de análise"
    preparar(cfg, origem)
    antes = arquivos(cfg)
    with pytest.raises(IdentidadeConflitante):
        conciliar_estado(cfg)
    assert arquivos(cfg) == antes


def test_limite_de_trocas_exige_revisao_no_limiar(cfg):
    origem = incidente()
    pares = [("23651", "25522"), ("21753", "25468"), ("11892", "25460"),
             ("12043", "25626"), ("12554", "25465")]
    preparar(cfg, {a: origem[a] for a, _ in pares})
    antes = arquivos(cfg)
    with pytest.raises(LoteSuspeito, match="5 normas com troca"):
        executar(cfg, Cliente({b: origem[b] for _, b in pares}), AGORA)
    assert arquivos(cfg) == antes
    assert executar(cfg, Cliente({b: origem[b] for _, b in pares[:4]}), AGORA) == 0
    assert len(publicados(cfg)) == 1


def test_limites_invalidos_nao_desativam_protecao(cfg):
    preparar(cfg, {"23651": incidente()["23651"]})
    antes = arquivos(cfg)
    cfg["protecao"]["limite_trocas"] = 0
    with pytest.raises(ValueError, match="positivos"):
        executar(cfg, Cliente({"30000": registro_novo()}), AGORA)
    assert arquivos(cfg) == antes
