# Validação final do ETL 2 — Louise Martins

Coleta real executada em 04/11/2026, entre 17:35:09 e 17:35:15 (America/Sao_Paulo; UTC−03:00), usando YouTube Data API v3, `videos.list`, `chart=mostPopular`, `videoCategoryId=10`. Foram solicitados até 50 vídeos por país; o retorno efetivo foi de 30 por país. Volume inferior ao limite solicitado não significa, por si só, falha de paginação.

## Resultado observado

| País | RAW | Música na tratada | Fora da categoria 10 (somente RAW) |
|---|---:|---:|---:|
| BR | 30 | 26 | 4 |
| US | 30 | 28 | 2 |
| MX | 30 | 28 | 2 |
| AR | 30 | 30 | 0 |
| ES | 30 | 27 | 3 |
| JP | 30 | 25 | 5 |
| Total | 180 | 164 | 16 |

As seis regiões retornaram dados. Não houve erro de API ou esgotamento de cota nesta coleta. O total é de observações por país: o mesmo vídeo pode aparecer em mais de um país sem constituir duplicação.

- Duplicações na chave `(video_id, country, snapshot_date)`: 0 na RAW e 0 na tratada.
- Ausentes em título, views, likes, comentários, duração e publicação: 0 na tratada.
- Views, likes e comentários negativos: 0 na tratada.
- Categoria diferente de Música: 16 no retorno, preservados na RAW; 0 na tratada após a correção.

Também foi verificada a idempotência de gravação dos dados reais já coletados: um novo upsert das tabelas manteve os totais em 180 RAW e 164 tratados, sem nova chamada à API.

Embora a solicitação tenha usado categoria 10, a resposta efetiva continha categorias 20, 22, 23, 24 e 27. O ETL agora aplica explicitamente o contrato de categoria à carga tratada. Isso é uma classificação por metadado da API, não uma avaliação manual do conteúdo dos vídeos.

## Datas e alinhamento

Os 30 CSVs disponíveis abrangem seis países e cinco semanas: 01, 08, 15, 22 e 29/10/2026. Para todos os países, a coleta real de **04/11/2026** foi alinhada a **29/10/2026**, com distância de **6 dias**, dentro do limite de aviso de 7 dias. A RAW mantém `snapshot_date=2026-11-04` e `extracted_at`; a tratada usa a semana do Chart para os cruzamentos. As métricas de idade do vídeo são calculadas antes do alinhamento, usando a data da coleta.

Esse cruzamento aproxima uma coleta atual de um Chart semanal fechado. Não comprova quais vídeos estavam em alta em 29/10, nem cria histórico retroativo do YouTube. Cada país é alinhado apenas às suas próprias semanas; país sem Chart é recusado.

## Correções e testes

Foram corrigidos o alinhamento global entre países, o tratamento de coleta vazia, a aceitação de títulos em branco, durações negativas e vídeos fora da categoria Música. Duplicações RAW passam a ser validadas antes do alinhamento. Falhas ou retornos vazios por país deixam de produzir uma carga tratada parcial com sucesso: a RAW recebida é preservada e a execução falha de forma explícita. Mensagens de erro do extrator não imprimem URLs que possam conter a API key.

Validação local: **95 testes passaram**, em Python 3.14.5, incluindo paginação, retry, cota, falhas por país, qualidade, alinhamento, ausência de contagens, regressão de categorias e pipeline completo com dados simulados. Comando:

```bash
python -m pytest -q -p no:cacheprovider --basetemp=../pytest-louise-final-02 --tb=short
```

O teste ponta a ponta usa dados simulados; os números da tabela acima provêm da coleta real, registrada em [evidencias_youtube_2026-11-04.json](evidencias_youtube_2026-11-04.json). Para reproduzir uma nova coleta em banco isolado:

```bash
python -m src.verificar_youtube --banco work/youtube-validacao.db --relatorio work/youtube-validacao.json
```

O banco de validação carrega os Charts dos CSVs sem chamar a API Spotify. Esta evidência cobre o ETL 2 da Louise; não atesta o enriquecimento do ETL 1 nem os resultados reais dos ETLs 3 e 4. Credenciais e arquivos `.env` não integram o commit.
