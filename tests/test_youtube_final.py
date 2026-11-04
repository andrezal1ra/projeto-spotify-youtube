"""Regressões do ETL 2: qualidade, cobertura e alinhamento por país."""
import json

import pandas as pd
import pytest
from sqlalchemy import create_engine

from src import db, etl2_youtube as etl
from src.config import Config
from src.qualidade import ErroQualidade


def _raw(**snippet):
    item = {"snippet": {"title": "Artista - Música", "publishedAt": "2026-10-01T00:00:00Z",
                        "categoryId": "10", **snippet},
            "statistics": {"viewCount": "1000"}, "contentDetails": {"duration": "PT3M"}}
    return pd.DataFrame([{"video_id": "v1", "country": "BR", "snapshot_date": "2026-11-04",
                          "payload": json.dumps(item), "extracted_at": "2026-11-04 12:00:00"}])


def test_coleta_vazia_tem_erro_de_qualidade():
    with pytest.raises(ErroQualidade, match="coleta vazia"):
        etl.transformar_videos(pd.DataFrame(), pd.DataFrame())


def test_duplicacao_raw_nao_desaparece_no_alinhamento():
    with pytest.raises(ErroQualidade, match="duplicadas"):
        etl.transformar_videos(pd.concat([_raw(), _raw()]), pd.DataFrame())


def test_titulo_em_branco_e_ausente():
    out = etl.transformar_videos(_raw(title="  "), pd.DataFrame())
    assert pd.isna(out.iloc[0].titulo)


def test_contagens_ocultas_nao_viram_engajamento_zero():
    out = etl.transformar_videos(_raw(), pd.DataFrame()).iloc[0]
    assert pd.isna(out.likes) and pd.isna(out.comentarios)
    assert pd.isna(out.taxa_engajamento)


def test_alinhamento_usa_somente_charts_do_mesmo_pais():
    raw = pd.concat([_raw(), _raw().assign(country="US")], ignore_index=True)
    videos = etl.transformar_videos(raw, pd.DataFrame())
    charts = pd.DataFrame({"country": ["BR", "US"],
                           "snapshot_date": ["2026-10-29", "2026-11-03"]})
    out = etl.alinhar_semana(videos, charts).set_index("country")
    assert str(out.loc["BR", "snapshot_date"]) == "2026-10-29"
    assert str(out.loc["US", "snapshot_date"]) == "2026-11-03"
    assert out.loc["BR", "views_por_dia"] == videos.iloc[0].views_por_dia
    assert str(raw.iloc[0].snapshot_date) == "2026-11-04"


def test_pais_sem_chart_nao_recebe_semana_de_outro_pais():
    with pytest.raises(ErroQualidade, match="BR"):
        etl.alinhar_semana(_raw(), pd.DataFrame({"country": ["US"],
                                               "snapshot_date": ["2026-10-29"]}))


def test_coleta_parcial_preserva_raw_e_nao_publica_tratada(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    db.criar_esquema(engine)
    monkeypatch.setattr(etl.ext, "extrair", lambda cfg: (_raw(), pd.DataFrame()))
    with pytest.raises(ErroQualidade, match="US"):
        etl.executar(Config(modo="real", paises=["BR", "US"]), engine)
    assert len(db.ler(engine, "SELECT * FROM raw_youtube_video")) == 1
    assert db.ler(engine, "SELECT * FROM youtube_video").empty


def test_duracao_negativa_nao_e_valida():
    assert etl.duracao_segundos("-PT3M") is None


def test_api_retornando_outra_categoria_fica_so_na_raw(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    db.criar_esquema(engine)
    raw = pd.concat([_raw(), _raw(categoryId="23").assign(video_id="v2")], ignore_index=True)
    monkeypatch.setattr(etl.ext, "extrair", lambda cfg: (raw, pd.DataFrame()))
    assert etl.executar(Config(modo="simulado"), engine)["linhas"] == 1
    assert len(db.ler(engine, "SELECT * FROM raw_youtube_video")) == 2
    assert list(db.ler(engine, "SELECT video_id FROM youtube_video").video_id) == ["v1"]


def test_falha_http_nao_expoe_chave_em_log(monkeypatch, caplog):
    from src.extract import youtube as ext

    class Cliente:
        unidades_gastas = 0

        def categorias(self, pais):
            return []

        def em_alta(self, pais):
            raise RuntimeError("https://youtube.googleapis.com/?key=SEGREDO_TESTE")

    monkeypatch.setattr(ext, "ClienteYouTube", lambda cfg: Cliente())
    ext.extrair(Config(modo="real", paises=["BR"]))
    assert "SEGREDO_TESTE" not in caplog.text
    assert "RuntimeError" in caplog.text
