import json
import os
from pathlib import Path

os.environ.setdefault("AGENT_KEY", "chave-de-teste-" + "x" * 32)
from types import SimpleNamespace

import pytest
from strands import ToolContext
from strands.agent.state import AgentState

FIXTURES = Path(__file__).parent / "fixtures"


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))


def contexto_de_tool(ficha: dict) -> ToolContext:
    """ToolContext com o AgentState real do Strands; as tools só usam agent.state."""
    agente = SimpleNamespace(state=AgentState({"contexto": ficha, "propostas": [], "acoes": []}))
    return ToolContext(tool_use={"toolUseId": "t1", "name": "teste", "input": {}}, agent=agente, invocation_state={})


@pytest.fixture
def sobrancelhas() -> dict:
    return carregar("sobrancelhas")


@pytest.fixture
def bicicletas() -> dict:
    return carregar("bicicletas")
