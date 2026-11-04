"""Coleta real do ETL 2 em banco isolado, usando somente os CSVs para alinhamento.

python -m src.verificar_youtube --banco work/youtube.db --relatorio work/youtube.json
As credenciais são lidas do ambiente/.env e nunca incluídas no relatório.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src import db, etl2_youtube
from src.config import Config
from src.etl1_spotify import transformar_chart
from src.extract.spotify import _para_raw_chart, ler_csvs_charts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", type=Path, required=True)
    parser.add_argument("--relatorio", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.banco.exists() or args.relatorio.exists():
        parser.error("use caminhos novos para preservar evidências anteriores")
    cfg = Config(modo="real")
    if not cfg.youtube_api_key or not cfg.paises:
        parser.error("configure YOUTUBE_API_KEY e pelo menos um país em PAISES")
    charts = ler_csvs_charts(cfg.charts_dir, cfg.paises)
    engine = db.criar_engine(f"sqlite:///{args.banco.resolve().as_posix()}")
    db.criar_esquema(engine)
    db.upsert(engine, "spotify_chart", transformar_chart(_para_raw_chart(charts)))
    relatorio = {"modo": "real", "inicio_utc": datetime.now(timezone.utc).isoformat(),
                 "paises_solicitados": cfg.paises,
                 "origem_alinhamento": "CSV Spotify Charts; sem enriquecimento Spotify nesta execução"}
    try:
        with db.auditar(engine, "etl2_youtube", info="modo=real; validação isolada da Louise") as estado:
            estado["linhas"] = etl2_youtube.executar(cfg, engine)["linhas"]
        raw = db.ler(engine, "SELECT * FROM raw_youtube_video")
        videos = db.ler(engine, "SELECT * FROM youtube_video")
        chaves = ["video_id", "country", "snapshot_date"]
        relatorio.update(status="ok", linhas_raw=len(raw), linhas_tratadas=len(videos),
                         excluidos_fora_categoria_musica=sum(
                             str(json.loads(p).get("snippet", {}).get("categoryId")) != "10"
                             for p in raw.payload),
                         duplicadas_raw=int(raw.duplicated(chaves).sum()),
                         duplicadas_tratadas=int(videos.duplicated(chaves).sum()),
                         ausentes={c: int(videos[c].isna().sum()) for c in
                                   ["titulo", "views", "likes", "comentarios", "duracao_s", "publicado_em"]},
                         inconsistencias={"views_negativas": int((videos.views < 0).sum()),
                                          "likes_negativos": int((videos.likes < 0).sum()),
                                          "comentarios_negativos": int((videos.comentarios < 0).sum()),
                                          "categoria_fora_musica": int((videos.category_id != "10").sum())},
                         paises=[])
        for pais, grupo in videos.groupby("country"):
            bruto = raw[raw.country == pais]
            datas = sorted(str(d) for d in grupo.snapshot_date.unique())
            coletas = sorted(str(d) for d in bruto.snapshot_date.unique())
            disponiveis = sorted(str(d) for d in charts.loc[charts.country == pais, "snapshot_date"].unique())
            relatorio["paises"].append({"country": pais, "videos": len(grupo),
                                        "datas_coleta_reais": coletas, "semanas_alinhadas": datas,
                                        "semanas_csv_disponiveis": disponiveis,
                                        "extracted_at_min": str(bruto.extracted_at.min()),
                                        "extracted_at_max": str(bruto.extracted_at.max())})
    except Exception as exc:
        # Não serializar HttpError: sua mensagem pode conter credenciais na URL.
        relatorio.update(status="erro", tipo_erro=type(exc).__name__)
    finally:
        relatorio["fim_utc"] = datetime.now(timezone.utc).isoformat()
        args.relatorio.parent.mkdir(parents=True, exist_ok=True)
        args.relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        engine.dispose()
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0 if relatorio["status"] == "ok" else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
