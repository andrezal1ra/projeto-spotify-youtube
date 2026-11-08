"""ETL 1 - Análise de Playlists e Faixas Populares no Spotify.
Responsável: Andreza Lira

Extract : Top 50 semanal por país (Spotify Charts) + metadados da Web API.
Transform: artistas (principal, participações), gênero, duração e um índice de
           popularidade 0-100 calculado a partir de posição e streams.
Load    : raw_spotify_chart, raw_spotify_track -> spotify_faixa, spotify_chart.
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from src import db
from src.config import Config
from src.extract import spotify as ext
from src.qualidade import validar

log = logging.getLogger("etl1")


def transformar_faixas(raw_track: pd.DataFrame, raw_chart: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for _, r in raw_track.iterrows():
        p = json.loads(r["payload"])
        t = p["track"]
        artistas = [a["name"].strip() for a in t.get("artists", []) if a.get("name")]
        generos = []
        for a in p.get("artists_detail", []):
            for g in a.get("genres") or []:
                if g not in generos:
                    generos.append(g.strip().lower())
        album = t.get("album") or {}
        lanc = album.get("release_date")
        # datas com precisão de ano ("2019") ou mês ("2019-05") viram o 1º dia
        if lanc and album.get("release_date_precision") == "year":
            lanc = f"{lanc}-01-01"
        elif lanc and album.get("release_date_precision") == "month":
            lanc = f"{lanc}-01"
        linhas.append({
            "track_id": r["track_id"],
            "nome": (t.get("name") or "").strip(),
            "artista_principal": artistas[0] if artistas else None,
            "artistas": "; ".join(artistas),
            "n_artistas": len(artistas),
            "tem_feat": len(artistas) > 1,
            "duracao_ms": t.get("duration_ms"),
            "album": album.get("name"),
            "data_lancamento": lanc,
            "generos": "; ".join(generos) or None,
            "genero_principal": generos[0] if generos else None,
        })
    # Mantém o esquema mesmo se todas as chamadas da API falharem.
    faixas = pd.DataFrame(linhas, columns=[
        "track_id", "nome", "artista_principal", "artistas", "n_artistas",
        "tem_feat", "duracao_ms", "album", "data_lancamento", "generos",
        "genero_principal",
    ])

    # faixas sem metadados da API: completa com o que o CSV do chart traz
    sem_meta = set(raw_chart["track_id"]) - set(faixas.get("track_id", []))
    if sem_meta:
        base = raw_chart[raw_chart["track_id"].isin(sem_meta)].drop_duplicates("track_id")
        extra = pd.DataFrame({
            "track_id": base["track_id"], "nome": base["track_name"],
            "artista_principal": base["artist_names"].str.split(",").str[0].str.strip(),
            "artistas": base["artist_names"].str.replace(",", ";"),
        })
        extra["n_artistas"] = extra["artistas"].str.count(";") + 1
        extra["tem_feat"] = extra["n_artistas"] > 1
        faixas = pd.concat([faixas, extra], ignore_index=True)

    faixas["duracao_ms"] = pd.to_numeric(faixas["duracao_ms"], errors="coerce")
    faixas["duracao_min"] = (faixas["duracao_ms"] / 60000).round(2)
    faixas["data_lancamento"] = pd.to_datetime(faixas["data_lancamento"], errors="coerce").dt.date
    faixas["nome"] = faixas["nome"].fillna("(sem nome)")
    faixas["artista_principal"] = faixas["artista_principal"].fillna("(desconhecido)")
    return faixas


def transformar_chart(raw_chart: pd.DataFrame) -> pd.DataFrame:
    df = raw_chart[["snapshot_date", "country", "position", "track_id", "streams",
                    "weeks_on_chart"]].copy()
    grupo = df.groupby(["snapshot_date", "country"])["streams"]
    streams_rel = df["streams"] / grupo.transform("max")                 # 0-1 no país/semana
    posicao_rel = (51 - df["position"]) / 50                              # 1 = 1º lugar
    # Índice próprio, já que a API removeu o campo popularity (fev/2026)
    df["indice_popularidade"] = (100 * (0.6 * streams_rel.fillna(posicao_rel) + 0.4 * posicao_rel)).round(1)
    df["streams"] = df["streams"].astype("Int64")
    df["weeks_on_chart"] = df["weeks_on_chart"].astype("Int64")
    return df


def executar(cfg: Config, engine) -> dict:
    raw_chart, raw_track = ext.extrair(cfg)
    db.upsert(engine, "raw_spotify_chart", raw_chart)
    db.upsert(engine, "raw_spotify_track", raw_track)

    faixas = validar(transformar_faixas(raw_track, raw_chart), "spotify_faixa",
                     chaves=["track_id"], obrigatorias=["nome", "artista_principal"],
                     intervalos={"duracao_min": (0.5, 15)})
    chart = validar(transformar_chart(raw_chart), "spotify_chart",
                    chaves=["snapshot_date", "country", "track_id"],
                    obrigatorias=["position"],
                    intervalos={"position": (1, 50), "indice_popularidade": (0, 100)})
    n = db.upsert(engine, "spotify_faixa", faixas) + db.upsert(engine, "spotify_chart", chart)
    log.info("ETL1: %d faixas, %d posições de chart, duração média %.2f min, %.0f%% com feat.",
             len(faixas), len(chart), faixas["duracao_min"].mean(),
             100 * np.mean(faixas["tem_feat"]))
    return {"linhas": n}
