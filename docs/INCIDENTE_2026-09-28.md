# Incidente de 28/09/2026: normas antigas no RSS

## Evidência e causa

A [coleta #19](https://github.com/jarbas-martinho/buscaANS/actions/runs/36474030313) leu 40 atos,
sem novidades. A [coleta #20](https://github.com/jarbas-martinho/buscaANS/actions/runs/36505864422),
agendada e sem reenvio, leu 40 atos e adicionou 30 cadastros ao estado. O horário 29/09/2026 01:01 UTC
corresponde a 28/09/2026 22:01 em Brasília.

No [commit a75ec34](https://github.com/jarbas-martinho/buscaANS/commit/a75ec34aaa062add772c8b918a976633fd44a7a6),
29 dos 30 cadastros tinham os mesmos título, ementa, DOU e situação de registros anteriores,
mas outros GUIDs e Autonumbers. A causa interna dessa mudança no portal não foi confirmada.
O coletor dependia dos IDs do cadastro para reconhecer a norma, cadastrou novamente os atos e
usou a hora da coleta no `pubDate`. Cinco passaram pelo filtro e chegaram ao feed:

| Norma | DOU | ID anterior | ID recebido |
|---|---|---|---|
| RN 680 | 22/09/2026 | 23651 | 25522 |
| RN 679 | 14/09/2026 | 21753 | 25468 |
| IN DIPRO 61 | 22/07/2026 | 11892 | 25460 |
| RN 675 | 11/06/2026 | 12043 | 25626 |
| RN 674 | 11/06/2026 | 12554 | 25465 |

## Conciliação incluída na correção

- Estado v2 com 41 normas distintas e as 70 referências de cadastro preservadas (29 duplicados conciliados).
- O cadastro 25660, RO 3143, não tinha equivalente no estado anterior: foi preservado e continua excluído pelo tipo.
- RN 679, IN DIPRO 61, RN 675 e RN 674 mantêm a marca de preexistentes e ficam fora do feed.
- RN 680 permanece uma vez, com `pubDate` de 23/09/2026 17:16:45 -0300, link atual `/25522`
  e GUID RSS legado `/23651`. Nenhuma data atual foi atribuída pela conciliação.
- A correção não remove itens já criados no Power Automate, SharePoint ou Teams.

## Validação reproduzível

`tests/fixtures/incidente_2026_09_28.json` é a cópia integral de `data/estado.json` do commit a75ec34.
Os testes separam os 40 registros anteriores e os 30 cadastros adicionados pelo horário persistido.
O replay reconstrói os campos consumidos pelo cliente a partir desses registros; não pretende
reproduzir a resposta HTTP integral dos 40 atos da ANS, que não foi arquivada na execução.

Os testes verificam bloqueio sem gravação, aprovação do mesmo lote, rejeição de aprovação para
lote diferente, preservação de aliases/datas/preexistentes e idempotência da conciliação.
Todos executam sem acessar a ANS. Para executar: `python -m pytest -q`.
