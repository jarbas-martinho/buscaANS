import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pytest

from buscaans import config, feed
from buscaans.__main__ import executar
from buscaans.ans_client import ClienteANS, ErroANS, _achatar, descobrir_query_ids
from buscaans.estado import Estado
from buscaans.filtro import excluido
from buscaans.normalizar import data_dou, status_legivel, texto_sem_html

FX = Path(__file__).parent / "fixtures"
TIPOS = config.carregar()["coleta"]["tipos_excluidos"]


def lista_real() -> list[dict]:
    dados = json.loads((FX / "retrieve_lista.json").read_text(encoding="utf-8"))
    return [_achatar(o) for o in dados["partialObjects"]]


class ClienteFalso:
    """Substitui o ClienteANS usando a resposta real salva; Autonumber derivado do guid."""

    def __init__(self, atos):
        self.atos = atos
        self.query_id = "fixo"
        self.candidatos = ["fixo"]
        self.chamadas_autonumber = 0

    def abrir(self):
        pass

    def listar(self, quantidade):
        return self.atos[:quantidade]

    def autonumber(self, guid):
        self.chamadas_autonumber += 1
        return str(int(guid[-6:]))

    def link(self, num):
        return f"https://componentes-portal.ans.gov.br/link/legislacao/{num}"

    def fechar(self):
        pass


@pytest.fixture
def cfg(tmp_path):
    c = config.carregar()
    c["estado"]["arquivo"] = str(tmp_path / "estado.json")
    c["feed"]["arquivo"] = str(tmp_path / "feed.xml")
    return c


def itens_feed(cfg):
    raiz = ET.parse(cfg["feed"]["arquivo"]).getroot()
    return raiz.findall("./channel/item")


def test_descobre_query_ids_da_lista_e_ignora_outras_entidades():
    xml = (FX / "pagina_trecho.xml").read_text(encoding="utf-8")
    assert descobrir_query_ids(xml, "Legislacao.Legislacao") == ["2aUSBIBKzEKmUAR+PH54AA", "vu3fmVivr0ucW2dUZkmT4g"]
    assert descobrir_query_ids("<page/>", "Legislacao.Legislacao") == []


def test_listar_tenta_proximo_candidato_quando_um_falha():
    c = ClienteANS(config.carregar()["ans"])
    c.candidatos = ["ruim", "bom"]
    c._listar = lambda qid, n: (_ for _ in ()).throw(ErroANS("x")) if qid == "ruim" else [{"guid": "1"}]
    assert c.listar(5) == [{"guid": "1"}]
    assert c.query_id == "bom"


def test_normalizacao():
    assert texto_sem_html('<p><span style="x">Dispõe &amp; altera</span>.</p>') == "Dispõe & altera ."
    d = data_dou(1790132400000, "America/Sao_Paulo")
    assert (d.year, d.month, d.day, d.hour) == (2026, 9, 23, 0)
    assert status_legivel("NaoVigente") == "Não vigente"
    assert status_legivel("Vigente") == "Vigente"


@pytest.mark.parametrize("titulo,esperado", [
    ("Resolução Operacional - RO ANS nº 3173, de 21 setembro 2026", True),
    ("Portaria - Portaria PRESI nº 9, de 16 julho 2026", True),
    ("Despacho - Despacho DIOPE nº 1", True),
    ("Resolução Normativa - RN ANS nº 680, de 18 setembro 2026", False),
    ("Instrução Normativa - IN ANS nº 38, de 21 julho 2026", False),
])
def test_filtro_por_tipo(titulo, esperado):
    assert excluido(titulo, TIPOS) is esperado


def test_primeira_execucao_semeia_com_data_do_dou(cfg):
    cli = ClienteFalso(lista_real())
    agora = datetime(2026, 9, 23, 18, 0, tzinfo=timezone.utc)
    novos = executar(cfg, cliente=cli, agora=agora)
    assert novos == len(lista_real())
    itens = itens_feed(cfg)
    titulos = [i.findtext("title") for i in itens]
    assert any(t.startswith("Resolução Normativa - RN ANS nº 680") for t in titulos)
    assert not any(t.startswith("Resolução Operacional") for t in titulos)
    # semeadura: pubDate = data do DOU (meia-noite), nunca o momento da execução
    assert all("00:00:00 -0300" in i.findtext("pubDate") for i in itens)
    rn680 = next(i for i in itens if "RN ANS nº 680" in i.findtext("title"))
    assert rn680.findtext("description").startswith("Publicado no DOU em 22/09/2026. Altera o Anexo I")
    assert rn680.findtext("link") == rn680.findtext("guid")


def test_segunda_execucao_sem_novidade_nao_altera_arquivos(cfg):
    atos = lista_real()
    executar(cfg, cliente=ClienteFalso(atos))
    antes = (Path(cfg["estado"]["arquivo"]).read_text(encoding="utf-8"),
             Path(cfg["feed"]["arquivo"]).read_text(encoding="utf-8"))
    cli = ClienteFalso(atos)
    assert executar(cfg, cliente=cli, agora=datetime(2026, 9, 24, tzinfo=timezone.utc)) == 0
    assert cli.chamadas_autonumber == 0
    depois = (Path(cfg["estado"]["arquivo"]).read_text(encoding="utf-8"),
              Path(cfg["feed"]["arquivo"]).read_text(encoding="utf-8"))
    assert antes == depois


def test_ato_novo_recebe_pubdate_da_deteccao_e_vai_ao_topo(cfg):
    atos = lista_real()
    rn = next(a for a in atos if a["Titulo"].startswith("Resolução Normativa"))
    executar(cfg, cliente=ClienteFalso([a for a in atos if a is not rn]))
    agora = datetime(2026, 9, 23, 17, 30, tzinfo=timezone.utc)
    assert executar(cfg, cliente=ClienteFalso(atos), agora=agora) == 1
    primeiro = itens_feed(cfg)[0]
    assert "RN ANS nº 680" in primeiro.findtext("title")
    assert primeiro.findtext("pubDate") == "Wed, 23 Sep 2026 14:30:00 -0300"


def test_estado_poda_os_mais_antigos():
    e = Estado({str(i): {"guid": str(i), "dou": f"2026-01-{i:02d}", "visto_em": "x"} for i in range(1, 11)})
    e.podar(3)
    assert sorted(e.itens, key=int) == ["8", "9", "10"]


def test_feed_vazio_valido():
    texto = feed.montar([], config.carregar()["feed"])
    assert ET.fromstring(texto.split("\n", 1)[1]).find("channel/title").text == "ANS: novas legislações"
