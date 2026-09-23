# Arquitetura

```
GitHub Actions (cron 30 min)
  └─ python -m buscaans
       ├─ ans_client  ── HTTP ──> componentes-portal.ans.gov.br (/index.html, page.xml, /xas/)
       ├─ normalizar / filtro
       ├─ estado  ──> data/estado.json   (commit no repositório)
       └─ feed    ──> docs/feed.xml      (GitHub Pages)
                                  │
Power Automate: gatilho RSS ──────┘──> Criar item em lista SharePoint ──> fluxo de aviso no Teams
```

## Módulos (`src/buscaans`)
| Módulo | Responsabilidade |
|---|---|
| `config.py` | Lê `config/defaults.toml` e aplica variáveis `BUSCAANS_*` |
| `ans_client.py` | Sessão anônima Mendix, descoberta do `queryId`, listagem, `Autonumber`, logout |
| `normalizar.py` | Ementa sem HTML, `DataDOU` no fuso de São Paulo, status legível |
| `filtro.py` | Exclusão pelo início do título |
| `estado.py` | Leitura, poda e gravação idempotente do estado |
| `feed.py` | RSS 2.0 com a biblioteca padrão |
| `__main__.py` | Orquestração e registro em log |

## Decisões
- **Feed RSS em vez de gravar direto no SharePoint.** Reaproveita o fluxo existente, usa só conectores padrão do Power Automate e não exige credenciais corporativas fora do tenant.
- **Mesma consulta da página (`retrieve` por `queryId`), não `retrieve_by_xpath`.** A consulta genérica devolve rascunhos e versões antigas (7.849 registros contra 4.693 exibidos).
- **`queryId` descoberto a cada execução.** É um hash que muda quando a ANS publica nova versão do sistema. A página tem cinco grades equivalentes; o coletor tenta cada uma e, por último, a reserva da configuração.
- **Chave do ato = `Autonumber`**, que também forma o link público `/link/legislacao/{Autonumber}`. O atributo `Url` do objeto aponta para domínio interno e não é usado.
- **`pubDate` = momento da detecção.** O gatilho RSS do Power Automate só entrega itens com data posterior à última verificação; a ANS registra atos com `DataDOU` à meia-noite e às vezes com dias de atraso, então usar a data do DOU faria perder itens. A data do DOU vai na descrição e em `<category>`.
- **Semeadura.** Na primeira execução (sem `estado.json`) os atos recebem `pubDate` = data do DOU, para não gerar avisos em massa.
- **Leitura dos N mais recentes, sem paginação por deslocamento**, porque inserções deslocam as páginas.
- **Arquivos só são regravados quando o conteúdo muda** (`lastBuildDate` = última novidade), evitando commits vazios.
