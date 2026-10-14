"""Espelho das contas do PWA (calc.ts / format.ts). O calc.ts continua sendo a fonte da verdade:
qualquer mudança lá precisa ser repetida aqui, e os testes de paridade usam valores tirados do JS."""

import math

SEMANAS_POR_MES = 52 / 12
EPS = 0.005


def ceil_cents(valor: float) -> float:
    """Arredonda para cima no centavo, como o ceilCents do format.ts.

    floor(x + 0.5) imita o Math.round do JS (o round() do Python arredonda .5 para o par).
    """
    return math.ceil(math.floor(valor * 1000 + 0.5) / 10) / 100


def valor_hora(renda_mensal: float, horas_semana: float) -> float:
    """Mesma conta do HourlyRateHelper: renda ÷ horas no mês, arredondado para cima."""
    return ceil_cents(renda_mensal / (horas_semana * SEMANAS_POR_MES))


def status_preco(preco: float, custo: float, ideal: float, valor_hora: float | None) -> str:
    """Semáforo do RN04, com a mesma tolerância de meio centavo do calc.ts."""
    if not valor_hora or preco <= 0:
        return "incompleto"
    if preco + EPS < custo:
        return "vermelho"
    if preco + EPS < ideal:
        return "amarelo"
    return "verde"


def brl(valor: float) -> str:
    """R$ 1.234,56 (negativo: -R$ 1,23), como o Intl pt-BR do app."""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if round(valor, 2) < 0 else ''}R$ {texto}"


def num(valor: float) -> str:
    """1.234,5 (até 2 casas, sem zeros à direita), como o num do format.ts."""
    texto = f"{valor:,.2f}".rstrip("0").rstrip(".")
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(razao: float) -> str:
    """21,1%"""
    return f"{razao * 100:.1f}%".replace(".", ",")
