# Análise Integrada de Tendências Musicais e Audiovisuais: Spotify e YouTube

**SENAC Pernambuco · Data Science · Prof. Heuryk Wylk**
**Equipe 03 — (H)LGBT**: Gabrielle Mendes (líder), Andreza Lira, Louise Martins, Beatriz Prazim, Diogenes Christian

Pipeline ETL que integra Spotify e YouTube para analisar o que está em alta em música e em vídeo. Ele cruza as duas fontes, compara países e mostra tudo num dashboard interativo.

| ETL | Tema | Responsável | Código |
|---|---|---|---|
| 1 | Playlists e faixas populares no Spotify | Andreza Lira | `src/etl1_spotify.py`, `src/extract/spotify.py` |
| 2 | Vídeos populares no YouTube | Louise Martins | `src/etl2_youtube.py`, `src/extract/youtube.py` |
| 3 | Correlação entre música e vídeo | Gabrielle Mendes | `src/etl3_correlacao.py` |
| 4 | Engajamento por região | Beatriz Prazim | `src/etl4_regiao.py` |
| 5 | Visualização interativa | Diogenes Christian | `dashboard/app.py` |

---

## Arquitetura

```
 Spotify Charts (CSV) ─┐
 Spotify Web API ──────┼─► EXTRACT ─► camada RAW ─► TRANSFORM ─► camada TRATADA ─► Dashboard
 YouTube Data API v3 ──┘   (retry,      (JSON         (limpeza,      (métricas,        (Streamlit
                           rate limit,   bruto)        validação)     cruzamentos)      + Plotly)
                           logs)
                          └──────────────── PostgreSQL 16 · tudo em Docker Compose ───────────────┘
```

Mais detalhes em [`docs/arquitetura.md`](docs/arquitetura.md) e [`docs/decisoes_tecnicas.md`](docs/decisoes_tecnicas.md).

## Como rodar

### Opção A — Docker (recomendado, igual para os 5)

```bash
docker compose up --build     # sem .env roda no modo simulado; com .env usa o MODO dele
```

O comando sobe o PostgreSQL e roda o pipeline (ETL 1 a 4). Depois abra o dashboard em **http://localhost:8501**.

### Opção B — Python local (sem Docker)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Sem Docker, apague a linha DATABASE_URL do .env: o projeto usa um SQLite local
python -m src.pipeline --modo simulado
streamlit run dashboard/app.py
```

### Rodar os testes

```bash
pytest           # 28 testes: transformações, qualidade, pipeline ponta a ponta e precisão do matching
```

## Modo real (com as APIs)

1. **Spotify**: crie um app em https://developer.spotify.com/dashboard. Desde fevereiro de 2026, o dono de um app em Development Mode precisa ter **Spotify Premium**. Copie o Client ID e o Client Secret para o `.env`.
2. **YouTube**: no Google Cloud Console, ative a *YouTube Data API v3* e crie uma *API key*. Cole a chave no `.env`.
3. **Charts**: baixe os CSVs do Top 50 semanal de cada país em https://charts.spotify.com e salve em `data/charts/`. Veja `data/charts/LEIA-ME.md`.
4. No `.env`, coloque `MODO=real` e rode `python -m src.pipeline` (ou `docker compose up`).

### Apresentar com dados reais em outro computador

O dashboard só lê o banco, que no modo local é um único arquivo: `data/tendencias.db`.

1. No PC com as chaves, rode `python -m src.pipeline` com `MODO=real`.
2. Copie `data/tendencias.db` para a pasta `data/` do projeto no outro PC (pen drive, Drive ou WhatsApp).
3. No outro PC, rode **só** `streamlit run dashboard/app.py`. **Não rode o pipeline lá**, senão ele mistura dados simulados no banco real.

As chaves nunca saem do primeiro PC. O dashboard descobre pelo próprio banco que os dados são reais e tira o aviso de "dados simulados".

No modo real, a coleta do YouTube (feita no dia) é alinhada à semana do CSV do Spotify Charts mais próxima, para as duas fontes se cruzarem. A data original da coleta continua na camada RAW.

A API do YouTube só devolve o que está em alta **agora**. Para ter série histórica, rodem o pipeline toda semana: o upsert acumula as coletas sem duplicar.

## Estrutura

```
├── src/
│   ├── extract/spotify.py    # Charts CSV + Spotipy (retry, rate limit, cache de artistas)
│   ├── extract/youtube.py    # videos.list mostPopular por país (controle de cota)
│   ├── etl1_spotify.py ... etl4_regiao.py
│   ├── pipeline.py           # orquestrador: python -m src.pipeline [--modo] [--etapas]
│   ├── db.py                 # esquema, upsert idempotente, auditoria das execuções
│   ├── qualidade.py          # validações (chaves, nulos, faixas de valores)
│   ├── mock_data.py          # dados SIMULADOS (artistas e músicas fictícios)
│   ├── utils.py              # normalização de texto, limitador de requisições
│   └── config.py             # .env e logging (logs/pipeline.log)
├── dashboard/app.py          # ETL 5: Streamlit
├── sql/schema.sql            # tabelas RAW e TRATADAS
├── tests/                    # pytest
├── docs/                     # arquitetura, decisões, dicionário de dados, Kahoot
├── Dockerfile, docker-compose.yml, requirements.txt, .env.example
```

## Resultados com dados simulados

Estes resultados validam o pipeline, **não são conclusões sobre o mercado real**:

- Os 6 países × 4 semanas produziram 1.200 posições de chart, 218 faixas e 1.200 registros de vídeos em alta.
- O matching música ↔ vídeo acertou 98,6% dos pares (212 pares "match") e encontrou 97% dos clipes reais. Isso é possível medir porque, no simulado, sabemos o gabarito.
- A correlação de Spearman entre posição no Spotify e views no YouTube ficou em ρ ≈ −0,64. Como o 1º lugar é o número menor, o sinal negativo quer dizer que posição melhor vem com mais views.
- O pipeline completo roda em cerca de 2 segundos e é idempotente: rodar duas vezes não duplica dados.

Com os dados reais, substituam esses números pelos que o dashboard mostrar.

## Limitações e melhorias futuras

Ver [`docs/decisoes_tecnicas.md`](docs/decisoes_tecnicas.md#melhorias-futuras).

## Deploy online (Streamlit Community Cloud, grátis)

1. Suba o projeto para um repositório no GitHub. O `.gitignore` já impede que o `.env` vá junto. Para o modo real, inclua os CSVs de `data/charts/` no repositório.
2. Em https://share.streamlit.io, entre com o GitHub e clique em **Create app**. Escolha o repositório, a branch `main` e o arquivo `dashboard/app.py`.
3. Em **Advanced settings**, escolha Python 3.12 e, em **Secrets**, cole as chaves no formato TOML:

```toml
MODO = "real"
SPOTIFY_CLIENT_ID = "..."
SPOTIFY_CLIENT_SECRET = "..."
YOUTUBE_API_KEY = "..."
PAISES = "BR,US,MX,AR,ES,JP"
```

4. Clique em **Deploy**. Na primeira abertura o dashboard roda o pipeline sozinho (alguns minutos) e depois mostra os dados.

Sem os Secrets, o app sobe no modo simulado. O banco no servidor é temporário: quando o app "dorme" e acorda, o pipeline roda de novo na primeira visita, buscando o YouTube do dia. Para trocar a semana do Spotify, suba CSVs novos em `data/charts/`.
