"""ETL 2 - Tendências de Vídeos Populares no YouTube.
Responsável: Louise Martins

Extract : vídeos de música em alta por país (videos.list mostPopular, categoria 10).
Transform: categorias, duração (ISO 8601 -> segundos), views, likes, comentários e
           métricas de engajamento.
Load    : raw_youtube_video, raw_youtube_categoria -> youtube_video.
"""
from __future__ import annotations

import json
import logging

import isodate
import numpy as np
import pandas as pd

from src import db
from src.config import Config
from src.extract import youtube as ext
from src.qualidade import validar
from src.utils import normalizar_titulo_video

log = logging.getLogger("etl2")


def duracao_segundos(iso: str | None) -> int | None:
    """'PT3M45S' -> 225. Retorna None para vazio ou inválido (ex.: lives 'P0D')."""
    if not iso:
        return None
    try:
        s = int(isodate.parse_duration(iso).total_seconds())
        return s or None
    except (isodate.ISO8601Error, ValueError):
        return None


def _int_ou_nulo(valor) -> float:
    # Likes ocultos / comentários desativados NÃO são zero: viram nulo.
    return float(valor) if valor not in (None, "") else np.nan


def transformar_videos(raw: pd.DataFrame, categorias: pd.DataFrame) -> pd.DataFrame:
    nomes_cat = dict(zip(categorias["category_id"], categorias["nome"])) if len(categorias) else {}
    linhas = []
    for _, r in raw.iterrows():
        it = json.loads(r["payload"])
        sn, st, cd = it.get("snippet", {}), it.get("statistics", {}), it.get("contentDetails", {})
        linhas.append({
            "video_id": r["video_id"], "country": r["country"],
            "snapshot_date": r["snapshot_date"], "posicao_trending": it.get("_posicao"),
            "titulo": (sn.get("title") or "").strip(),
            "canal": sn.get("channelTitle"), "category_id": sn.get("categoryId"),
            "publicado_em": sn.get("publishedAt"),
            "duracao_s": duracao_segundos(cd.get("duration")),
            "views": _int_ou_nulo(st.get("viewCount")),
            "likes": _int_ou_nulo(st.get("likeCount")),
            "comentarios": _int_ou_nulo(st.get("commentCount")),
        })
    df = pd.DataFrame(linhas)
    df["categoria"] = df["category_id"].map(nomes_cat).fillna("Desconhecida")
    df["titulo_normalizado"] = df["titulo"].map(normalizar_titulo_video)
    df["publicado_em"] = pd.to_datetime(df["publicado_em"], errors="coerce", utc=True).dt.tz_localize(None)

    views = df["views"].where(df["views"] > 0)
    interacoes = df["likes"].fillna(0) + df["comentarios"].fillna(0)
    sem_dados = df["likes"].isna() & df["comentarios"].isna()
    df["taxa_engajamento"] = (100 * interacoes / views).where(~sem_dados).round(3)
    df["likes_por_mil"] = (1000 * df["likes"] / views).round(2)
    idade = (pd.to_datetime(df["snapshot_date"]) - df["publicado_em"]).dt.days.clip(lower=1)
    df["views_por_dia"] = (df["views"] / idade).round(0)
    for c in ["views", "likes", "comentarios"]:
        df[c] = df[c].astype("Int64")
    df["duracao_s"] = df["duracao_s"].astype("Int64")
    return df


def alinhar_semana(videos: pd.DataFrame, datas_chart: list) -> pd.DataFrame:
    """Leva a data da coleta do YouTube para a semana de chart mais próxima.

    No modo real o YouTube só mostra o que está em alta HOJE (ex.: 18/10), mas o CSV
    do Spotify Charts é de uma semana fechada (ex.: 16/10). Sem este alinhamento as
    duas fontes nunca se cruzariam. A data original continua na camada RAW.
    """
    if videos.empty or not datas_chart:
        return videos
    datas = sorted(pd.to_datetime(pd.Series(datas_chart)).dt.date.unique())
    def mais_proxima(d):
        return min(datas, key=lambda c: abs((c - d).days))
    df = videos.copy()
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date.map(mais_proxima)
    # se duas coletas caírem na mesma semana, fica a mais recente
    return df.sort_values("publicado_em").drop_duplicates(
        ["video_id", "country", "snapshot_date"], keep="last")


def executar(cfg: Config, engine) -> dict:
    raw, cat = ext.extrair(cfg)
    db.upsert(engine, "raw_youtube_categoria", cat)
    db.upsert(engine, "raw_youtube_video", raw)
    videos = transformar_videos(raw, cat)
    if cfg.modo == "real":
        datas_chart = db.ler(engine, "SELECT DISTINCT snapshot_date FROM spotify_chart")["snapshot_date"]
        videos = alinhar_semana(videos, list(datas_chart))
    videos = validar(videos, "youtube_video",
                     chaves=["video_id", "country", "snapshot_date"],
                     obrigatorias=["titulo", "views"],
                     intervalos={"taxa_engajamento": (0, 100), "views": (0, None)})
    n = db.upsert(engine, "youtube_video", videos)
    log.info("ETL2: %d vídeos, engajamento mediano %.2f%%, %d sem likes visíveis",
             len(videos), videos["taxa_engajamento"].median(), videos["likes"].isna().sum())
    return {"linhas": n}
