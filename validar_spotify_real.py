"""Executa somente o ETL 1 e registra cobertura e erros sem credenciais."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from requests.adapters import HTTPAdapter

from src import db, etl1_spotify
from src.config import Config
from src.extract import spotify as ext


def main():
    cfg = Config(modo='real')
    cfg.validar(etapas=[1])
    out = Path(__file__).resolve().parents[2] / 'outputs'
    banco = out / 'spotify_andreza_real.db'
    engine = db.criar_engine('sqlite:///' + banco.as_posix())
    db.criar_esquema(engine)
    arquivo_eventos = out / 'spotify_eventos_api.json'
    eventos = json.loads(arquivo_eventos.read_text(encoding='utf-8')) if arquivo_eventos.exists() else []
    arquivo_artistas = out / 'spotify_cache_artistas.json'
    cache_artistas = json.loads(arquivo_artistas.read_text(encoding='utf-8')) if arquivo_artistas.exists() else {}

    class ClienteComCheckpoint(ext.ClienteSpotify):
        def __init__(self, cfg):
            super().__init__(cfg)
            self._cache_artistas.update(cache_artistas)
            # Não bloquear um processo por horas dentro do Retry-After do Spotipy.
            self.sp._session.mount('https://', HTTPAdapter(max_retries=0))

        def faixa(self, tid):
            resultado = super().faixa(tid)
            db.upsert(engine, 'raw_spotify_track', pd.DataFrame([{
                'track_id': tid, 'payload': json.dumps(resultado, ensure_ascii=False),
                'extracted_at': datetime.now(),
            }]))
            arquivo_artistas.write_text(json.dumps(self._cache_artistas, ensure_ascii=False), encoding='utf-8')
            return resultado

    def chamar(self, func, *args):
        try:
            self.limitador.aguardar()
            resultado = func(*args)
            eventos.append({'endpoint': func.__name__, 'id': args[0], 'status': 'ok'})
            return resultado
        except Exception as exc:
            eventos.append({'endpoint': func.__name__, 'id': args[0], 'status': 'erro',
                            'http_status': getattr(exc, 'http_status', None),
                            'tipo': type(exc).__name__})
            if getattr(exc, 'http_status', None) == 429:
                # BaseException evita que o fallback de artista engula a pausa.
                raise PausarColeta() from None
            raise
        finally:
            (out / 'spotify_eventos_api.json').write_text(
                json.dumps(eventos, ensure_ascii=False, indent=2), encoding='utf-8')
            if len(eventos) % 50 == 0:
                print('Consultas concluídas:', len(eventos), flush=True)

    class PausarColeta(BaseException):
        pass

    ClienteComCheckpoint._chamar = chamar
    logging.basicConfig(level=logging.CRITICAL)
    raw_chart = ext._para_raw_chart(ext.ler_csvs_charts(cfg.charts_dir, cfg.paises))
    db.upsert(engine, 'raw_spotify_chart', raw_chart)
    salvos = set(db.ler(engine, 'SELECT track_id FROM raw_spotify_track').track_id)
    cliente = ClienteComCheckpoint(cfg)
    pausada = False
    for tid in sorted(set(raw_chart.track_id) - salvos):
        try:
            cliente.faixa(tid)
        except PausarColeta:
            pausada = True
            arquivo_artistas.write_text(json.dumps(cliente._cache_artistas, ensure_ascii=False), encoding='utf-8')
            print('Coleta pausada por HTTP 429. Respostas completas já salvas serão reutilizadas.', flush=True)
            break
        except Exception:
            continue
    raw_track = db.ler(engine, 'SELECT * FROM raw_spotify_track')
    db.upsert(engine, 'spotify_faixa', etl1_spotify.transformar_faixas(raw_track, raw_chart))
    db.upsert(engine, 'spotify_chart', etl1_spotify.transformar_chart(raw_chart))
    faixas = db.ler(engine, 'SELECT * FROM spotify_faixa')
    raw = db.ler(engine, 'SELECT * FROM raw_spotify_track')
    charts = db.ler(engine, 'SELECT * FROM spotify_chart')
    esperados = set(charts.track_id)
    recebidos = set(raw.track_id)
    divergencias = []
    raw_charts = db.ler(engine, 'SELECT * FROM raw_spotify_chart')
    for _, r in raw.iterrows():
        t = json.loads(r.payload)['track']
        nomes = raw_charts.loc[raw_charts.track_id == r.track_id, 'track_name'].unique().tolist()
        if t.get('name') not in nomes or t.get('id') != r.track_id:
            divergencias.append({'track_id': r.track_id, 'id_retornado': t.get('id'),
                                 'nomes_csv': nomes, 'nome_api': t.get('name')})
    falhas = [e for e in eventos if e['status'] == 'erro']
    resumo = {
        'data_utc': datetime.now(timezone.utc).isoformat(), 'modo': 'real', 'pausada_por_429': pausada,
        'faixas_esperadas': len(esperados), 'faixas_recebidas_api': len(recebidos),
        'linhas_chart': len(charts), 'faixas_sem_resposta': sorted(esperados - recebidos),
        'chamadas_logicas': len(eventos), 'falhas_apos_retentativas': falhas,
        'observacao_retentativas': 'Eventos representam chamadas lógicas após retries; não cada tentativa HTTP.',
        'campos_preenchidos': {c: int(faixas[c].notna().sum()) for c in [
            'nome', 'artista_principal', 'artistas', 'album', 'duracao_ms',
            'data_lancamento', 'generos', 'genero_principal']},
        'duracao_min_minima': float(faixas.duracao_min.min()),
        'duracao_min_maxima': float(faixas.duracao_min.max()),
        'duracoes_fora_05_a_15_min': int(((faixas.duracao_min < .5) | (faixas.duracao_min > 15)).sum()),
        'divergencias_nome_ou_id': divergencias,
        'duplicados_chart': int(charts.duplicated(['country', 'snapshot_date', 'track_id']).sum()),
        'duplicados_faixa': int(faixas.duplicated(['track_id']).sum()),
    }
    (out / 'spotify_validacao_real.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resumo, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
