from strands import ToolContext, tool

from app.tools.tool_result import erro, resultado_json

MAX_ACOES = 3


@tool(context=True)
def show_tip(tip_id: str, tool_context: ToolContext) -> dict:
    """Mostra abaixo da resposta o botão do app ligado a uma dica da ficha (ex.: "Lançar despesa").

    Args:
        tip_id: id de uma dica da ficha.
    """
    state = tool_context.agent.state
    dica = next((d for d in state.get("contexto")["dicas"] if d["id"] == tip_id), None)
    if dica is None or not dica.get("acao"):
        return erro("Essa dica não existe na ficha ou não tem botão.")

    acoes = state.get("acoes")
    if dica["acao"] not in acoes:
        if len(acoes) >= MAX_ACOES:
            return erro("Já há 3 botões nesta resposta.")
        state.set("acoes", acoes + [dica["acao"]])
    return resultado_json({"ok": "Botão adicionado abaixo da resposta."})
