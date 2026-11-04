"""ETL 5 - Visualização Interativa (Streamlit + Plotly).
Responsável: Diogenes Christian

Rodar:  streamlit run dashboard/app.py
Filtros: período, país, gênero, artista e faixa de engajamento.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

st.set_page_config(page_title="Tendências Spotify × YouTube", page_icon="🎵", layout="wide")

# Deploy (Streamlit Community Cloud): as chaves ficam em "Secrets" no painel do site,
# nunca no GitHub. Aqui elas viram variáveis de ambiente para o pipeline usar.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, (str, int, float)):
            os.environ.setdefault(_k, str(_v))
except Exception:  # rodando local, sem secrets.toml: usa o .env
    pass

from src.config import Config  # noqa: E402


ISO3 = {"BR": "BRA", "US": "USA", "MX": "MEX", "AR": "ARG", "ES": "ESP", "JP": "JPN",
        "GB": "GBR", "FR": "FRA", "DE": "DEU", "IT": "ITA", "PT": "PRT", "CO": "COL",
        "CL": "CHL", "PE": "PER", "CA": "CAN", "KR": "KOR", "IN": "IND", "AU": "AUS"}
NOMES = {"BR": "Brasil", "US": "Estados Unidos", "MX": "México", "AR": "Argentina",
         "ES": "Espanha", "JP": "Japão", "GB": "Reino Unido", "FR": "França",
         "DE": "Alemanha", "IT": "Itália", "PT": "Portugal", "CO": "Colômbia",
         "CL": "Chile", "PE": "Peru", "CA": "Canadá", "KR": "Coreia do Sul",
         "IN": "Índia", "AU": "Austrália"}
AZUL, LARANJA = "#1F6FA8", "#E07B24"


@st.cache_data(ttl=600)
def carregar(database_url: str) -> dict[str, pd.DataFrame]:
    engine = create_engine(database_url)
    consultas = {
        "chart": """SELECT c.*, f.nome, f.artista_principal, f.artistas, f.genero_principal,
                           f.duracao_min, f.tem_feat, f.data_lancamento
                    FROM spotify_chart c JOIN spotify_faixa f USING (track_id)""",
        "videos": "SELECT * FROM youtube_video",
        "pares": """SELECT m.track_id, m.video_id, m.score, f.nome, f.artista_principal,
                           f.genero_principal
                    FROM musica_video m JOIN spotify_faixa f USING (track_id)
                    WHERE m.status = 'match'""",
        "correl": "SELECT * FROM correlacao_resumo",
        "regiao": "SELECT * FROM regiao_resumo",
        "overlap": "SELECT * FROM regiao_overlap",
        "execucoes": "SELECT * FROM pipeline_execucao ORDER BY inicio DESC",
    }
    try:
        with engine.connect() as con:
            dados = {k: pd.read_sql(text(q), con) for k, q in consultas.items()}
    finally:
        engine.dispose()
    for k in ["chart", "videos", "correl", "regiao", "overlap"]:
        dados[k]["snapshot_date"] = pd.to_datetime(dados[k]["snapshot_date"]).dt.date
    for coluna in ["views", "likes", "comentarios", "taxa_engajamento", "views_por_dia"]:
        dados["videos"][coluna] = pd.to_numeric(dados["videos"][coluna], errors="coerce")
    dados["chart"]["genero_principal"] = dados["chart"]["genero_principal"].fillna("(sem gênero)")
    return dados


try:
    d = carregar(Config().database_url)
except Exception:  # não expõe credenciais nem detalhes da conexão
    st.error("Banco indisponível ou esquema incompleto. Configure DATABASE_URL ou copie "
             "o banco real para data/tendencias.db. Execute o pipeline real antes de abrir o dashboard.")
    st.stop()

# ------------------------------------------------------------------ filtros
st.sidebar.title("Filtros")
if st.sidebar.button("Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

if d["chart"].empty:
    st.info("Banco sem dados do Spotify. Execute a carga real antes de consultar as cinco abas.")
    st.stop()

datas = sorted(d["chart"]["snapshot_date"].unique())
if len(datas) > 1:
    ini, fim = st.sidebar.select_slider("Período (semanas)", options=datas,
                                        value=(datas[0], datas[-1]),
                                        format_func=lambda x: x.strftime("%d/%m/%Y"))
else:
    ini = fim = datas[0]
paises_disp = sorted(d["chart"]["country"].unique())
paises = st.sidebar.multiselect("Países", paises_disp, default=paises_disp,
                                format_func=lambda p: f"{p} · {NOMES.get(p, p)}")
generos = st.sidebar.multiselect("Gêneros", sorted(d["chart"]["genero_principal"].unique()),
                                 placeholder="Todos")
artistas = st.sidebar.multiselect("Artistas", sorted(d["chart"]["artista_principal"].unique()),
                                  placeholder="Todos")
eng_max = pd.to_numeric(d["videos"]["taxa_engajamento"], errors="coerce").max()
eng_max = float(eng_max) if pd.notna(eng_max) else 10.0
eng = st.sidebar.slider("Engajamento no YouTube (%)", 0.0, round(eng_max + 0.5, 1),
                        (0.0, round(eng_max + 0.5, 1)), step=0.1)

def no_periodo(df):
    return df[(df["snapshot_date"] >= ini) & (df["snapshot_date"] <= fim) & df["country"].isin(paises)]

chart = no_periodo(d["chart"])
if generos:
    chart = chart[chart["genero_principal"].isin(generos)]
if artistas:
    chart = chart[chart["artista_principal"].isin(artistas)]
videos = no_periodo(d["videos"])
videos = videos[videos["taxa_engajamento"].between(*eng) | videos["taxa_engajamento"].isna()]
# Artista e gênero limitam vídeos aos vínculos confirmados; sem esses filtros,
# YouTube continua mostrando todos os vídeos em alta no período e países.
if generos or artistas:
    ids = d["pares"].loc[d["pares"]["track_id"].isin(chart["track_id"]), "video_id"]
    videos = videos[videos["video_id"].isin(ids)]
ultima = chart["snapshot_date"].max() if not chart.empty else fim

if chart.empty or not paises:
    st.warning("Nenhum dado para os filtros escolhidos.")
    st.stop()

# ------------------------------------------------------------------ cabeçalho
st.title("Tendências musicais e audiovisuais · Spotify × YouTube")
# O modo vem do próprio banco (última execução), e não do .env: assim um banco gerado
# com dados reais num PC continua marcado como real quando é aberto em outro PC.
ultimas = d["execucoes"]
modos = set(ultimas.loc[ultimas["status"] == "ok", "mensagem"].dropna())
modo = "real" if modos == {"modo=real"} else "simulado" if modos == {"modo=simulado"} else "não confirmado ou misto"
if modo != "real":
    st.warning(f"Origem do banco: {modo}. Estes dados não comprovam resultados reais.")
st.caption(f"Semanas de {ini:%d/%m/%Y} a {fim:%d/%m/%Y} · {len(paises)} países · "
           f"fonte: Spotify Charts + Spotify Web API + YouTube Data API v3"
           + (" · ⚠️ DADOS SIMULADOS" if modo == "simulado" else ""))

v_musica = videos.merge(d["pares"][["video_id", "track_id"]], on="video_id")
v_musica = v_musica.merge(chart[["track_id", "country", "snapshot_date"]].drop_duplicates(),
                          on=["track_id", "country", "snapshot_date"])
v_musica = v_musica.sort_values("views", ascending=False).drop_duplicates(
    ["track_id", "country", "snapshot_date"])
mediana = videos["taxa_engajamento"].median()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Faixas no Top 50", chart["track_id"].nunique())
k2.metric("Artistas", chart["artista_principal"].nunique())
k3.metric("Vídeos em alta", videos["video_id"].nunique())
k4.metric("Engajamento mediano YT", f"{mediana:.2f}%" if pd.notna(mediana) else "Sem dados")
k5.metric("Faixas com vídeo em alta", v_musica["track_id"].nunique())

aba1, aba2, aba3, aba4, aba5 = st.tabs(
    ["🎧 Spotify", "▶️ YouTube", "🔗 Música × Vídeo", "🌎 Regiões", "⚙️ Pipeline"])

# ------------------------------------------------------------------ Spotify
with aba1:
    c1, c2 = st.columns(2)
    top_art = (chart[chart["snapshot_date"] == ultima].groupby("artista_principal")["streams"]
               .sum().nlargest(10).sort_values().reset_index())
    c1.plotly_chart(px.bar(top_art, x="streams", y="artista_principal", orientation="h",
                           title=f"Top 10 artistas por streams (semana {ultima:%d/%m})",
                           labels={"streams": "Streams", "artista_principal": ""},
                           color_discrete_sequence=[AZUL]), width="stretch")
    gen = (chart[chart["snapshot_date"] == ultima].groupby("genero_principal")
           .agg(faixas=("track_id", "nunique"), duracao=("duracao_min", "mean"))
           .nlargest(10, "faixas").reset_index())
    c2.plotly_chart(px.bar(gen, x="genero_principal", y="faixas", color="duracao",
                           title="Gêneros no Top 50 (cor = duração média em min)",
                           labels={"genero_principal": "", "faixas": "Faixas", "duracao": "Min"},
                           color_continuous_scale="Blues"), width="stretch")

    melhores = chart.groupby("track_id")["indice_popularidade"].mean().nlargest(8).index
    linha = chart[chart["track_id"].isin(melhores)].copy()
    linha["faixa"] = linha["nome"] + " – " + linha["artista_principal"]
    linha = linha.groupby(["snapshot_date", "faixa"], as_index=False)["position"].min()
    fig = px.line(linha, x="snapshot_date", y="position", color="faixa", markers=True,
                  title="Evolução da melhor posição das faixas mais populares",
                  labels={"snapshot_date": "Semana", "position": "Posição", "faixa": ""})
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Ranking da semana")
    st.dataframe(chart[chart["snapshot_date"] == ultima]
                 .sort_values(["country", "position"])
                 [["country", "position", "nome", "artistas", "genero_principal",
                   "duracao_min", "streams", "indice_popularidade", "weeks_on_chart"]]
                 .rename(columns={"country": "País", "position": "Pos.", "nome": "Faixa",
                                  "artistas": "Artistas", "genero_principal": "Gênero",
                                  "duracao_min": "Duração (min)", "streams": "Streams",
                                  "indice_popularidade": "Índice pop.",
                                  "weeks_on_chart": "Semanas"}),
                 width="stretch", hide_index=True)

# ------------------------------------------------------------------ YouTube
with aba2:
    if videos.empty:
        st.info("Nenhum vídeo para os filtros escolhidos.")
    c1, c2 = st.columns(2)
    vu = videos[videos["snapshot_date"] == ultima].copy()
    vu["tamanho"] = vu["comentarios"].astype("float").fillna(0).clip(lower=0) + 1
    c1.plotly_chart(px.scatter(vu, x="views", y="taxa_engajamento", color="country",
                               hover_name="titulo", log_x=True, size="tamanho",
                               title="Views × engajamento (tamanho = comentários)",
                               labels={"views": "Views (log)", "taxa_engajamento": "Engajamento (%)",
                                       "country": "País"}), width="stretch")
    eng_sem = videos.groupby(["snapshot_date", "country"], as_index=False)["taxa_engajamento"].mean()
    c2.plotly_chart(px.line(eng_sem, x="snapshot_date", y="taxa_engajamento", color="country",
                            markers=True, title="Engajamento médio por semana",
                            labels={"snapshot_date": "Semana", "taxa_engajamento": "%",
                                    "country": "País"}), width="stretch")
    st.subheader("Vídeos de música mais vistos")
    st.dataframe(vu.nlargest(20, "views")[["country", "titulo", "canal", "views", "likes",
                                           "comentarios", "taxa_engajamento", "views_por_dia"]],
                 width="stretch", hide_index=True)

# ------------------------------------------------------------------ correlação
with aba3:
    cruz = chart.merge(v_musica[["track_id", "country", "snapshot_date", "views",
                                 "taxa_engajamento", "titulo"]],
                       on=["track_id", "country", "snapshot_date"], how="inner")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.scatter(cruz, x="position", y="views", color="country", log_y=True,
                               hover_name="nome", trendline=None,
                               title="Posição no Spotify × views no YouTube",
                               labels={"position": "Posição no Top 50", "views": "Views (log)",
                                       "country": "País"}), width="stretch")
    from src.etl3_correlacao import resumir
    faixas = chart[["track_id", "data_lancamento"]].drop_duplicates("track_id")
    pares = d["pares"].assign(status="match")
    corr = resumir(chart[["track_id", "country", "snapshot_date", "position"]],
                   faixas, videos, pares)
    if cruz.empty:
        st.info("Nenhuma música vinculada a vídeo nos países e semanas selecionados.")
    c2.plotly_chart(px.bar(corr.groupby("country", as_index=False)
                           [["pct_faixas_com_video", "spearman_rho"]].mean(),
                           x="country", y="pct_faixas_com_video",
                           title="% do Top 50 que também está em alta no YouTube",
                           labels={"country": "País", "pct_faixas_com_video": "%"},
                           color_discrete_sequence=[LARANJA]), width="stretch")
    rho = corr["spearman_rho"].astype(float).mean()
    if pd.isna(rho):
        st.info("Correlação indisponível: são necessários ao menos cinco pares com variação por país e semana.")
    else:
        st.info(f"Correlação de Spearman média entre posição e views: **ρ = {rho:.2f}**. "
            "Valor negativo = quanto MELHOR a posição no Spotify (número menor), MAIS views "
            "o clipe tem. Correlação não prova causalidade.")
    st.subheader("Músicas presentes nas duas plataformas")
    resumo = (cruz.groupby(["nome", "artista_principal"])
              .agg(paises=("country", "nunique"), melhor_posicao=("position", "min"),
                   views_max=("views", "max"), engajamento=("taxa_engajamento", "mean"))
              .sort_values(["paises", "views_max"], ascending=False).reset_index())
    st.dataframe(resumo, width="stretch", hide_index=True)

# ------------------------------------------------------------------ regiões
with aba4:
    from src.etl4_regiao import resumo_regioes, sobreposicao
    reg = resumo_regioes(chart[["snapshot_date", "country", "track_id", "streams"]],
                         chart[["track_id", "artista_principal", "genero_principal", "duracao_min"]]
                         .drop_duplicates("track_id"), videos)
    st.caption("Faixas locais: exclusivas entre os países selecionados, após os filtros.")
    reg = reg[reg["snapshot_date"] == reg["snapshot_date"].max()].copy()
    metrica = st.selectbox("Métrica do mapa", {
        "pct_faixas_locais": "% de faixas locais (só tocam ali)",
        "engajamento_medio_yt": "Engajamento médio no YouTube (%)",
        "streams_total": "Streams totais do Top 50",
        "duracao_media_min": "Duração média das faixas (min)",
    }.items(), format_func=lambda x: x[1])
    reg["iso3"] = reg["country"].map(ISO3)
    reg["pais"] = reg["country"].map(NOMES)
    m1, m2 = st.columns([3, 2])
    # O mapa baixa o contorno dos países da internet (cdn.plot.ly). As barras ao lado
    # mostram a mesma métrica e funcionam mesmo offline (plano B da apresentação).
    m1.plotly_chart(px.choropleth(reg, locations="iso3", color=metrica[0], hover_name="pais",
                                  hover_data=["artista_top", "genero_top"],
                                  color_continuous_scale="Oranges", title=metrica[1],
                                  labels={metrica[0]: ""}), width="stretch")
    m2.plotly_chart(px.bar(reg.sort_values(metrica[0]), x=metrica[0], y="pais", orientation="h",
                           title="Mesma métrica, por país", text_auto=".3~s",
                           labels={metrica[0]: "", "pais": ""},
                           color_discrete_sequence=[LARANJA]), width="stretch")
    c1, c2 = st.columns(2)
    ov = sobreposicao(chart).rename(columns={"pais_a": "country"})
    ov = ov[ov["pais_b"].isin(paises) & (ov["snapshot_date"] == ov["snapshot_date"].max())]
    matriz = pd.concat([ov, ov.rename(columns={"country": "pais_b", "pais_b": "country"})])
    matriz = matriz.pivot_table(index="country", columns="pais_b", values="jaccard")
    if matriz.empty:
        c1.info("Selecione ao menos dois países com dados para comparar os rankings.")
    else:
        c1.plotly_chart(px.imshow(matriz, text_auto=".2f", color_continuous_scale="Blues",
                              title="Semelhança entre os Top 50 (índice de Jaccard)",
                              labels={"x": "", "y": "", "color": "Jaccard"}),
                    width="stretch")
    c2.dataframe(reg[["pais", "artista_top", "genero_top", "pct_faixas_locais",
                      "engajamento_medio_yt", "views_medianas_yt"]]
                 .rename(columns={"pais": "País", "artista_top": "Artista nº 1",
                                  "genero_top": "Gênero nº 1", "pct_faixas_locais": "% locais",
                                  "engajamento_medio_yt": "Engaj. YT %",
                                  "views_medianas_yt": "Views medianas"}),
                 width="stretch", hide_index=True)

# ------------------------------------------------------------------ pipeline
with aba5:
    st.subheader("Últimas execuções do ETL")
    st.caption("Histórico global do banco; os filtros musicais não se aplicam às execuções.")
    if d["execucoes"].empty:
        st.info("Nenhuma execução registrada; origem dos dados não confirmada.")
    st.dataframe(d["execucoes"].head(20), width="stretch", hide_index=True)
