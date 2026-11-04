"""Testes da extração e do alinhamento do YouTube sem internet."""
from datetime import date

import pandas as pd
import pytest

from src.config import Config
from src.extract import youtube as ext
from src.extract.youtube import CotaEsgotada
from src.etl2_youtube import alinhar_semana


def _item(video_id: str) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": f"Vídeo {video_id}",
            "channelTitle": "Canal",
            "categoryId": "10",
            "publishedAt": "2026-10-01T00:00:00Z",
        },
        "contentDetails": {"duration": "PT3M"},
        "statistics": {"viewCount": "1000", "likeCount": "50", "commentCount": "10"},
    }


def test_extrair_real_continua_quando_um_pais_falha(monkeypatch):
    class ClienteFalso:
        def __init__(self, cfg):
            self.unidades_gastas = 0

        def categorias(self, pais):
            return [{"id": "10", "snippet": {"title": "Music"}}]

        def em_alta(self, pais):
            if pais == "US":
                raise RuntimeError("falha temporária")
            return [_item(f"{pais.lower()}-1")]

    monkeypatch.setattr(ext, "ClienteYouTube", ClienteFalso)
    cfg = Config()
    cfg.modo, cfg.paises = "real", ["BR", "US", "MX"]

    raw, categorias = ext.extrair(cfg)

    assert list(raw["country"]) == ["BR", "MX"]
    assert list(raw["video_id"]) == ["br-1", "mx-1"]
    assert list(categorias["category_id"]) == ["10"]


def test_extrair_real_para_nos_paises_apos_cota(monkeypatch):
    chamadas = []

    class ClienteFalso:
        def __init__(self, cfg):
            self.unidades_gastas = 0

        def categorias(self, pais):
            return []

        def em_alta(self, pais):
            chamadas.append(pais)
            if pais == "US":
                raise CotaEsgotada("cota")
            return [_item(f"{pais.lower()}-1")]

    monkeypatch.setattr(ext, "ClienteYouTube", ClienteFalso)
    cfg = Config()
    cfg.modo, cfg.paises = "real", ["BR", "US", "MX"]

    raw, _ = ext.extrair(cfg)

    assert chamadas == ["BR", "US"]
    assert set(raw["country"]) == {"BR"}


def test_alinhar_semana_mantem_a_coleta_mais_recente(caplog):
    videos = pd.DataFrame([
        {"video_id": "v1", "country": "BR", "snapshot_date": date(2026, 10, 20),
         "publicado_em": pd.Timestamp("2026-10-30")},
        {"video_id": "v1", "country": "BR", "snapshot_date": date(2026, 10, 21),
         "publicado_em": pd.Timestamp("2026-10-01")},
    ])

    alinhados = alinhar_semana(videos, [date(2026, 10, 22)])

    assert len(alinhados) == 1
    assert alinhados.iloc[0]["snapshot_date"] == date(2026, 10, 22)
    assert alinhados.iloc[0]["publicado_em"] == pd.Timestamp("2026-10-01")
    assert "Coleta do YouTube" not in caplog.text


def test_alinhar_semana_avisa_distancia_maior_que_sete_dias(caplog):
    videos = pd.DataFrame([
        {"video_id": "v1", "country": "BR", "snapshot_date": date(2026, 11, 20),
         "publicado_em": pd.Timestamp("2026-10-01")},
    ])

    with caplog.at_level("WARNING", logger="etl2"):
        alinhados = alinhar_semana(videos, [date(2026, 10, 29)])

    assert len(alinhados) == 1
    assert "22 dias" in caplog.text
    assert "2026-11-20" in caplog.text
