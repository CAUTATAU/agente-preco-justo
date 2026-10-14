from typing import Literal

from strands import ToolContext, tool

from app.tools.tool_result import erro, resultado_json

MAX_PROPOSTAS = 3


@tool(context=True)
def propose_change(
    kind: Literal["preco", "valor_hora"],
    value: float,
    reason: str,
    tool_context: ToolContext,
    item_id: str | None = None,
    weekly_hours: float | None = None,
) -> dict:
    """Sugere uma mudança que a pessoa pode aceitar com um toque. Nada é alterado sem o aceite dela.

    Use para sugerir um preço novo para um item (kind "preco", com item_id) ou um valor da hora
    (kind "valor_hora"). Só sugira valores que vieram da ficha ou de outra ferramenta.

    Args:
        kind: "preco" para o preço de um item ou "valor_hora" para o valor da hora de trabalho.
        value: valor sugerido em reais.
        reason: motivo em uma frase curta, sem jargão.
        item_id: id do item, obrigatório quando kind for "preco".
        weekly_hours: horas por semana para o valor da hora; se omitido, usa as da ficha.
    """
    state = tool_context.agent.state
    ficha = state.get("contexto")
    valor = round(value, 2)
    if not 0.01 <= valor <= 1e7:
        return erro("O valor precisa ser maior que zero.")

    if kind == "preco":
        item = next((i for i in ficha["itens"] if i["id"] == item_id), None)
        if item is None:
            return erro("Item não encontrado na ficha.")
        # RN01: sem a hora de trabalho o preço mínimo sai sem o trabalho da pessoa
        if not ficha["valorHora"] or item["status"] == "incompleto":
            return erro("Falta o valor da hora: não sugira preço. Ofereça ajuda para calcular a hora.")
        proposta = {"tipo": "preco", "valor": valor, "motivo": reason[:200], "itemId": item_id, "horasSemana": None}
    else:
        horas = ficha["horasSemana"] if weekly_hours is None else weekly_hours
        if not 1 <= horas <= 112:
            return erro("As horas por semana precisam ficar entre 1 e 112.")
        proposta = {"tipo": "valor_hora", "valor": valor, "motivo": reason[:200], "itemId": None, "horasSemana": horas}

    # Uma sugestão por alvo: a nova substitui a anterior
    propostas = [p for p in state.get("propostas") if (p["tipo"], p["itemId"]) != (proposta["tipo"], proposta["itemId"])]
    if len(propostas) >= MAX_PROPOSTAS:
        return erro("Já há 3 sugestões nesta resposta.")
    state.set("propostas", propostas + [proposta])
    return resultado_json({"ok": "Cartão criado: a pessoa decide se aceita. Não diga que o valor foi alterado."})
