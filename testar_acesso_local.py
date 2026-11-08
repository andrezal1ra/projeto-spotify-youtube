import logging
logging.disable(logging.CRITICAL)
from src.config import Config
from src.extract.spotify import ClienteSpotify, ler_csvs_charts

c = Config(modo='real')
tid = ler_csvs_charts(c.charts_dir, c.paises).uri.iloc[0].split(':')[-1]
try:
    p = ClienteSpotify(c).faixa(tid)
    print('API OK; faixa recebida:', bool(p.get('track', {}).get('id')))
except Exception as e:
    print('Falha de acesso:', type(e).__name__, 'HTTP:', getattr(e, 'http_status', None))
    raise SystemExit(1)
