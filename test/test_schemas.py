import pytest
from pydantic import ValidationError

from app.schemas import Acao, Contexto, PedidoChat
from conftest import carregar


def pedido(**extra) -> dict:
    return {"contexto": carregar("sobrancelhas"), "pergunta": "posso baixar o buço?", **extra}


@pytest.mark.parametrize("nome", ["sobrancelhas", "bicicletas", "brownies", "sobrancelhas-sem-hora"])
def test_contexto_gerado_pelo_pwa_e_aceito(nome):
    # As fixtures saem do calc.ts/advisor.ts reais + montarContexto: se o contrato divergir, quebra aqui
    Contexto.model_validate(carregar(nome))


def test_campos_fora_do_contrato_nao_chegam_a_ia():
    ctx = carregar("sobrancelhas") | {"nomeNegocio": "Studio da Ana", "email": "ana@ex.com"}
    dump = Contexto.model_validate(ctx).model_dump()
    assert "nomeNegocio" not in dump and "email" not in dump


def test_recusa_numero_nao_finito():
    ctx = carregar("sobrancelhas")
    ctx["itens"][0]["preco"] = float("nan")
    with pytest.raises(ValidationError):
        PedidoChat.model_validate(pedido(contexto=ctx))


@pytest.mark.parametrize(
    "extra",
    [
        {"historico": [{"papel": "usuario", "texto": "oi"}] * 7},
        {"pergunta": "x" * 501},
        {"pergunta": ""},
    ],
)
def test_recusa_pedido_fora_dos_limites(extra):
    with pytest.raises(ValidationError):
        PedidoChat.model_validate(pedido(**extra))


@pytest.mark.parametrize("rota", ["//site-malicioso.com", "https://site.com", "despesas"])
def test_acao_so_aceita_rota_interna(rota):
    with pytest.raises(ValidationError):
        Acao(label="Ir", to=rota)


def test_acao_aceita_rota_das_dicas():
    assert Acao(label="Cadastrar", to="/despesas?aba=ferramentas").to == "/despesas?aba=ferramentas"
