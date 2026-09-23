# Dicionário de dados

## `data/estado.json`
```json
{"versao": 1, "itens": {"<Autonumber>": { ... }}}
```

| Campo | Tipo | Descrição |
|---|---|---|
| chave | texto numérico | `Autonumber` do ato no portal da ANS; identifica o ato e forma o link |
| `guid` | texto | Identificador interno do objeto Mendix (evita consultar o `Autonumber` de novo) |
| `titulo` | texto | Título do ato, ex. "Resolução Normativa - RN ANS nº 680, de 18 setembro 2026" |
| `ementa` | texto | Ementa sem HTML |
| `dou` | data ISO (`AAAA-MM-DD`) ou nulo | Data de publicação no DOU, fuso de São Paulo |
| `status` | texto | Situação exibida no portal ("Vigente", "Não vigente", ...) |
| `link` | URL | `https://componentes-portal.ans.gov.br/link/legislacao/{Autonumber}` |
| `visto_em` | data e hora ISO com fuso | Momento da detecção (na semeadura, meia-noite da data do DOU); vira o `pubDate` do feed |
| `excluido` | booleano | `true` se o tipo do ato está em `coleta.tipos_excluidos` (fica fora do feed) |

Poda: mantém no máximo `estado.maximo` registros (padrão 2000), descartando os de DOU mais antigo.

## `docs/feed.xml` (RSS 2.0)
| Elemento | Conteúdo |
|---|---|
| `item/title` | `titulo` |
| `item/link`, `item/guid` | `link` |
| `item/description` | "Publicado no DOU em dd/mm/aaaa. " + `ementa` |
| `item/pubDate` | `visto_em` (RFC 822) |
| `item/category` | "DOU dd/mm/aaaa" e `status` |
| `channel/lastBuildDate` | maior `visto_em` entre os itens |
