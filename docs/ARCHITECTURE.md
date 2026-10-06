# Arquitetura

```
GitHub Actions (cron 09:17, 13:17, 18:17)
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
| `identidade.py` | Identidade da norma, comparação conservadora de ementas e GUID RSS estável |
| `protecao.py` | Limites de publicação, resumo de revisão e aprovação vinculada ao lote |
| `feed.py` | RSS 2.0 com a biblioteca padrão |
| `pages.py` | Confere a publicação do feed no GitHub Pages e reexecuta a que falhar |
| `__main__.py` | Orquestração e registro em log |

## Decisões
- **Feed RSS em vez de gravar direto no SharePoint.** Reaproveita o fluxo existente, usa só conectores padrão do Power Automate e não exige credenciais corporativas fora do tenant.
- **Mesma consulta da página (`retrieve` por `queryId`), não `retrieve_by_xpath`.** A consulta genérica devolve rascunhos e versões antigas (7.849 registros contra 4.693 exibidos).
- **`queryId` descoberto a cada execução.** É um hash que muda quando a ANS publica nova versão do sistema. A página tem cinco grades equivalentes; o coletor tenta cada uma e, por último, a reserva da configuração.
- **Número original da ANS como identidade principal.** A ANS publica versões atualizadas de um ato
  (`Versao = Atualizada`), cada uma com `Autonumber` e guid novos; o campo `AutonumberOriginal` aponta
  para o ato original, e `/link/legislacao/{original}` redireciona para a versão vigente. O coletor
  reconhece o ato por guid, número da versão, número original e, só por último, pela identidade do
  título. Versão confirmada por número atualiza título, ementa, DOU, situação e link, sem republicar e
  sem revisão manual; título padronizado ou ementa alterada numa versão não bloqueiam a coleta.
- **Identidade pelo título como último recurso.** Usada apenas quando nenhum número bate. A chave `identidade` usa o prefixo normalizado do título
  (tipo e órgão), número, data completa do ato e data do DOU. A normalização tolera caixa, acentos,
  espaços, pontuação e o `de` nas datas. Títulos fora do formato reconhecido usam o título completo
  normalizado + DOU, sem tentar adivinhar tipo ou órgão. Retificações no título e outro DOU geram
  identidades distintas; ementa divergente para a mesma identidade (sem número em comum) bloqueia a coleta para revisão.
  O parser não tenta equiparar abreviações diferentes de órgãos ou tipos.
- **Referências preservadas.** A chave numérica de `itens` continua sendo o primeiro `Autonumber`
  conhecido, por compatibilidade operacional. `identificadores` reúne todos os números/guids
  reconciliados. Um cadastro novo equivalente atualiza o link, mantendo `visto_em`, `pre_existente`
  e `rss_guid`. IDs antigos já conhecidos não fazem o link regredir. Novos atos recebem GUID RSS
  derivado da identidade; atos legados mantêm o GUID já publicado.
- **`pubDate` = momento da detecção.** O gatilho RSS do Power Automate só entrega itens com data posterior à última verificação; a ANS registra atos com `DataDOU` à meia-noite e às vezes com dias de atraso, então usar a data do DOU faria perder itens. A data do DOU vai na descrição e em `<category>`.
- **Semeadura sem feed.** Na primeira execução (sem `estado.json`) todos os atos lidos são marcados `pre_existente` e ficam fora do feed. Assim o feed só contém atos detectados depois da implantação, e o Power Automate não tem o que recriar, qualquer que seja o comportamento do gatilho na primeira leitura.
- **Reenvio controlado.** `--reenviar` aceita qualquer Autonumber reconciliado. Se a norma estiver na
  leitura, atualiza `visto_em` e libera `pre_existente`, preservando os aliases e o GUID RSS. Não remove
  o histórico. Só o reenvio explicitamente solicitado dispensa a revisão por DOU antigo.
- **Proteção antes de gravar.** Mudanças são preparadas em memória. A partir de 5 normas reconhecidas só pelo título com novos IDs,
  10 atos desconhecidos (incluindo excluídos), ou uma norma desconhecida elegível com DOU ausente ou
  anterior à janela de 7 dias, a execução falha e preserva os arquivos anteriores. A semeadura inicial
  não publica nada, por isso não exige aprovação de volume. Conflitos de identidade continuam bloqueados.
- **Aprovação específica.** O código SHA-256 vincula estado anterior, eventos candidatos (incluindo
  conteúdo e IDs), limites e motivos. Não inclui a hora de execução. Mudanças nesses dados invalidam
  a aprovação; não há desativação persistente da proteção. Conflitos de conteúdo não são liberados por código.
- **Frequência de três execuções diárias.** A ANS publica poucos atos por semana; mais frequência não traz ganho e aumenta a carga no portal.
- **Leitura dos N mais recentes, sem paginação por deslocamento**, porque inserções deslocam as páginas.
- **Publicação conferida pela coleta.** O Pages publica em workflow próprio, que pode falhar sem aviso
  (05/10/2026: travou e foi cancelado). A coleta espera a publicação do commit, reexecuta uma vez e falha
  visivelmente se não publicar; no início de cada coleta, corrige falha anterior. Reexecutar a mesma
  publicação usa a permissão `actions: write` já existente, sem exigir `pages: write`.
- **Arquivos só são regravados quando o conteúdo muda** (`lastBuildDate` = última novidade), evitando commits vazios.
