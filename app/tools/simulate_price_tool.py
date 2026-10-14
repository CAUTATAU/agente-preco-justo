from strands import ToolContext, tool

from app.services.precos import brl, pct, status_preco
from app.tools.tool_result import erro, resultado_json


@tool(context=True)
def simulate_price(item_id: str, new_price: float, tool_context: ToolContext) -> dict:
    """Simula um preço novo para um item da ficha: quanto sobra por unidade e no mês, e a cor do semáforo.

    Use sempre que a pessoa perguntar "e se eu cobrar X?" ou quiser baixar ou subir um preço.
    Os valores já vêm formatados: copie como vieram.

    Args:
        item_id: id do item na ficha.
        new_price: preço novo em reais, por unidade ou atendimento.
    """
    ficha = tool_context.agent.state.get("contexto")
    item = next((i for i in ficha["itens"] if i["id"] == item_id), None)
    if item is None:
        return erro("Item não encontrado na ficha.")
    if new_price <= 0:
        return erro("O preço precisa ser maior que zero.")

    custo = item["custoTotal"]
    sobra = new_price - custo
    return resultado_json(
        {
            "item": item["nome"],
            "precoNovo": brl(new_price),
            "custo": brl(custo),
            "status": status_preco(new_price, custo, item["precoIdeal"], ficha["valorHora"]),
            "sobraPorUnidade": brl(sobra),
            "sobraPct": pct(sobra / new_price),
            # "Total" no nome: o modelo lia "sobraNoMes" como diferença ("R$ 557,69 a mais")
            "sobraTotalNoMes": brl(sobra * item["vendasMes"]),
            "precoMinimo": brl(item["precoMinimo"]),
            "precoIdeal": brl(item["precoIdeal"]),
        }
    )
