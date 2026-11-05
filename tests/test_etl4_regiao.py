
import pandas as pd
import pytest

from src.etl4_regiao import resumo_regioes, sobreposicao, jaccard


def dados_exemplo():
    chart = pd.DataFrame([
        {"snapshot_date": "2026-10-15", "country": "BR", "track_id": "A", "streams": 100},
        {"snapshot_date": "2026-10-15", "country": "BR", "track_id": "B", "streams": 200},
        {"snapshot_date": "2026-10-15", "country": "US", "track_id": "B", "streams": 300},
        {"snapshot_date": "2026-10-15", "country": "US", "track_id": "C", "streams": 400},
    ])

    faixas = pd.DataFrame([
        {"track_id": "A", "artista_principal": "Artista A", "genero_principal": "pop", "duracao_min": 3.0},
        {"track_id": "B", "artista_principal": "Artista B", "genero_principal": "rock", "duracao_min": 4.0},
        {"track_id": "C", "artista_principal": "Artista C", "genero_principal": "pop", "duracao_min": 5.0},
    ])

    videos = pd.DataFrame([
        {"snapshot_date": "2026-10-15", "country": "BR", "views": 1000, "taxa_engajamento": 10.0},
        {"snapshot_date": "2026-10-15", "country": "BR", "views": 3000, "taxa_engajamento": 20.0},
        {"snapshot_date": "2026-10-15", "country": "US", "views": 5000, "taxa_engajamento": 5.0},
    ])

    return chart, faixas, videos


def test_resumo_regioes_por_pais():
    chart, faixas, videos = dados_exemplo()
    resultado = resumo_regioes(chart, faixas, videos)

    assert len(resultado) == 2
    assert set(resultado["country"]) == {"BR", "US"}

    br = resultado.set_index("country").loc["BR"]
    us = resultado.set_index("country").loc["US"]

    assert br["n_faixas"] == 2
    assert br["pct_faixas_locais"] == 50.0
    assert br["streams_total"] == 300
    assert br["artista_top"] == "Artista B"
    assert br["duracao_media_min"] == 3.5
    assert br["n_videos_musica"] == 2
    assert br["engajamento_medio_yt"] == 15.0
    assert br["views_medianas_yt"] == 2000.0

    assert us["pct_faixas_locais"] == 50.0
    assert us["streams_total"] == 700
    assert us["artista_top"] == "Artista C"
    assert us["n_videos_musica"] == 1


def test_sobreposicao_entre_paises():
    chart, _, _ = dados_exemplo()
    resultado = sobreposicao(chart)

    assert len(resultado) == 1
    assert resultado.iloc[0]["pais_a"] == "BR"
    assert resultado.iloc[0]["pais_b"] == "US"
    assert resultado.iloc[0]["jaccard"] == pytest.approx(0.333, abs=0.001)


def test_jaccard_identico_e_sem_intersecao():
    assert jaccard({"A", "B"}, {"A", "B"}) == 1.0
    assert jaccard({"A"}, {"B"}) == 0.0
