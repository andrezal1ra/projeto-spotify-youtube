"""Testes da extração do Spotify (modo real) sem internet: a API é substituída por um falso."""
import json

import pytest
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.exceptions import SpotifyException
from tenacity import wait_none

from src.config import Config
from src.etl1_spotify import transformar_faixas
from src.extract import spotify as ext
from src.extract.spotify import ClienteSpotify


class SpotifyFalso:
    """Imita spotipy.Spotify: devolve respostas prontas ou levanta erros na ordem dada."""

    def __init__(self, faixas=None, artistas=None):
        self.faixas = faixas or {}      # track_id -> dict ou lista de (erro | dict)
        self.artistas = artistas or {}  # artist_id -> dict ou exceção
        self.chamadas = {"track": 0, "artist": 0}

    def track(self, tid):
        self.chamadas["track"] += 1
        resp = self.faixas[tid]
        if isinstance(resp, list):      # sequência: um item por tentativa
            resp = resp.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def artist(self, aid):
        self.chamadas["artist"] += 1
        resp = self.artistas[aid]
        if isinstance(resp, Exception):
            raise resp
        return resp


def _faixa(tid, artistas):
    return {"id": tid, "name": f"Música {tid}", "duration_ms": 200000,
            "album": {"name": "Álbum", "release_date": "2026-01-01",
                      "release_date_precision": "day"},
            "artists": [{"id": a, "name": f"Artista {a}"} for a in artistas]}


def _erro(status):
    return SpotifyException(status, -1, f"erro {status}")


@pytest.fixture
def cliente(monkeypatch):
    # sem espera entre tentativas, para o teste não demorar
    monkeypatch.setattr(ClienteSpotify._chamar.retry, "wait", wait_none())
    cfg = Config()
    cfg.spotify_client_id, cfg.spotify_client_secret = "id-falso", "segredo-falso"
    cfg.intervalo_requisicoes = 0
    return ClienteSpotify(cfg)


def test_token_fica_so_na_memoria(cliente):
    # garante que o .cache com o access token não volta a ser criado no projeto
    assert isinstance(cliente.sp.auth_manager.cache_handler, MemoryCacheHandler)


def test_429_tenta_de_novo_e_recupera(cliente):
    cliente.sp = SpotifyFalso(
        faixas={"t1": [_erro(429), _erro(503), _faixa("t1", ["a1"])]},
        artistas={"a1": {"name": "Artista a1", "genres": ["funk"]}},
    )
    resp = cliente.faixa("t1")
    assert resp["track"]["id"] == "t1"
    assert cliente.sp.chamadas["track"] == 3


def test_429_persistente_desiste_depois_de_4_tentativas(cliente):
    cliente.sp = SpotifyFalso(faixas={"t1": [_erro(429)] * 10})
    with pytest.raises(SpotifyException):
        cliente.faixa("t1")
    assert cliente.sp.chamadas["track"] == 4


def test_faixa_nao_encontrada_nao_repete(cliente):
    # 404 não é transitório: tentar de novo só gastaria requisições
    cliente.sp = SpotifyFalso(faixas={"t1": _erro(404)})
    with pytest.raises(SpotifyException):
        cliente.faixa("t1")
    assert cliente.sp.chamadas["track"] == 1


def test_artista_sem_genero(cliente):
    cliente.sp = SpotifyFalso(faixas={"t1": _faixa("t1", ["a1"])},
                              artistas={"a1": {"name": "Artista a1", "genres": []}})
    detalhe = cliente.faixa("t1")["artists_detail"][0]
    assert detalhe["genres"] == []


def test_falha_no_artista_nao_derruba_a_faixa(cliente):
    cliente.sp = SpotifyFalso(faixas={"t1": _faixa("t1", ["a1"])},
                              artistas={"a1": _erro(404)})
    detalhe = cliente.faixa("t1")["artists_detail"][0]
    assert detalhe == {"id": "a1", "name": "Artista a1", "genres": []}


def test_artista_repetido_usa_cache(cliente):
    cliente.sp = SpotifyFalso(
        faixas={"t1": _faixa("t1", ["a1"]), "t2": _faixa("t2", ["a1", "a2"])},
        artistas={"a1": {"name": "A1", "genres": ["pop"]}, "a2": {"name": "A2", "genres": []}},
    )
    cliente.faixa("t1")
    cliente.faixa("t2")
    assert cliente.sp.chamadas["artist"] == 2   # a1 só é buscado uma vez


def test_extrair_real_segue_quando_uma_faixa_falha(tmp_path, monkeypatch):
    csv = ("rank,uri,artist_names,track_name,source,peak_rank,previous_rank,weeks_on_chart,streams\n"
           "1,spotify:track:ok,Ana,Canção Boa,L,1,1,3,2000\n"
           "2,spotify:track:sumiu,\"Bia, Caio\",Canção Sumida,L,2,2,1,1000\n")
    (tmp_path / "regional-br-weekly-2026-10-16.csv").write_text(csv, encoding="utf-8")

    class ClienteFalso:
        def __init__(self, cfg):
            pass

        def faixa(self, tid):
            if tid == "sumiu":
                raise _erro(404)
            return {"track": _faixa(tid, ["a1"]),
                    "artists_detail": [{"id": "a1", "name": "Ana", "genres": []}]}

    monkeypatch.setattr(ext, "ClienteSpotify", ClienteFalso)
    cfg = Config()
    cfg.modo, cfg.paises, cfg.charts_dir = "real", ["BR"], tmp_path

    raw_chart, raw_track = ext.extrair(cfg)
    assert len(raw_chart) == 2
    assert list(raw_track["track_id"]) == ["ok"]
    assert json.loads(raw_track.loc[0, "payload"])["track"]["id"] == "ok"

    # a faixa sem metadados ainda entra na camada tratada, com os dados do CSV
    faixas = transformar_faixas(raw_track, raw_chart).set_index("track_id")
    assert faixas.loc["sumiu", "nome"] == "Canção Sumida"
    assert faixas.loc["sumiu", "n_artistas"] == 2
