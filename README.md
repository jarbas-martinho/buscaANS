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
1. Três vezes ao dia (09h, 13h e 18h de Brasília) o GitHub Actions executa `python -m buscaans`.
2. O coletor abre uma sessão anônima no portal, lê os 40 atos mais recentes pela data do DOU e
   identifica os que ainda não estão em `data/estado.json`.
3. Atos dos tipos excluídos (Resolução Operacional, Resolução Regimental, Despacho, Portaria,
   Resoluções Administrativas) ficam registrados, mas fora do feed.
4. `docs/feed.xml` é regravado e publicado pelo GitHub Pages.

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

## Documentação
- [Arquitetura](docs/ARCHITECTURE.md)
- [Integrações (portal da ANS e Power Automate)](docs/INTEGRATIONS.md)
- [Implantação e operação](docs/DEPLOYMENT.md)
- [Dicionário de dados](docs/DATA_DICTIONARY.md)
- [Histórico de versões](docs/CHANGELOG.md)
