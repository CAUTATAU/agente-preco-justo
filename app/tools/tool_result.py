"""Retorno das tools no formato ToolResult do Strands, com bloco JSON.

Devolvendo só um dict, o Strands faz {"text": str(dict)}: o modelo leria o repr do Python
(aspas simples, True/None). O bloco "json" chega estruturado, e o status "error" é o sinal
para o modelo tratar o problema em vez de inventar dados.
"""

from typing import Any

from strands.types.tools import ToolResult


def resultado_json(dados: Any, sucesso: bool = True) -> ToolResult:
    return {"status": "success" if sucesso else "error", "content": [{"json": dados}]}


def erro(mensagem: str) -> ToolResult:
    return resultado_json({"erro": mensagem}, sucesso=False)
