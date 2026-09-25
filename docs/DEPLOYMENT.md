# Implantação e operação

## Onde roda
- **GitHub Actions**: `.github/workflows/coletar.yml`, às 09:17, 13:17 e 18:17 de Brasília (cron `17 12,16,21 * * *`, em UTC; minuto fora da hora cheia porque nela o GitHub atrasa ou descarta execuções agendadas; mesmo assim podem ocorrer atrasos) e sob demanda (`workflow_dispatch`, com o campo opcional "reenviar").
  Para mudar os horários, editar a linha `cron` do workflow.
  Instala, roda os testes, coleta e commita `data/` e `docs/` somente se algo mudou.
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
| `BUSCAANS_CONFIG` | Caminho de outro arquivo TOML |

Para usar no Actions, definir em Settings > Secrets and variables > Actions > Variables e repassar no passo "Coletar" (`env:`).

## Trocar a origem no Power Automate
Os 40 atos já existentes na implantação estão marcados como pré-existentes e fora do feed, então o
Power Automate não tem nada para recriar. O feed contém apenas a RN 680 (Autonumber 23651), que estava
pendente no fluxo antigo, com data de 23/09/2026 16:53.

1. Abrir o fluxo de coleta.
2. No gatilho RSS "Quando um item de feed é publicado", trocar a URL do feed
   `https://feeds.feedburner.com/gov/NUXu` por `https://jarbas-martinho.github.io/buscaANS/feed.xml`.
3. Manter "Propriedade de data: PublishDate", a condição e a ação "Criar item". Salvar.
4. Conferir se a RN 680 chegou à lista e ao Teams. Se não chegar (o gatilho pode considerar só itens
   publicados depois da troca), executar Actions > "Coletar legislações da ANS" > Run workflow com
   "reenviar" = `23651` (ou `gh workflow run coletar.yml -f reenviar=23651`). Ela volta ao feed com data
   atual e é entregue em até ~10 minutos (cache do Pages).

Observação: a coluna DataPublicação passa a receber o momento em que o coletor detectou o ato
(até algumas horas depois do cadastro no portal, conforme o próximo horário agendado).
A data do DOU fica no início da descrição.

## Operação
- Execução manual: aba Actions > "Coletar legislações da ANS" > Run workflow, ou `gh workflow run coletar.yml`.
- Falhas: o GitHub envia e-mail ao dono do repositório quando o workflow falha. O feed anterior permanece publicado.
- Reprocessar do zero: apagar `data/estado.json` e `docs/feed.xml` e executar; ocorre nova semeadura com feed vazio, sem disparar avisos.
- Reenviar um ato: Run workflow com "reenviar" = Autonumber (o número final do link `/link/legislacao/{n}`). O ato precisa estar entre os 40 mais recentes do portal.
