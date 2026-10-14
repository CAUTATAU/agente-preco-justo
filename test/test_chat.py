"""Rota /chat com um agente falso no lugar do Bedrock (o modelo é a única parte externa)."""

import os

import pytest
from fastapi.testclient import TestClient
from strands.agent.agent_result import AgentResult
from strands.agent.state import AgentState
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.exceptions import ModelThrottledException

from app import main
from app.agent import agent_factory
from conftest import carregar

CHAVE = {"X-Agent-Key": os.environ["AGENT_KEY"]}
BUCO = "4f6a1c2e-0b7d-4c1e-9a55-1d2e3f4a5b6c"
PROPOSTA = {"tipo": "preco", "valor": 12.41, "motivo": "Mantém a meta", "itemId": BUCO, "horasSemana": None}


class AgenteFalso:
    """Faz o papel do create_agent + Agent: registra o que recebeu e devolve um AgentResult real."""

    def __init__(self, texto="Pode, até **R$ 12,41**.", parada="end_turn", propostas=(), erro=None):
        self.texto, self.parada, self.propostas, self.erro = texto, parada, list(propostas), erro
        self.mensagens = None  # o que o "modelo" acrescenta à conversa; padrão: uma resposta com `texto`
        self.chamadas = []

    def __call__(self, contexto, historico):
        self.state = AgentState({"contexto": contexto.model_dump(), "propostas": [], "acoes": []})
        self.messages = [{"role": "assistant", "content": [{"text": "resposta antiga do histórico"}]}]
        return self

    async def invoke_async(self, prompt, limits=None):
        self.chamadas.append((prompt, limits))
        if self.erro:
            raise self.erro
        self.state.set("propostas", self.propostas)
        self.messages.append({"role": "user", "content": prompt})
        self.messages.extend(self.mensagens or [assistente(self.texto)])
        return AgentResult(stop_reason=self.parada, message=self.messages[-1], metrics=EventLoopMetrics(), state={})


def assistente(texto: str, *, com_ferramenta: bool = False) -> dict:
    conteudo = [{"text": texto}] if texto else []
    if com_ferramenta:
        conteudo.append({"toolUse": {"toolUseId": "t1", "name": "show_tip", "input": {"tip_id": "x"}}})
    return {"role": "assistant", "content": conteudo}


RESULTADO_TOOL = {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "status": "success", "content": []}}]}


@pytest.fixture
def cliente():
    return TestClient(main.app)


@pytest.fixture
def agente(monkeypatch):
    falso = AgenteFalso()
    monkeypatch.setattr(agent_factory, "create_agent", falso)
    return falso


def pedido(**extra) -> dict:
    return {"consentimento": True, "contexto": carregar("sobrancelhas"), "pergunta": "posso baixar o buço?", **extra}


def test_health_nao_exige_chave(cliente):
    assert cliente.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("cabecalhos", [{}, {"X-Agent-Key": "errada"}])
def test_sem_a_chave_do_node_e_403(cliente, agente, cabecalhos):
    r = cliente.post("/chat", json=pedido(), headers=cabecalhos)
    assert (r.status_code, r.json()) == (403, {"error": "Acesso negado."})
    assert agente.chamadas == []


def test_sem_consentimento_nao_chama_o_modelo(cliente, agente):
    r = cliente.post("/chat", json=pedido(consentimento=False), headers=CHAVE)
    assert r.status_code == 403
    assert "autorize" in r.json()["error"]
    assert agente.chamadas == []


@pytest.mark.parametrize(
    "corpo",
    [
        pedido(historico=[{"papel": "usuario", "texto": "oi"}] * 7),
        pedido(pergunta=""),
        {"consentimento": True, "pergunta": "oi"},
    ],
)
def test_corpo_invalido_e_400_no_formato_do_node(cliente, agente, corpo):
    r = cliente.post("/chat", json=corpo, headers=CHAVE)
    assert r.status_code == 400
    assert set(r.json()) == {"error"}
    assert agente.chamadas == []


def test_resposta_traz_texto_e_propostas(cliente, agente):
    agente.propostas = [PROPOSTA]
    r = cliente.post("/chat", json=pedido(), headers=CHAVE)
    assert r.status_code == 200
    assert r.json() == {"resposta": "Pode, até **R$ 12,41**.", "propostas": [PROPOSTA], "acoes": []}


def test_modelo_recebe_a_ficha_minima_a_pergunta_e_o_limite(cliente, agente):
    ctx = carregar("sobrancelhas") | {"nomeNegocio": "Studio da Ana"}
    cliente.post("/chat", json=pedido(contexto=ctx), headers=CHAVE)
    (prompt, limits), = agente.chamadas
    ficha, pergunta = prompt[0]["text"], prompt[1]["text"]
    assert ficha.startswith("<ficha>") and "Buço com cera" in ficha
    assert "Studio da Ana" not in ficha  # RNF06: o que não está no contrato não vai para a IA
    assert pergunta == "posso baixar o buço?"
    assert limits == {"turns": 4}


@pytest.mark.parametrize("parada", ["refusal", "content_filtered"])
def test_recusa_do_modelo_descarta_propostas(cliente, agente, parada):
    agente.parada, agente.propostas = parada, [PROPOSTA]
    corpo = cliente.post("/chat", json=pedido(), headers=CHAVE).json()
    assert corpo["propostas"] == [] and corpo["resposta"] == main.TEXTO_RECUSA


def test_texto_escrito_antes_da_ferramenta_nao_se_perde(cliente, agente):
    # Bedrock real: o modelo responde, chama show_tip no fim e encerra sem texto
    agente.mensagens = [assistente("Seus preços estão bons.", com_ferramenta=True), RESULTADO_TOOL, assistente("")]
    assert cliente.post("/chat", json=pedido(), headers=CHAVE).json()["resposta"] == "Seus preços estão bons."


def test_resposta_dividida_pela_ferramenta_vem_inteira(cliente, agente):
    # Bedrock real: "Falta o valor da hora..." → show_tip → "Mas antes de baixar..."; só o fim perdia o começo
    agente.mensagens = [
        assistente("Sem o valor da hora, não dá para saber.", com_ferramenta=True),
        RESULTADO_TOOL,
        assistente("Mas antes, confira a jornada."),
    ]
    resposta = cliente.post("/chat", json=pedido(), headers=CHAVE).json()["resposta"]
    assert resposta == "Sem o valor da hora, não dá para saber.\n\nMas antes, confira a jornada."


def test_texto_vazio_com_proposta_aponta_o_cartao(cliente, agente):
    agente.texto, agente.propostas = "", [PROPOSTA]
    assert cliente.post("/chat", json=pedido(), headers=CHAVE).json()["resposta"] == "Deixei uma sugestão abaixo."


@pytest.mark.parametrize("erro", [ModelThrottledException("cota"), RuntimeError("boom")])
def test_falha_do_modelo_vira_503_amigavel(cliente, agente, erro):
    agente.erro = erro
    r = cliente.post("/chat", json=pedido(), headers=CHAVE)
    assert (r.status_code, r.json()) == (503, {"error": main.INDISPONIVEL})
