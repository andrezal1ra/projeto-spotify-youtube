import json
from types import SimpleNamespace

import requests
from spotipy.exceptions import SpotifyException

import validar_spotify_real as ver
from src.config import Config


def test_pausa_429_preserva_e_retoma_sem_repetir_faixas(tmp_path, monkeypatch):
    pasta = tmp_path / 'work' / 'projeto'
    pasta.mkdir(parents=True)
    (tmp_path / 'outputs').mkdir()
    charts = pasta / 'charts'
    charts.mkdir()
    (charts / 'regional-br-weekly-2026-10-01.csv').write_text(
        'rank,uri,artist_names,track_name,streams\n1,spotify:track:a,A,A,20\n2,spotify:track:b,B,B,10\n', encoding='utf-8')
    monkeypatch.setattr(ver, '__file__', str(pasta / 'validar_spotify_real.py'))
    cfg = Config(modo='real', spotify_client_id='fake', spotify_client_secret='fake',
                 paises=['BR'], charts_dir=charts)
    monkeypatch.setattr(ver, 'Config', lambda **kwargs: cfg)
    chamadas = []
    bloquear = [True]

    def track(tid):
        chamadas.append(tid)
        if tid == 'b' and bloquear[0]:
            raise SpotifyException(429, -1, 'limit')
        return {'id': tid, 'name': tid, 'artists': [], 'album': {}, 'duration_ms': 200000}

    def iniciar(self, cfg):
        self.sp = SimpleNamespace(_session=requests.Session(), track=track)
        self._cache_artistas = {}
        self.limitador = SimpleNamespace(aguardar=lambda: None)

    monkeypatch.setattr(ver.ext.ClienteSpotify, '__init__', iniciar)
    ver.main()
    resumo = json.loads((tmp_path / 'outputs' / 'spotify_validacao_real.json').read_text(encoding='utf-8'))
    assert resumo['pausada_por_429'] is True
    assert resumo['faixas_recebidas_api'] == 1
    bloquear[0] = False
    ver.main()
    resumo = json.loads((tmp_path / 'outputs' / 'spotify_validacao_real.json').read_text(encoding='utf-8'))
    assert resumo['faixas_recebidas_api'] == 2
    assert chamadas == ['a', 'b', 'b']
