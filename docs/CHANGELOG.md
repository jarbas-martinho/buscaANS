# Histórico de versões

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
