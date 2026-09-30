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
from buscaans.ans_client import ErroANS
from buscaans.estado import Estado
from buscaans.identidade import IdentidadeConflitante, chave
from buscaans.protecao import LoteSuspeito

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime(2026, 9, 28, 22, 1, 14, tzinfo=FUSO)
INCIDENTE = Path(__file__).parent / "fixtures" / "incidente_2026_09_28.json"
# AutonumberOriginal real de cada um dos 70 registros do incidente, consultado no portal em 29/09.
ORIGINAIS = Path(__file__).parent / "fixtures" / "originais_2026_09_29.json"


@pytest.fixture
def cfg(tmp_path):
    c = config.carregar(ambiente={})
    c["estado"]["arquivo"] = str(tmp_path / "estado.json")
    c["feed"]["arquivo"] = str(tmp_path / "feed.xml")
    return c


def incidente():
    return json.loads(INCIDENTE.read_text(encoding="utf-8"))["itens"]


def originais():
    return {n: o for n, o in json.loads(ORIGINAIS.read_text(encoding="utf-8"))["originais"].items() if o != "0"}


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

    def __init__(self, itens, originais=None):
        # Sem "originais", simula registros sem AutonumberOriginal: só resta a identidade pelo título.
        self.itens = itens
        self.originais = originais or {}
        self.encerrado = False
        self.consultas = 0

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

    def numeros(self, guid):
        # Como o portal, responde por qualquer registro conhecido, inclusive os que saíram da lista.
        for num, item in {**incidente(), **self.itens}.items():
            if item["guid"] == guid:
                self.consultas += 1
                return num, self.originais.get(num)
        raise ErroANS(f"Objeto {guid} não encontrado")

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
    publicados_antes = [(i.findtext("guid"), i.findtext("pubDate")) for i in publicados(cfg)]
    # O portal pode alternar entre cadastros antigos/novos sem gerar outra publicação. Na primeira
    # alternância o registro antigo revela a raiz (sem AutonumberOriginal) e o link passa a usá-la.
    alternado = Cliente({antigo: origem[antigo], novo: origem[novo]})
    assert executar(cfg, alternado, AGORA) == 0
    assert [(i.findtext("guid"), i.findtext("pubDate")) for i in publicados(cfg)] == publicados_antes
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert e.itens[antigo]["original"] == antigo and e.itens[antigo]["link"].endswith("/" + antigo)
    antes = arquivos(cfg)
    assert executar(cfg, alternado, AGORA) == 0
    assert arquivos(cfg) == antes


def test_mesmo_numero_com_outro_guid_nao_republica(cfg):
    item = incidente()["23651"]
    preparar(cfg, {"23651": item})
    assert executar(cfg, Cliente({"23651": dict(item, guid="outro-guid")}), AGORA) == 0
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert e.itens["23651"]["identificadores"]["23651"] == sorted([item["guid"], "outro-guid"])


def test_ementa_divergente_sem_numero_original_exige_revisao_sem_gravar(cfg):
    origem = incidente()
    preparar(cfg, {"23651": origem["23651"]})
    antes = arquivos(cfg)
    item = dict(origem["25522"], ementa="Texto retificado, materialmente diferente")
    with pytest.raises(IdentidadeConflitante):
        executar(cfg, Cliente({"25522": item}), AGORA, aprovar_lote="qualquer-codigo")
    assert arquivos(cfg) == antes


@pytest.mark.parametrize("num", ["23651", "25522"])
def test_versao_com_ementa_alterada_atualiza_sem_republicar(cfg, num):
    # Mesmo registro (23651) ou nova versão confirmada pelo AutonumberOriginal (25522 -> 23651).
    origem = incidente()
    preparar(cfg, {"23651": origem["23651"]})
    item = dict(origem[num], ementa="Texto retificado pela ANS")
    assert executar(cfg, Cliente({num: item}, originais()), AGORA) == 0
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert e.itens["23651"]["ementa"] == "Texto retificado pela ANS"
    assert e.itens["23651"]["visto_em"] == origem["23651"]["visto_em"]
    rss = publicados(cfg)
    assert len(rss) == 1 and rss[0].findtext("pubDate") == "Wed, 23 Sep 2026 17:16:45 -0300"


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


def test_versao_com_titulo_padronizado_e_a_mesma_norma(cfg):
    # Na lista coexistem "RO ANS nº" e "RO Diretoria Colegiada nº"; o número original decide.
    origem = incidente()
    preparar(cfg, {"15697": origem["15697"]})
    item = dict(origem["25667"], titulo=origem["25667"]["titulo"].replace("Diretoria Colegiada", "ANS"))
    assert chave(item) != chave(origem["15697"])
    assert executar(cfg, Cliente({"25667": item}, originais()), AGORA) == 0
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert len(e.itens) == 1 and e.itens["15697"]["titulo"] == item["titulo"]


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


def test_replay_do_lote_real_com_numeros_originais_nao_bloqueia_nem_republica(cfg):
    # Causa confirmada: as 29 "trocas" de 28/09 eram versões atualizadas (AutonumberOriginal = número antigo).
    origem = incidente()
    anteriores = {n: i for n, i in origem.items() if i["visto_em"] != AGORA.isoformat()}
    recebidos = {n: i for n, i in origem.items() if i["visto_em"] == AGORA.isoformat()}
    preparar(cfg, anteriores)
    # Só a RO 3143 (25660), nunca vista antes, é nova; fica fora do feed pelo tipo.
    assert executar(cfg, Cliente(recebidos, originais()), AGORA) == 1
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    assert len(e.itens) == 41
    rn680 = e.itens["23651"]
    assert set(rn680["identificadores"]) == {"23651", "25522"}
    assert rn680["original"] == "23651" and rn680["link"].endswith("/23651")
    assert e.itens["25660"]["original"] == "11961" and e.itens["25660"]["excluido"]
    rss = publicados(cfg)
    assert len(rss) == 1
    assert rss[0].findtext("pubDate") == "Wed, 23 Sep 2026 17:16:45 -0300"
    assert rss[0].findtext("guid").endswith("/23651") and rss[0].findtext("link").endswith("/23651")
    antes = arquivos(cfg)
    cliente = Cliente(recebidos, originais())
    assert executar(cfg, cliente, AGORA + timedelta(days=1)) == 0
    assert arquivos(cfg) == antes
    assert cliente.consultas == 0  # números originais já registrados: nenhuma consulta extra


def test_nova_versao_casa_pelo_original_que_so_o_portal_conhecia(cfg):
    # RN 678: já era versão atualizada (13030) em 23/09; o original 11856 nunca apareceu na lista.
    origem = incidente()
    preparar(cfg, {"13030": origem["13030"]})
    versao = dict(origem["13030"], guid="versao-3-rn678",
                  titulo=origem["13030"]["titulo"].replace("21 julho", "21 de julho de"))
    mapa = {"13030": "11856", "30001": "11856"}
    cliente = Cliente({"30001": versao}, mapa)
    assert executar(cfg, cliente, AGORA) == 0
    assert cliente.consultas == 2  # preenchimento do original + a versão nova
    e = Estado.ler(Path(cfg["estado"]["arquivo"]))
    item = e.itens["13030"]
    assert set(item["identificadores"]) == {"13030", "30001"}
    assert item["original"] == "11856" and item["link"].endswith("/11856")
    assert item["visto_em"] == origem["13030"]["visto_em"]


@pytest.mark.parametrize("original,link", [(None, "/30000"), ("29990", "/29990")])
def test_norma_nova_usa_o_numero_original_no_link(cfg, original, link):
    preparar(cfg, {"23651": incidente()["23651"]})
    mapa = {"30000": original} if original else {}
    assert executar(cfg, Cliente({"30000": registro_novo()}, mapa), AGORA) == 1
    item = Estado.ler(Path(cfg["estado"]["arquivo"])).itens["30000"]
    assert item["original"] == link[1:]
    assert publicados(cfg)[0].findtext("link").endswith(link)
    # Reenvio aceita também o número original.
    assert executar(cfg, Cliente({"30000": registro_novo()}, mapa), AGORA + timedelta(days=1), [link[1:]]) == 1
