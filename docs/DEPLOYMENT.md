# Implantação e operação

## Onde roda
- **GitHub Actions**: `.github/workflows/coletar.yml`, a cada 30 minutos (UTC) e sob demanda (`workflow_dispatch`).
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
1. Abrir o fluxo de coleta.
2. No gatilho RSS "Quando um item de feed é publicado", trocar a URL do feed
   `https://feeds.feedburner.com/gov/NUXu` por `https://jarbas-martinho.github.io/buscaANS/feed.xml`.
3. Manter "Propriedade de data: PublishDate", a condição e a ação "Criar item".
4. Salvar. O primeiro aviso chegará com a próxima legislação detectada (os atos já existentes no feed
   estão datados pelo DOU, anteriores à troca, e normalmente não disparam o fluxo; no pior caso,
   os itens atuais do feed entram uma única vez na lista).

Observação: a coluna DataPublicação passa a receber o momento em que o coletor detectou o ato
(até ~45 minutos após o cadastro no portal: agendamento de 30 min, atrasos do GitHub e cache de 10 min do Pages). A data do DOU fica no início da descrição.

## Operação
- Execução manual: aba Actions > "Coletar legislações da ANS" > Run workflow, ou `gh workflow run coletar.yml`.
- Falhas: o GitHub envia e-mail ao dono do repositório quando o workflow falha. O feed anterior permanece publicado.
- Reprocessar do zero: apagar `data/estado.json` e `docs/feed.xml` e executar; ocorre nova semeadura sem disparar avisos.
- Forçar reenvio de um ato: remover a entrada dele de `data/estado.json`; na próxima execução ele volta ao feed com data atual.
