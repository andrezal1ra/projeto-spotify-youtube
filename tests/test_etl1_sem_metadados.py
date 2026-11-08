import pandas as pd

from src.etl1_spotify import transformar_faixas


def test_todas_as_faixas_sem_metadados_preservam_chart():
    chart = pd.DataFrame([
        {"track_id": "a", "track_name": "Canção", "artist_names": "Ana, Bia"},
        {"track_id": "a", "track_name": "Canção", "artist_names": "Ana, Bia"},
    ])
    resultado = transformar_faixas(pd.DataFrame(), chart)
    assert len(resultado) == 1
    assert resultado.iloc[0]["nome"] == "Canção"
    assert resultado.iloc[0]["n_artistas"] == 2
    assert resultado[["duracao_ms", "duracao_min", "album", "generos",
                      "data_lancamento"]].isna().all().all()
