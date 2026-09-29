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

Mudanças de `guid` e `Autonumber` também podem ocorrer sem mudar o conteúdo da norma. O coletor
concilia esses cadastros pela identidade normativa e pela ementa. Trocas em massa bloqueiam a
publicação para revisão no resumo do Actions; veja [operação](DEPLOYMENT.md#lotes-bloqueados).

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

`pubDate` permanece sendo a data da primeira detecção, exceto em reenvio solicitado. Trocar o
cadastro da ANS não altera essa data nem o GUID RSS. A data do DOU continua na descrição/categoria,
pois usar o DOU no gatilho pode perder atos disponibilizados tardiamente.

Esta correção não altera o fluxo nem remove itens já criados no SharePoint/Teams. A proteção no
destino contra duplicidade é complementar e deve usar a identidade da norma, não apenas o link.
