from typing import Literal

from strands import ToolContext, tool

from app.services.precos import brl, pct
from app.tools.tool_result import resultado_json

# critério -> (campo da ficha, como mostrar o valor)
CRITERIOS = {
    "sobra_por_hora": ("sobraPorHora", lambda v: f"{brl(v)} por hora"),
    "sobra_no_mes": ("sobraMes", lambda v: f"{brl(v)} no mês"),
    "sobra_pct": ("sobraPct", lambda v: f"{pct(v / 100)} do preço"),
}


@tool(context=True)
def compare_items(criterion: Literal["sobra_por_hora", "sobra_no_mes", "sobra_pct"], tool_context: ToolContext) -> dict:
    """Ordena os itens da ficha do que deixa mais para o que deixa menos. Use sempre que a pessoa
    quiser comparar itens ("qual rende mais?", "qual vale mais a pena?"); nunca compare de cabeça.

    Args:
        criterion: "sobra_por_hora" (quanto sobra por hora de trabalho), "sobra_no_mes" (quanto sobra
            no mês com as vendas atuais) ou "sobra_pct" (quanto sobra em % do preço).
    """
    campo, mostrar = CRITERIOS[criterion]
    itens = [i for i in tool_context.agent.state.get("contexto")["itens"] if i.get(campo) is not None]
    itens.sort(key=lambda i: i[campo], reverse=True)
    return resultado_json(
        {"ranking": [{"posicao": n, "item": i["nome"], "valor": mostrar(i[campo])} for n, i in enumerate(itens, 1)]}
    )
