"""Paridade com o PWA: valores esperados tirados rodando o calc.ts/format.ts originais no node."""

import pytest

from app.services.precos import brl, ceil_cents, num, pct, status_preco, valor_hora


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (8.683798, 8.69),
        (0.1 + 0.2, 0.30),  # erro de ponto flutuante: math.ceil(v * 100) daria 0,31
        (0.0205, 0.03),  # Math.round do JS sobe no .5; o round() do Python daria 0,02
        (1.0049, 1.01),
        (10, 10.0),
    ],
)
def test_ceil_cents_igual_ao_format_ts(valor, esperado):
    assert ceil_cents(valor) == esperado


@pytest.mark.parametrize("renda, horas, esperado", [(3000, 40, 17.31), (2500, 44, 13.12), (1800, 52, 7.99)])
def test_valor_hora_igual_ao_hourly_rate_helper(renda, horas, esperado):
    assert valor_hora(renda, horas) == esperado


# Buço da fixture: custo 8,683798 e preço ideal 12,41
@pytest.mark.parametrize(
    "preco, esperado",
    [
        (8.67, "vermelho"),
        (8.68, "amarelo"),  # abaixo do custo por menos de meio centavo: o calc.ts tolera (EPS)
        (12.40, "amarelo"),
        (12.41, "verde"),
    ],
)
def test_status_segue_o_rn04(preco, esperado):
    assert status_preco(preco, custo=8.683798, ideal=12.41, valor_hora=25) == esperado


@pytest.mark.parametrize("preco, hora", [(15, None), (15, 0), (0, 25)])
def test_status_incompleto_sem_hora_ou_sem_preco(preco, hora):
    assert status_preco(preco, custo=8.683798, ideal=12.41, valor_hora=hora) == "incompleto"


@pytest.mark.parametrize(
    "valor, esperado",
    [(1234.5, "R$ 1.234,50"), (-2.3162, "-R$ 2,32"), (0.004, "R$ 0,00"), (1_000_000, "R$ 1.000.000,00")],
)
def test_brl_formata_como_o_app(valor, esperado):
    assert brl(valor) == esperado


@pytest.mark.parametrize("valor, esperado", [(40 * 52 / 12, "173,33"), (40, "40"), (1234.5, "1.234,5")])
def test_num_como_o_format_ts(valor, esperado):
    assert num(valor) == esperado


@pytest.mark.parametrize("razao, esperado", [(2.3162 / 11, "21,1%"), (-0.5, "-50,0%"), (0.3, "30,0%")])
def test_pct_com_virgula_e_uma_casa(razao, esperado):
    assert pct(razao) == esperado
