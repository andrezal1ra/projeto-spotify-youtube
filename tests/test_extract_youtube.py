"""Testes da extração do YouTube (modo real) sem internet: a API é substituída por um falso."""
import json
from datetime import date

import httplib2
import pytest
from googleapiclient.errors import HttpError
from tenacity import wait_none

from src.config import Config
from src.extract import youtube as ext
from src.extract.youtube import ClienteYouTube, CotaEsgotada, _transitorio

COTA = b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}'


def _http_erro(status, conteudo=b""):
    return HttpError(httplib2.Response({"status": status}), conteudo)


def _video(vid):
    return {"id": vid, "snippet": {"title": f"Vídeo {vid}"}}


class RequisicaoFalsa:
    """Imita o objeto de requisição da API: devolve respostas ou levanta erros na ordem dada."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = 0

    def execute(self):
        self.chamadas += 1
        resp = self.respostas.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


class _Pedido:
    def __init__(self, paginas, indice):
        self.paginas, self.indice = paginas, indice

    def execute(self):
        return self.paginas[self.indice]


class YouTubeFalso:
    """Imita yt.videos().list(...) e list_next(...), com várias páginas de resultado."""

    def __init__(self, paginas):
        self.paginas = paginas
        self.parametros = None

    def videos(self):
        return self

    def list(self, **kwargs):
        self.parametros = kwargs
        return _Pedido(self.paginas, 0)

    def list_next(self, pedido, resp):
        prox = pedido.indice + 1
        return _Pedido(self.paginas, prox) if prox < len(self.paginas) else None


@pytest.fixture
def cliente(monkeypatch):
    # sem espera entre tentativas, para o teste não demorar
    monkeypatch.setattr(ClienteYouTube._executar.retry, "wait", wait_none())
    # evita montar o cliente real do Google
    import googleapiclient.discovery as discovery
    monkeypatch.setattr(discovery, "build", lambda *a, **k: object())
    cfg = Config()
    cfg.youtube_api_key = "chave-falsa"
    cfg.intervalo_requisicoes = 0
    return ClienteYouTube(cfg)


# ---------- _transitorio ----------

@pytest.mark.parametrize("status,esperado", [(500, True), (503, True), (404, False), (403, False)])
def test_transitorio_so_para_erros_5xx(status, esperado):
    assert _transitorio(_http_erro(status)) is esperado


def test_transitorio_ignora_erro_sem_resposta_http():
    assert _transitorio(ValueError("qualquer coisa")) is False


# ---------- _executar: retry, cota e contagem ----------

def test_503_tenta_de_novo_e_recupera(cliente):
    req = RequisicaoFalsa([_http_erro(503), _http_erro(503), {"items": []}])
    assert cliente._executar(req) == {"items": []}
    assert req.chamadas == 3
    assert cliente.unidades_gastas == 1   # só a chamada que deu certo gasta cota


def test_503_persistente_desiste_depois_de_4_tentativas(cliente):
    req = RequisicaoFalsa([_http_erro(503)] * 10)
    with pytest.raises(HttpError):
        cliente._executar(req)
    assert req.chamadas == 4
    assert cliente.unidades_gastas == 0


def test_erro_nao_transitorio_nao_repete(cliente):
    # 404 não adianta tentar de novo: só gastaria requisições
    req = RequisicaoFalsa([_http_erro(404)])
    with pytest.raises(HttpError):
        cliente._executar(req)
    assert req.chamadas == 1


def test_cota_esgotada_levanta_erro_proprio_e_nao_repete(cliente):
    req = RequisicaoFalsa([_http_erro(403, COTA)])
    with pytest.raises(CotaEsgotada):
        cliente._executar(req)
    assert req.chamadas == 1


def test_403_que_nao_e_cota_continua_sendo_http_error(cliente):
    req = RequisicaoFalsa([_http_erro(403, b'{"error": {"errors": [{"reason": "forbidden"}]}}')])
    with pytest.raises(HttpError):
        cliente._executar(req)
    assert req.chamadas == 1


# ---------- em_alta ----------

def test_em_alta_pede_musica_do_pais_e_junta_paginas(cliente):
    cliente.yt = YouTubeFalso([{"items": [_video("a"), _video("b")]},
                               {"items": [_video("c")]}])
    itens = cliente.em_alta("BR")
    assert [i["id"] for i in itens] == ["a", "b", "c"]
    p = cliente.yt.parametros
    assert p["chart"] == "mostPopular"
    assert p["regionCode"] == "BR"
    assert p["videoCategoryId"] == "10"
    assert cliente.unidades_gastas == 2   # uma unidade por página


def test_em_alta_respeita_o_maximo(cliente):
    cliente.yt = YouTubeFalso([{"items": [_video(str(i)) for i in range(3)]},
                               {"items": [_video(str(i)) for i in range(3, 6)]}])
    itens = cliente.em_alta("BR", maximo=5)
    assert len(itens) == 5
    assert cliente.yt.parametros["maxResults"] == 5


# ---------- extrair (modo real) ----------

class ClienteFalso:
    unidades_gastas = 0

    def __init__(self, por_pais):
        self.por_pais = por_pais   # país -> lista de vídeos ou exceção

    def categorias(self, pais):
        return [{"id": "10", "snippet": {"title": "Music"}}]

    def em_alta(self, pais, maximo=50):
        resp = self.por_pais[pais]
        if isinstance(resp, Exception):
            raise resp
        return [dict(v) for v in resp]   # cópia, porque extrair() altera o item


def _cfg(paises):
    cfg = Config()
    cfg.modo, cfg.paises = "real", paises
    return cfg


def _usar(monkeypatch, por_pais):
    monkeypatch.setattr(ext, "ClienteYouTube", lambda cfg: ClienteFalso(por_pais))


def test_extrair_real_gera_uma_linha_por_video_com_a_data_de_hoje(monkeypatch):
    _usar(monkeypatch, {"BR": [_video("a"), _video("b")], "US": [_video("c")]})
    raw_video, raw_cat = ext.extrair(_cfg(["BR", "US"]))

    assert len(raw_video) == 3
    assert set(raw_video["country"]) == {"BR", "US"}
    assert (raw_video["snapshot_date"] == date.today()).all()
    posicoes_br = [json.loads(p)["_posicao"] for p in raw_video[raw_video.country == "BR"]["payload"]]
    assert posicoes_br == [1, 2]
    assert list(raw_cat["nome"]) == ["Music"]


def test_extrair_real_segue_quando_um_pais_falha(monkeypatch):
    _usar(monkeypatch, {"BR": RuntimeError("falhou"), "US": [_video("c")]})
    raw_video, _ = ext.extrair(_cfg(["BR", "US"]))
    assert set(raw_video["country"]) == {"US"}


def test_extrair_real_para_quando_a_cota_acaba_e_guarda_o_que_ja_veio(monkeypatch):
    _usar(monkeypatch, {"BR": [_video("a")], "US": CotaEsgotada("acabou"), "MX": [_video("c")]})
    raw_video, _ = ext.extrair(_cfg(["BR", "US", "MX"]))
    assert set(raw_video["country"]) == {"BR"}   # MX nem chega a ser tentado