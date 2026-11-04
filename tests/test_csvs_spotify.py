"""Validação dos CSVs reais do Spotify Charts versionados no projeto."""

from datetime import date
from pathlib import Path
import re

import pandas as pd
import pytest


PASTA_CHARTS = Path(__file__).parents[1] / "data" / "charts"
PAISES = {"ar", "br", "es", "jp", "mx", "us"}
DATAS = {
    date(2026, 10, 1),
    date(2026, 10, 8),
    date(2026, 10, 15),
    date(2026, 10, 22),
    date(2026, 10, 29),
}
COLUNAS_OBRIGATORIAS = {
    "rank",
    "uri",
    "artist_names",
    "track_name",
    "streams",
    "weeks_on_chart",
}
PADRAO_NOME = re.compile(
    r"regional-(?P<pais>[a-z]{2})-weekly-(?P<data>\d{4}-\d{2}-\d{2})\.csv"
)


def _arquivos():
    return sorted(PASTA_CHARTS.glob("regional-*-weekly-*.csv"))


def test_existe_um_csv_para_cada_pais_e_semana_de_outubro():
    encontrados = set()
    for arquivo in _arquivos():
        correspondencia = PADRAO_NOME.fullmatch(arquivo.name)
        assert correspondencia, f"nome fora do padrão: {arquivo.name}"
        encontrados.add(
            (
                correspondencia.group("pais"),
                date.fromisoformat(correspondencia.group("data")),
            )
        )

    esperados = {(pais, data) for pais in PAISES for data in DATAS}
    assert encontrados == esperados


@pytest.mark.parametrize("arquivo", _arquivos(), ids=lambda p: p.name)
def test_csv_tem_estrutura_e_dados_validos(arquivo):
    dados = pd.read_csv(arquivo)

    assert COLUNAS_OBRIGATORIAS <= set(dados.columns)
    assert len(dados) == 200, "o Top Songs semanal deve conter 200 posições"
    assert not dados[list(COLUNAS_OBRIGATORIAS)].isna().any().any()

    ranks = pd.to_numeric(dados["rank"], errors="raise")
    streams = pd.to_numeric(dados["streams"], errors="raise")
    semanas = pd.to_numeric(dados["weeks_on_chart"], errors="raise")

    assert sorted(ranks.tolist()) == list(range(1, 201))
    assert dados["uri"].str.fullmatch(r"spotify:track:[A-Za-z0-9]+", na=False).all()
    assert dados["uri"].is_unique
    assert (streams >= 0).all()
    assert (semanas >= 1).all()
    assert dados["artist_names"].str.strip().ne("").all()
    assert dados["track_name"].str.strip().ne("").all()
