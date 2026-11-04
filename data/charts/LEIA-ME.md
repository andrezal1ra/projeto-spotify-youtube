# CSVs do Spotify Charts (modo real)

1. Acesse https://charts.spotify.com e faça login (conta Spotify gratuita serve).
2. Em **Charts**, escolha *Top Songs* → *Weekly* → o país.
3. Clique no ícone de download (CSV) no canto da tabela.
4. Salve aqui **sem renomear**. O nome precisa ser como
   `regional-br-weekly-2026-10-16.csv`: o pipeline tira o país e a data do nome.
5. Repita para cada país do `.env` (PAISES) e para cada semana que quiserem analisar.

Colunas usadas: `rank`, `uri`, `artist_names`, `track_name`, `streams`, `weeks_on_chart`.

## Validação

Os arquivos versionados são verificados por `tests/test_csvs_spotify.py`. O teste
confirma a cobertura de países e semanas, o padrão dos nomes, as colunas
obrigatórias, as 200 posições do ranking, campos ausentes, URIs duplicadas e os
tipos e intervalos dos valores numéricos.

Execute com:

```bash
pytest tests/test_csvs_spotify.py
```
