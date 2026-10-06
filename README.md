# buscaANS

Coletor das novas legislações publicadas pela ANS. Consulta a busca de legislações do portal
([componentes-portal.ans.gov.br/link/legislacoes](https://componentes-portal.ans.gov.br/link/legislacoes)),
aplica o filtro de tipos de ato e publica um **feed RSS** que alimenta o fluxo do Power Automate
(gravação em lista do SharePoint e aviso no Teams).

**Feed:** https://jarbas-martinho.github.io/buscaANS/feed.xml

## Por que existe
O fluxo antigo usava o RSS `feeds.feedburner.com/gov/NUXu`. A ANS migrou a busca para uma aplicação
Mendix sem RSS e o fluxo parou. Este projeto recria o feed a partir do novo portal; no Power Automate
basta trocar a URL do gatilho RSS (passo a passo em [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).

## Como funciona
1. Três vezes ao dia (09:17, 13:17 e 18:17 de Brasília) o GitHub Actions executa `python -m buscaans`.
2. O coletor abre uma sessão anônima no portal, lê os 40 atos mais recentes pela data do DOU e
   reconhece cada norma pelo número original da ANS (`AutonumberOriginal`), que se mantém quando a
   ANS publica versões atualizadas; o título (tipo/órgão, número, datas) é usado só como último recurso.
3. Atos dos tipos excluídos (Resolução Operacional, Resolução Regimental, Despacho, Portaria,
   Resoluções Administrativas) ficam registrados, mas fora do feed.
4. Versões atualizadas não viram novidade: preservam a data de detecção e o GUID do RSS, e o link usa o
   número original, que o portal redireciona para a versão vigente. Lotes suspeitos param para revisão
   no Actions antes de qualquer gravação; lotes aprovados atualizam `docs/feed.xml` no GitHub Pages.
5. A coleta confere se o GitHub Pages publicou o feed e reexecuta a publicação que falhar.

## Uso local
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m buscaans
```

## Configuração
Tudo em [config/defaults.toml](config/defaults.toml): tipos excluídos, quantidade lida, tamanho do feed,
endereços do portal. Qualquer chave pode ser sobrescrita por variável `BUSCAANS_<SECAO>_<CHAVE>`
(listas separadas por `;`), por exemplo `BUSCAANS_COLETA_TIPOS_EXCLUIDOS="Portaria;Despacho"`.

Proteções padrão: revisão a partir de 5 normas com novos identificadores, 10 atos desconhecidos no
mesmo lote, ou qualquer norma desconhecida elegível com DOU de mais de 7 dias atrás ou ausente.
Veja como revisar e liberar um lote em [Implantação e operação](docs/DEPLOYMENT.md#lotes-bloqueados).

## Documentação
- [Arquitetura](docs/ARCHITECTURE.md)
- [Integrações (portal da ANS e Power Automate)](docs/INTEGRATIONS.md)
- [Implantação e operação](docs/DEPLOYMENT.md)
- [Dicionário de dados](docs/DATA_DICTIONARY.md)
- [Histórico de versões](docs/CHANGELOG.md)
- [Incidente de 28/09/2026 e conciliação](docs/INCIDENTE_2026-09-28.md)

## Licença
[MIT](LICENSE). Código fornecido sem garantia; os dados coletados são públicos e pertencem à ANS.
