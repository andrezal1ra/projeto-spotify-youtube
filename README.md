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

## Resultados com dados reais

Os resultados devem ser registrados após conectar o banco produzido pelo pipeline real.
Não há banco real incluído nesta cópia. Os CSVs do Spotify, isoladamente, não comprovam
as métricas de YouTube, matching ou correlação. Consulte as cinco abas e registre o
período, os países e filtros junto com os resultados. Não use os números de testes
simulados como conclusões sobre o mercado.

## Limitações e melhorias futuras

Ver [`docs/decisoes_tecnicas.md`](docs/decisoes_tecnicas.md#melhorias-futuras).

## Deploy online (Streamlit Community Cloud)

1. Execute o pipeline real em ambiente com as credenciais e valide o banco gerado.
2. Configure um banco PostgreSQL persistente acessível pelo servidor; informe sua
   `DATABASE_URL` em Secrets. Alternativamente, disponibilize `data/tendencias.db`
   no ambiente do app por um processo de entrega controlado. O banco local é temporário
   na hospedagem; ele não será reconstruído pelo dashboard.
3. No Streamlit Community Cloud, selecione o repositório, a branch que contém estas
   alterações e o arquivo `dashboard/app.py`. Use Python 3.12 e `requirements.txt`.
4. Abra o app e confira Spotify, YouTube, Música × Vídeo, Regiões e Pipeline.
   Sem o banco ou com esquema incompleto, o app mostra orientação de configuração.
5. Após uma nova carga, use **Atualizar dados** para limpar o cache (também expira em 10 minutos).

O dashboard apenas lê os dados: não executa coleta nem cria dados simulados na abertura.
As chaves das APIs são necessárias no ambiente de coleta; para consultar um banco
pronto, basta configurar o acesso ao banco. Não publique senhas nem arquivos `.env`.
