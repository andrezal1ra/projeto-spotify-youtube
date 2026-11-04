"""EXTRACT - YouTube Data API v3.

Usa videos.list(chart='mostPopular', regionCode=<país>, videoCategoryId='10'):
os vídeos de MÚSICA em alta em cada país. Custo: 1 unidade de cota por chamada
(a cota padrão é 10.000 unidades/dia). Evitamos search.list, que custa 100.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime

import pandas as pd
from tenacity import (retry, retry_if_exception, stop_after_attempt,
                      wait_exponential)

from src.config import Config
from src.mock_data import Simulador
from src.utils import LimitadorRequisicoes

log = logging.getLogger("extract.youtube")


class CotaEsgotada(RuntimeError):
    """A cota diária da API acabou: não adianta tentar de novo hoje."""


def _transitorio(exc: Exception) -> bool:
    resp = getattr(exc, "resp", None)
    return getattr(resp, "status", None) in (500, 502, 503, 504)


class ClienteYouTube:
    def __init__(self, cfg: Config):
        from googleapiclient.discovery import build

        self.yt = build("youtube", "v3", developerKey=cfg.youtube_api_key, cache_discovery=False)
        self.limitador = LimitadorRequisicoes(cfg.intervalo_requisicoes)
        self.unidades_gastas = 0

    @retry(retry=retry_if_exception(_transitorio), stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=1, max=30), reraise=True)
    def _executar(self, requisicao):
        from googleapiclient.errors import HttpError

        self.limitador.aguardar()
        try:
            resp = requisicao.execute()
        except HttpError as exc:
            if exc.resp.status == 403 and b"quotaExceeded" in (exc.content or b""):
                raise CotaEsgotada("Cota diária do YouTube esgotada") from exc
            raise
        self.unidades_gastas += 1
        return resp

    def em_alta(self, pais: str, maximo: int = 50) -> list[dict]:
        itens = []
        req = self.yt.videos().list(
            part="snippet,statistics,contentDetails", chart="mostPopular",
            regionCode=pais, videoCategoryId="10", maxResults=min(50, maximo),
        )
        while req is not None and len(itens) < maximo:
            resp = self._executar(req)
            itens.extend(resp.get("items", []))
            req = self.yt.videos().list_next(req, resp)
        return itens[:maximo]

    def categorias(self, pais: str) -> list[dict]:
        resp = self._executar(self.yt.videoCategories().list(part="snippet", regionCode=pais))
        return resp.get("items", [])


def extrair(cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (raw_youtube_video, raw_youtube_categoria)."""
    agora = datetime.now()
    linhas, categorias = [], {}

    if cfg.modo == "simulado":
        sim = Simulador(cfg.paises)
        for c in sim.categorias():
            categorias[c["id"]] = c["snippet"]["title"]
        for pais in sim.paises:
            for dia in sim.datas:   # simula 4 coletas semanais
                for pos, item in enumerate(sim.videos_em_alta(pais, dia), start=1):
                    item["_posicao"] = pos
                    linhas.append({"video_id": item["id"], "country": pais, "snapshot_date": dia,
                                   "payload": json.dumps(item, ensure_ascii=False),
                                   "extracted_at": agora})
    else:
        cli = ClienteYouTube(cfg)
        hoje = date.today()   # a API só dá o "agora": a série histórica vem de rodar toda semana
        try:
            lista_categorias = cli.categorias(cfg.paises[0])
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", "n/a")
            raise RuntimeError(f"Falha nas categorias do YouTube: {type(exc).__name__}, HTTP {status}") from None
        for c in lista_categorias:
            categorias[c["id"]] = c["snippet"]["title"]
        for pais in cfg.paises:
            try:
                itens = cli.em_alta(pais)
            except CotaEsgotada:
                log.error("Cota esgotada ao chegar em %s; salvando o que já foi coletado", pais)
                break
            except Exception as exc:
                # HttpError pode incluir a URL com a API key: nunca registrar str(exc).
                log.error("Falha ao extrair %s: %s, HTTP %s (seguindo com os outros países)",
                          pais, type(exc).__name__, getattr(getattr(exc, "resp", None), "status", "n/a"))
                continue
            for pos, item in enumerate(itens, start=1):
                item["_posicao"] = pos
                linhas.append({"video_id": item["id"], "country": pais, "snapshot_date": hoje,
                               "payload": json.dumps(item, ensure_ascii=False),
                               "extracted_at": agora})
            log.info("YouTube %s: %d vídeos", pais, len(itens))
        log.info("Cota usada nesta execução: %d unidades", cli.unidades_gastas)

    df_cat = pd.DataFrame([{"category_id": k, "nome": v} for k, v in categorias.items()])
    return pd.DataFrame(linhas), df_cat
