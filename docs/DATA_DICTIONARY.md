# Dicionário de dados

## `data/estado.json`
```json
{"versao": 2, "itens": {"<Autonumber canônico>": { ... }}}
```

| Campo | Tipo | Descrição |
|---|---|---|
| chave | texto numérico | Primeiro `Autonumber` conhecido da norma; pode diferir do link atual |
| `identidade` | texto JSON | Versão da chave, tipo/órgão, número, data do ato e DOU; fallback pelo título normalizado completo + DOU |
| `identificadores` | objeto | Cada Autonumber conhecido aponta para a lista de guids Mendix associados à mesma norma |
| `rss_guid` | texto | Identificador imutável no RSS: link legado ou `urn:buscaans:ato:<SHA-256 da identidade>` para novos atos |
| `original` | texto numérico | `AutonumberOriginal` da ANS (ou o próprio `Autonumber`, se o ato nunca teve versão atualizada); também reconhece a norma e forma o link |
| `guid` | texto | Identificador do cadastro atual; os anteriores ficam em `identificadores` |
| `titulo` | texto | Título do ato, ex. "Resolução Normativa - RN ANS nº 680, de 18 setembro 2026" |
| `ementa` | texto | Ementa sem HTML |
| `dou` | data ISO (`AAAA-MM-DD`) ou nulo | Data de publicação no DOU, fuso de São Paulo |
| `status` | texto | Situação exibida no portal ("Vigente", "Não vigente", ...) |
| `link` | URL | `/link/legislacao/{original}`, que o portal redireciona para a versão vigente; sem `original`, o número da versão mais recente |
| `visto_em` | data e hora ISO com fuso | Momento da detecção; vira o `pubDate` do feed |
| `excluido` | booleano | `true` se o tipo do ato está em `coleta.tipos_excluidos` (fica fora do feed) |
| `pre_existente` | booleano | `true` se o ato já existia na implantação (semeadura); fica fora do feed para não ser recriado no SharePoint |

Poda: mantém no máximo `estado.maximo` registros (padrão 2000), descartando os de DOU mais antigo.
Cada registro representa uma norma, com todos os seus identificadores. A proteção por DOU antigo
impede publicação automática de normas antigas esquecidas por essa poda.

Migração de v1: agrupa identidades com ementas equivalentes, preserva a data e a marca de preexistente
do primeiro registro e o GUID RSS original, conserva todos os identificadores e usa o link do último
cadastro detectado. Ementas conflitantes não são fundidas. A migração é idempotente.

## `docs/feed.xml` (RSS 2.0)
| Elemento | Conteúdo |
|---|---|
| `item/title` | `titulo` |
| `item/link` | `link` atual |
| `item/guid` | `rss_guid`, com `isPermaLink="false"` para URNs; preserva GUIDs legados |
| `item/description` | "Publicado no DOU em dd/mm/aaaa. " + `ementa` |
| `item/pubDate` | `visto_em` (RFC 822) |
| `item/category` | "DOU dd/mm/aaaa" e `status` |
| `channel/lastBuildDate` | maior `visto_em` entre os itens |
