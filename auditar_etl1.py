"""Auditoria local dos Charts. Não faz nem simula enriquecimento pela API."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from src import db
from src.config import Config
from src.etl1_spotify import transformar_chart, transformar_faixas
from src.extract.spotify import ler_csvs_charts, _para_raw_chart


def main():
    out = Path(__file__).resolve().parents[2] / 'outputs'
    out.mkdir(exist_ok=True)
    cfg = Config(modo='real')
    arquivos = []
    for p in sorted(cfg.charts_dir.glob('*.csv')):
        d = pd.read_csv(p)
        problemas = []
        for campo in ['rank', 'uri', 'artist_names', 'track_name', 'streams', 'weeks_on_chart']:
            if campo not in d or d[campo].isna().any():
                problemas.append('ausente/nulo: ' + campo)
        if sorted(d['rank']) != list(range(1, 201)):
            problemas.append('ranking inválido')
        if not d.uri.is_unique:
            problemas.append('URI duplicada')
        if not d.uri.str.fullmatch(r'spotify:track:[A-Za-z0-9]{22}').all():
            problemas.append('URI inválida')
        if (d.streams < 0).any() or (d.weeks_on_chart < 1).any():
            problemas.append('valores inválidos')
        arquivos.append(dict(arquivo=p.name, linhas=len(d), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), problemas=problemas))
    raw = _para_raw_chart(ler_csvs_charts(cfg.charts_dir, cfg.paises))
    chart = transformar_chart(raw)
    faixas = transformar_faixas(pd.DataFrame(), raw)
    banco = out / 'spotify_charts_sem_enriquecimento.db'
    engine = db.criar_engine('sqlite:///' + banco.as_posix())
    db.criar_esquema(engine)
    for tabela, dados in [('raw_spotify_chart', raw), ('spotify_faixa', faixas), ('spotify_chart', chart)]:
        db.upsert(engine, tabela, dados)
        db.upsert(engine, tabela, dados)
        assert len(db.ler(engine, 'SELECT * FROM ' + tabela)) == len(dados)
    resumo = dict(
        modo='auditoria_csv_sem_api', enriquecimento_api_executado=False,
        arquivos=len(arquivos), linhas_arquivos=sum(a['linhas'] for a in arquivos),
        linhas_top50=len(raw), faixas_unicas=int(raw.track_id.nunique()),
        paises=sorted(raw.country.unique().tolist()),
        semanas=sorted(str(d) for d in raw.snapshot_date.unique()),
        duplicados_chave=int(raw.duplicated(['country','snapshot_date','track_id']).sum()),
        indice_min=float(chart.indice_popularidade.min()), indice_max=float(chart.indice_popularidade.max()),
        idempotencia_verificada=True,
        metadados_api='pendentes: artistas oficiais, gêneros, álbum, duração e lançamento',
        falhas_api=None, faixas_nao_encontradas_api=None,
        cobertura=raw.groupby(['country','snapshot_date']).size().rename('linhas').reset_index().astype(str).to_dict('records'),
        inventario=arquivos,
    )
    (out / 'auditoria_etl1.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in resumo.items() if k not in ['cobertura','inventario']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
