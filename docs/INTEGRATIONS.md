# Integrações

## Portal de legislações da ANS (entrada)
Aplicação Mendix em `https://componentes-portal.ans.gov.br`, acesso anônimo, sem API documentada.
As chamadas abaixo foram obtidas observando o navegador e podem mudar sem aviso.

| Passo | Requisição | Uso |
|---|---|---|
| 1 | `GET /index.html` | Cookies iniciais |
| 2 | `POST /xas/` `{"action":"get_session_data",...}` | Cookie `__Host-XASSESSIONID` e `csrftoken` |
| 3 | `GET /pages/pt_BR/Legislacao/Legislacao_Overview_Gov.page.xml` | Descobrir `queryId` da lista (entidade `Legislacao.Legislacao`, ordem `DataDOU desc`, argumento `RevogadasIncluir`) |
| 4 | `POST /xas/` `{"action":"retrieve","params":{"queryId":...,"options":{"amount":40,"sort":[["DataDOU","desc"]]}}}` com header `X-Csrf-Token` | Lista: `Titulo`, `Ementa` (HTML), `DataDOU` (epoch ms), `Status` |
| 5 | `POST /xas/` `{"action":"retrieve_by_ids","params":{"ids":[guid],"schema":{}}}` | `Autonumber` de cada ato novo |
| 6 | `POST /xas/` `{"action":"logout"}` | Encerrar a sessão |

Link público do ato: `https://componentes-portal.ans.gov.br/link/legislacao/{Autonumber}`.

**Sinais de quebra:** workflow falhando com "Nenhum queryId funcionou" ou "Lista de legislações veio vazia".
Refazer a observação no navegador (DevTools, aba Rede, filtrar `xas`) e ajustar `ans_client.py` ou `config/defaults.toml`.

## Power Automate (saída)
O fluxo existente consome `https://jarbas-martinho.github.io/buscaANS/feed.xml` com o gatilho
"Quando um item de feed é publicado" (`shared_rss`, `OnNewFeed`, `sinceProperty: PublishDate`).

| Campo do gatilho | Origem no feed | Coluna SharePoint |
|---|---|---|
| `title` | título do ato | Title |
| `summary` | "Publicado no DOU em dd/mm/aaaa. " + ementa | Descrição |
| `publishDate` | momento em que o coletor detectou o ato | DataPublicação |
| `primaryLink` | link público do ato | link |

A condição de exclusão do fluxo pode permanecer: os títulos novos continuam começando pelo tipo do ato
("Resolução Operacional - ..."), então o filtro duplicado é inofensivo.
