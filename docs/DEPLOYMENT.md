# Implantação e operação

## Onde roda
- **GitHub Actions**: `.github/workflows/coletar.yml`, às 09:17, 13:17 e 18:17 de Brasília (cron `17 12,16,21 * * *`, em UTC; minuto fora da hora cheia porque nela o GitHub atrasa ou descarta execuções agendadas; mesmo assim podem ocorrer atrasos) e sob demanda (`workflow_dispatch`, com os campos opcionais "reenviar" e "aprovar_lote").
  Para mudar os horários, editar a linha `cron` do workflow.
  Instala, roda os testes, coleta e commita `data/` e `docs/` somente se algo mudou.
- **Testes de PR**: `.github/workflows/testes.yml` valida o código sem coletar dados nem publicar o feed.
- **GitHub Pages**: branch `main`, pasta `/docs` (com `.nojekyll`). Feed em `https://jarbas-martinho.github.io/buscaANS/feed.xml`.
- O repositório é público (exigência do Pages gratuito). Não há segredos: só dados públicos da ANS.

## Permissões do workflow
- `contents: write` para commitar estado e feed.
- `actions: write` para reativar o próprio agendamento a cada execução; o GitHub desativa agendamentos de repositórios públicos após 60 dias sem atividade.

## Variáveis de ambiente (opcionais)
Qualquer chave de `config/defaults.toml` como `BUSCAANS_<SECAO>_<CHAVE>`. Exemplos:

| Variável | Efeito |
|---|---|
| `BUSCAANS_COLETA_QUANTIDADE` | Quantos atos recentes ler por execução (padrão 40) |
| `BUSCAANS_COLETA_TIPOS_EXCLUIDOS` | Tipos excluídos, separados por `;` |
| `BUSCAANS_FEED_ITENS` | Itens no feed (padrão 50) |
| `BUSCAANS_ANS_QUERY_ID_RESERVA` | `queryId` usado se a descoberta falhar |
| `BUSCAANS_PROTECAO_LIMITE_TROCAS` | Bloqueia a partir deste número de normas com IDs novos (padrão 5) |
| `BUSCAANS_PROTECAO_LIMITE_NOVOS` | Bloqueia a partir deste número de atos desconhecidos, incluindo excluídos (padrão 10) |
| `BUSCAANS_PROTECAO_ATRASO_DOU_DIAS` | Janela para DOU de normas desconhecidas elegíveis (padrão 7 dias); DOU ausente exige revisão |
| `BUSCAANS_CONFIG` | Caminho de outro arquivo TOML |

Para usar no Actions, definir em Settings > Secrets and variables > Actions > Variables e repassar no passo "Coletar" (`env:`).

## Trocar a origem no Power Automate
Os atos da semeadura ficam fora do feed. Após a conciliação do incidente de 28/09/2026, o feed
contém apenas a RN 680, que estava pendente no fluxo antigo, com a data preservada de
23/09/2026 17:16:45 -0300. Seu link atual termina em 25522; seu GUID RSS legado termina em 23651.
Novidades posteriores à conciliação podem acrescentar outros itens.

1. Abrir o fluxo de coleta.
2. No gatilho RSS "Quando um item de feed é publicado", trocar a URL do feed
   `https://feeds.feedburner.com/gov/NUXu` por `https://jarbas-martinho.github.io/buscaANS/feed.xml`.
3. Manter "Propriedade de data: PublishDate", a condição e a ação "Criar item". Salvar.
4. Conferir se a RN 680 chegou à lista e ao Teams. Se não chegar (o gatilho pode considerar só itens
   publicados depois da troca), executar Actions > "Coletar legislações da ANS" > Run workflow com
   "reenviar" = `23651` (ou `gh workflow run coletar.yml -f reenviar=23651`). Ela volta ao feed com data
   atual. A entrega depende do cache do Pages e da próxima consulta do gatilho RSS.

Observação: a coluna DataPublicação passa a receber o momento em que o coletor detectou o ato
(até algumas horas depois do cadastro no portal, conforme o próximo horário agendado).
A data do DOU fica no início da descrição.

## Operação
- Execução manual: aba Actions > "Coletar legislações da ANS" > Run workflow, ou `gh workflow run coletar.yml`.
- Falhas: aparecem no Actions; notificações dependem das preferências do GitHub. O feed anterior permanece publicado.
- Publicação do feed: ver [Publicação no GitHub Pages](#publicação-no-github-pages).
- Não apague o estado para resolver uma troca de identificadores: isso perde o histórico de reconhecimento.
- Reenviar um ato: Run workflow com "reenviar" = Autonumber antigo ou atual conhecido. A norma precisa
  estar entre os 40 atos lidos. O histórico de IDs é preservado; o reenvio solicitado muda a data do RSS.

## Publicação no GitHub Pages

O Pages publica `docs/` em um workflow automático do GitHub (`pages-build-deployment`), separado da
coleta. Se ele falhar, o feed no ar fica desatualizado, e o GitHub não avisa ninguém (a execução é
atribuída ao robô do Pages). Por isso a coleta confere a publicação com `python -m buscaans.pages`:

| Passo do workflow | O que faz |
|---|---|
| Conferir publicação anterior | Se a publicação mais recente da `main` falhou ou foi cancelada, pede a reexecução. Não interrompe a coleta |
| Confirmar publicação do feed | Só quando houve push: espera a publicação do commit, reexecuta uma vez se falhar e faz a coleta falhar se ainda assim não publicar |

Parâmetros em `config/defaults.toml`, seção `[pages]`: espera (`espera_minutos`, padrão 20, acima dos
15 minutos após os quais o GitHub cancela uma publicação travada), intervalo de consulta e workflow.

Correção manual, se preciso: Actions > `pages-build-deployment` > execução com falha > "Re-run failed jobs",
ou `gh run rerun <id> --failed`. Se a data do item no feed ficou anterior à última leitura do Power
Automate, use o reenvio (ver Operação) para o gatilho não ignorá-lo.

## Lotes bloqueados

O passo de coleta termina com falha antes de gravar `data/estado.json` ou `docs/feed.xml` quando
atinge um limite de volume/trocas ou encontra norma desconhecida elegível com DOU antigo/ausente.
O passo de commit não executa. O resumo do Actions e os logs mostram os motivos, a lista de atos,
links e o código SHA-256 do lote. O código não é credencial: identifica exatamente os dados revisados.

1. Abra a execução bloqueada e revise o resumo e os links das normas.
2. Se o lote for legítimo, use Run workflow na branch `main`, preenchendo `aprovar_lote` com o código
   completo exibido. Mantenha `reenviar` igual ao da execução revisada, se houver.
3. A nova consulta precisa produzir os mesmos eventos sobre o mesmo estado, limites e motivos.
   Se algum deles mudar, haverá novo bloqueio e outro código para revisar.
4. Não aumente limites apenas para contornar um incidente. A aprovação vale para um lote e não
   desabilita proteções futuras. Um código antigo não é aceito depois que o estado muda.

Conflitos de identidade/ementa ocorrem só quando a norma é reconhecida pelo título, sem número em comum.
Exigem examinar retificações, republicações e possível reutilização de IDs; `aprovar_lote` não os libera.
Versões atualizadas reconhecidas pelo `AutonumberOriginal` não passam por esse bloqueio nem contam como troca.

## Conciliar registros locais

```bash
python -m buscaans --conciliar-estado
git diff -- data/estado.json docs/feed.xml
```

Esse comando não consulta a ANS nem utiliza a data atual. Concilia apenas identidades com ementas
equivalentes, preservando todas as referências, a primeira data e a marca de preexistente. É idempotente.
Revise o diff e publique por PR. A correção do incidente já inclui os arquivos conciliados, portanto
não é necessário reexecutar o comando após integrar o PR.

Antes de integrar o PR, confira se `main` recebeu novas coletas: o estado/feed da branch devem
preservar essas novidades, conciliando de novo se necessário. O PR não altera o Power Automate
e não remove itens já criados no destino.
