import logging

import pandas as pd

from src.etl2_youtube import alinhar_semana


def _videos(linhas):
    return pd.DataFrame(
        linhas, columns=["video_id", "country", "snapshot_date", "publicado_em", "views"]
    )


def test_mesma_semana_fica_a_coleta_mais_recente():
    # a coleta mais nova aparece primeiro de propósito, para pegar o bug antigo
    df = _videos([
        ("v1", "BR", "2026-10-30", "2026-10-01", 500),
        ("v1", "BR", "2026-10-27", "2026-10-01", 100),
    ])
    out = alinhar_semana(df, ["2026-10-29"])
    assert len(out) == 1
    assert out.iloc[0]["views"] == 500


def test_avisa_quando_coleta_esta_longe_do_csv(caplog):
    df = _videos([("v1", "BR", "2026-11-10", "2026-10-01", 100)])
    with caplog.at_level(logging.WARNING):
        alinhar_semana(df, ["2026-10-29"])
    assert "7 dias" in caplog.text