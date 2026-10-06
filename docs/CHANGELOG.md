# Histórico de versões

## 1.4.0 (2026-10-06)
- Proteção da publicação no GitHub Pages (`python -m buscaans.pages`). Em 05/10 a publicação da RN 681 travou e foi cancelada pelo GitHub após 15 minutos; o feed ficou desatualizado sem aviso.
- Após cada push, a coleta espera a publicação do commit (até 20 minutos) e reexecuta uma vez a que falhar. Se ainda assim não publicar, a execução falha e o GitHub avisa por e-mail.
- No início de cada coleta, reexecuta a publicação mais recente se ela tiver falhado.
- Tempo máximo do job de coleta: de 10 para 30 minutos. Sem nova permissão: a reexecução usa `actions: write`.

## 1.3.0 (2026-09-29)
- Causa do incidente de 28/09 confirmada: a ANS publica **versões atualizadas** dos atos, com `Autonumber` e guid novos e o campo `AutonumberOriginal` apontando para o ato original.
- Reconhecimento pela ordem guid, número da versão, `AutonumberOriginal` e, só por último, identidade pelo título. Versão confirmada pelo número original atualiza título, ementa, DOU, situação e link sem republicar, sem exigir revisão e sem contar como troca no limite de proteção.
- Campo `original` no estado, preenchido uma vez para as normas já conhecidas (uma consulta por norma).
- Links no feed e no estado passam a usar o número original, que o portal redireciona para a versão vigente.
- `--reenviar` aceita também o número original.
- Teste de regressão com os números originais reais dos 70 registros do incidente (`tests/fixtures/originais_2026_09_29.json`).

## 1.2.0 (2026-09-29)
- Identidade normativa independente de GUID/Autonumber da ANS, com todos os identificadores conciliados preservados.
- Trocas de cadastro mantêm o `pubDate`, a marca de preexistente e o GUID RSS original; novos atos usam GUID derivado da identidade.
- Bloqueio antes da gravação para trocas em massa, excesso de atos desconhecidos e normas antigas/sem DOU; resumo no Actions e aprovação específica do lote.
- Conflitos de conteúdo exigem revisão e não são liberados pela aprovação de volume.
- Conciliação offline e idempotente do incidente da coleta #20: 29 duplicados conciliados, 41 normas e 70 referências preservadas; cinco falsas novidades retiradas do feed.
- Reenvio por identificador antigo ou atual sem apagar histórico; testes automáticos em PR sem coleta/publicação.

## 1.1.2 (2026-09-25)
- Agendamento movido para o minuto 17 (09:17, 13:17 e 18:17 de Brasília): na hora cheia o GitHub atrasava as execuções em até 3 horas e descartou as das 09h.

## 1.1.1 (2026-09-24)
- Licença MIT (`LICENSE`).
- Removidas referências a unidade organizacional específica na documentação.

## 1.1.0 (2026-09-23)
- Coleta três vezes ao dia (09h, 13h e 18h de Brasília) no lugar de a cada 30 minutos.
- Semeadura marca os atos existentes como `pre_existente` e os mantém fora do feed, eliminando o risco de o Power Automate recriá-los no SharePoint. Feed reimplantado vazio.
- Opção `--reenviar` e campo "reenviar" na execução manual do workflow para devolver um ato ao feed (usado para colocar a RN 680 no feed).

## 1.0.0 (2026-09-23)
- Coletor do novo portal de legislações da ANS (aplicação Mendix, endpoint `/xas/`) com sessão anônima.
- Descoberta automática do `queryId` da lista no XML da página, com tentativa entre candidatos e valor reserva em configuração.
- Filtro por tipo de ato configurável (mantidas as 5 exclusões do fluxo antigo).
- Estado em `data/estado.json` e feed RSS 2.0 em `docs/feed.xml`, publicado no GitHub Pages.
- `pubDate` do item = momento da detecção (semeadura inicial datada pelo DOU).
- Workflow do GitHub Actions a cada 30 minutos, com testes antes da coleta e reativação automática do agendamento.
- Ato sem `Autonumber` é registrado em log e ignorado, sem interromper a coleta dos demais.
