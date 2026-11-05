"""Orquestrador do pipeline ETL.

Uso:
    python -m src.pipeline                 # roda ETL 1 a 4 no MODO do .env
    python -m src.pipeline --modo simulado # força dados simulados
    python -m src.pipeline --etapas 3 4    # roda só algumas etapas

O ETL 5 (visualização) é o dashboard: streamlit run dashboard/app.py
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from src import db, etl1_spotify, etl2_youtube, etl3_correlacao, etl4_regiao
from src.config import Config, configurar_logging

ETAPAS = {
    1: ("etl1_spotify", etl1_spotify.executar),
    2: ("etl2_youtube", etl2_youtube.executar),
    3: ("etl3_correlacao", etl3_correlacao.executar),
    4: ("etl4_regiao", etl4_regiao.executar),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline ETL Spotify + YouTube")
    parser.add_argument("--modo", choices=["simulado", "real"])
    parser.add_argument("--etapas", type=int, nargs="+", default=[1, 2, 3, 4],
                        choices=list(ETAPAS))
    args = parser.parse_args(argv)

    configurar_logging()
    log = logging.getLogger("pipeline")
    cfg = Config()
    if args.modo:
        cfg.modo = args.modo
    cfg.validar(etapas=args.etapas)
    log.info("Iniciando pipeline | modo=%s | países=%s | banco=%s", cfg.modo,
             ",".join(cfg.paises), cfg.database_url.split("@")[-1])

    engine = db.criar_engine(cfg.database_url)
    db.criar_esquema(engine)

    inicio = time.time()
    for n in sorted(args.etapas):
        nome, funcao = ETAPAS[n]
        log.info("===== ETL %d: %s =====", n, nome)
        try:
            with db.auditar(engine, nome, info=f"modo={cfg.modo}") as estado:
                estado["linhas"] = funcao(cfg, engine)["linhas"]
        except Exception:
            log.error("Pipeline interrompido no ETL %d (detalhes no log acima)", n)
            return 1
    log.info("Pipeline concluído em %.1f s", time.time() - inicio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
