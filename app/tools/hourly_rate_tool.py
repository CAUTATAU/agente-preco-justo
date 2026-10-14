from strands import tool

from app.services.precos import SEMANAS_POR_MES, brl, num, valor_hora
from app.tools.tool_result import erro, resultado_json


@tool
def hourly_rate(monthly_income: float, weekly_hours: float) -> dict:
    """Calcula o valor da hora de trabalho pela mesma conta do app: renda desejada ÷ horas no mês.

    Use quando a pessoa não souber quanto vale a hora dela, depois de perguntar as duas coisas.

    Args:
        monthly_income: quanto a pessoa quer ganhar por mês pelo trabalho, em reais (só as contas pessoais).
        weekly_hours: horas de trabalho por semana.
    """
    if monthly_income <= 0 or not 1 <= weekly_hours <= 112:
        return erro("Informe uma renda maior que zero e entre 1 e 112 horas por semana.")

    valor = valor_hora(monthly_income, weekly_hours)
    return resultado_json(
        {
            "valorHora": valor,
            "valorHoraTexto": brl(valor),
            "conta": f"{brl(monthly_income)} ÷ {num(weekly_hours * SEMANAS_POR_MES)} horas no mês",
        }
    )
