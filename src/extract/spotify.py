"""EXTRACT - Spotify.

Fontes (decisão técnica, ver docs/decisoes_tecnicas.md):
  1. Spotify Charts (charts.spotify.com): CSVs do Top 50 semanal por país.
     Substituem o campo `popularity` e as playlists editoriais, que a Web API
     deixou de oferecer para apps em Development Mode (nov/2024 e fev/2026).
  2. Spotify Web API via Spotipy (Client Credentials): metadados de cada faixa
     (duração, álbum, data de lançamento, artistas) e gêneros dos artistas.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from tenacity import (retry, retry_if_exception, stop_after_attempt,
                      wait_exponential)

from src.config import Config
from src.mock_data import Simulador
from src.utils import LimitadorRequisicoes

log = logging.getLogger("extract.spotify")

# regional-br-weekly-2026-10-16.csv  /  regional-br-weekly-2026-10-16 (1).csv
PADRAO_ARQUIVO = re.compile(r"regional-([a-z]{2})-weekly-(\d{4}-\d{2}-\d{2})", re.I)


# ---------------------------------------------------------------- charts (CSV)
def ler_csvs_charts(pasta: Path, paises: list[str]) -> pd.DataFrame:
    arquivos = sorted(pasta.glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum CSV em {pasta}. Baixe o Top 50 semanal de cada país em "
            "https://charts.spotify.com (login gratuito) e salve nesta pasta."
        )
    frames = []
    for arq in arquivos:
        m = PADRAO_ARQUIVO.search(arq.name)
        if not m:
            log.warning("Ignorando %s (nome fora do padrão regional-xx-weekly-AAAA-MM-DD)", arq.name)
            continue
        pais, dia = m.group(1).upper(), date.fromisoformat(m.group(2))
        if pais not in paises:
            continue
        df = pd.read_csv(arq)
        faltando = {"rank", "uri", "artist_names", "track_name", "streams"} - set(df.columns)
        if faltando:
            log.error("%s sem colunas %s - arquivo ignorado", arq.name, faltando)
            continue
        df["country"], df["snapshot_date"] = pais, dia
        if "weeks_on_chart" not in df.columns:
            df["weeks_on_chart"] = None
        frames.append(df.head(50))
        log.info("Chart lido: %s %s (%d linhas)", pais, dia, min(len(df), 50))
    if not frames:
        raise ValueError("Nenhum CSV válido para os países configurados")
    return pd.concat(frames, ignore_index=True)


def _para_raw_chart(df: pd.DataFrame) -> pd.DataFrame:
    agora = datetime.now()
    return pd.DataFrame({
        "snapshot_date": df["snapshot_date"],
        "country": df["country"],
        "position": df["rank"].astype(int),
        "track_id": df["uri"].str.split(":").str[-1],
        "track_name": df["track_name"],
        "artist_names": df["artist_names"],
        "streams": pd.to_numeric(df["streams"], errors="coerce"),
        "weeks_on_chart": pd.to_numeric(df["weeks_on_chart"], errors="coerce"),
        "extracted_at": agora,
    })


# ---------------------------------------------------------------- Web API
def _erro_transitorio(exc: Exception) -> bool:
    status = getattr(exc, "http_status", None)
    return status in (429, 500, 502, 503, 504) or isinstance(exc, (ConnectionError, TimeoutError))


class ClienteSpotify:
    def __init__(self, cfg: Config):
        import spotipy
        from spotipy.cache_handler import MemoryCacheHandler
        from spotipy.oauth2 import SpotifyClientCredentials

        self.sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=cfg.spotify_client_id, client_secret=cfg.spotify_client_secret,
                # token só na memória: sem isso o Spotipy grava um arquivo .cache com o
                # access token na raiz do projeto, e ele acaba indo parar no Git
                cache_handler=MemoryCacheHandler(),
            ),
            retries=3, status_retries=3, backoff_factor=0.5,  # respeita Retry-After do 429
            requests_timeout=15,
        )
        self.limitador = LimitadorRequisicoes(cfg.intervalo_requisicoes)
        self._cache_artistas: dict[str, dict] = {}

    @retry(retry=retry_if_exception(_erro_transitorio), stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=1, max=30), reraise=True)
    def _chamar(self, func, *args):
        self.limitador.aguardar()
        return func(*args)

    def faixa(self, track_id: str) -> dict:
        # Endpoints em lote (/tracks?ids=, /artists?ids=) foram removidos em fev/2026:
        # uma requisição por faixa, com cache de artistas para economizar chamadas.
        track = self._chamar(self.sp.track, track_id)
        detalhes = []
        for art in track.get("artists", []):
            aid = art["id"]
            if aid not in self._cache_artistas:
                try:
                    a = self._chamar(self.sp.artist, aid)
                    self._cache_artistas[aid] = {"id": aid, "name": a.get("name"),
                                                 "genres": a.get("genres") or []}
                except Exception as exc:  # gênero é opcional; não derruba a extração
                    log.warning("Sem detalhes do artista %s: %s", aid, exc)
                    self._cache_artistas[aid] = {"id": aid, "name": art.get("name"), "genres": []}
            detalhes.append(self._cache_artistas[aid])
        return {"track": track, "artists_detail": detalhes}


# ---------------------------------------------------------------- orquestração
def extrair(cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (raw_spotify_chart, raw_spotify_track)."""
    agora = datetime.now()
    if cfg.modo == "simulado":
        sim = Simulador(cfg.paises)
        charts = pd.DataFrame(sim.charts())
        raw_chart = _para_raw_chart(charts)
        obter = sim.track_payload
    else:
        charts = ler_csvs_charts(cfg.charts_dir, cfg.paises)
        raw_chart = _para_raw_chart(charts)
        obter = ClienteSpotify(cfg).faixa

    ids = sorted(raw_chart["track_id"].unique())
    log.info("Buscando metadados de %d faixas únicas", len(ids))
    registros, falhas = [], 0
    for i, tid in enumerate(ids, start=1):
        try:
            registros.append({"track_id": tid, "payload": json.dumps(obter(tid), ensure_ascii=False),
                              "extracted_at": agora})
        except Exception as exc:
            falhas += 1
            log.error("Falha ao buscar faixa %s: %s", tid, exc)
        if i % 50 == 0:
            log.info("  %d/%d faixas", i, len(ids))
    if falhas:
        log.warning("%d faixas sem metadados (seguem só com dados do chart)", falhas)
    return raw_chart, pd.DataFrame(registros)
