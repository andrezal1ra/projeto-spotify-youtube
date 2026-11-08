# Resultados dos CSVs — ETL 1 da Andreza

Análise local dos arquivos versionados. Nenhuma consulta ao Spotify foi realizada nesta etapa.

## Cobertura do Top 50

| País | Semanas | Posições | Faixas únicas no país | Streams somados |
|---|---:|---:|---:|---:|
| AR | 5 | 250 | 65 | 176.253.462 |
| BR | 5 | 250 | 73 | 960.831.888 |
| ES | 5 | 250 | 83 | 294.149.630 |
| JP | 5 | 250 | 66 | 291.299.528 |
| MX | 5 | 250 | 66 | 930.559.730 |
| US | 5 | 250 | 76 | 1.092.243.418 |

Período dos arquivos: 01, 08, 15, 22 e 29 de outubro de 2026. São 1.500 posições e 400 faixas únicas no conjunto. As quantidades de faixas únicas por país não devem ser somadas para obter o total global, pois uma música pode aparecer em vários países.

Streams representam reproduções informadas nos CSVs, não ouvintes únicos. Os totais abrangem somente o Top 50 selecionado, não todo o catálogo ou todo o consumo do país. A origem externa dos números não foi comparada ao portal Charts.

## Dez faixas com mais streams somados nos arquivos selecionados

| Faixa | Artistas conforme CSV | Países em que apareceu | Streams somados |
|---|---|---:|---:|
| BbY WOW | KAROL G, Judeline, rusowsky | 4 | 107.174.954 |
| OLIVIA LA FLAKA | Natanael Cano, Tito Double P, Victor Mendivil, Ovi | 1 | 46.701.618 |
| Pós - Ao Vivo | Felipe e Rodrigo | 1 | 45.232.384 |
| Postinho de Gasolina | João Gustavo e Murilo, Grelo | 1 | 44.325.181 |
| Patient Zero | Taylor Swift | 2 | 42.529.324 |
| Nicole Kidman | ADÉLA | 1 | 41.691.563 |
| Choosin' Texas | Ella Langley | 1 | 39.848.756 |
| RIKI | Neton Vega | 1 | 33.737.071 |
| SUPERESTRELLA | Aitana | 3 | 30.956.161 |
| Earrings | Malcolm Todd | 1 | 30.839.080 |

Esse ranking agrega as observações dos seis países e das cinco semanas. Não é o ranking global oficial do Spotify.

## Verificações concluídas sem API

- Recalculei os números diretamente dos CSVs com a biblioteca padrão do Python.
- Reconciliei todas as 1.500 chaves e seus streams com o banco SQLite da auditoria; não houve divergências.
- Executei a suíte completa de testes local: **100 testes passaram em 10,69 segundos**. Os testes de API usam respostas falsas.
- O teste de pausa e retomada confirma que a coleta consegue reutilizar uma faixa já salva no cenário testado.

## Parte ainda pendente

Enriquecimento autenticado completo das 400 faixas e validação final de artistas oficiais, gêneros, álbuns, duração e lançamento. O acesso à API não foi utilizado para produzir este resumo.

## Fala curta para apresentar os resultados

“Concluí a validação local dos CSVs e conferi os dados carregados no banco. Os 30 arquivos contêm 6.000 linhas, e o projeto seleciona as 50 primeiras de cada um. Isso gera 1.500 posições e 400 músicas diferentes. A suíte completa teve 100 testes aprovados. Também produzi um resumo por país e um ranking calculado a partir dos streams dos arquivos. A confirmação dos metadados da API continua pendente, então não apresento esse enriquecimento como concluído.”
