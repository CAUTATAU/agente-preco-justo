import pytest

from app.agent.agent_factory import historico_para_mensagens
from app.schemas import Mensagem


def m(papel: str, texto: str) -> Mensagem:
    return Mensagem(papel=papel, texto=texto)


def u(texto: str) -> dict:
    return {"role": "user", "content": [{"text": texto}]}


def a(texto: str) -> dict:
    return {"role": "assistant", "content": [{"text": texto}]}


# O Converse do Bedrock exige começar pelo usuário e alternar; a pergunta nova entra depois, como "user"
@pytest.mark.parametrize(
    "historico, esperado",
    [
        ([], []),
        ([m("assistente", "Olá!")], []),
        ([m("usuario", "a"), m("assistente", "b")], [u("a"), a("b")]),
        ([m("usuario", "a"), m("usuario", "b"), m("assistente", "c")], [u("a\n\nb"), a("c")]),
        ([m("usuario", "a"), m("assistente", "b"), m("usuario", "c")], [u("a"), a("b")]),
        ([m("assistente", "x"), m("usuario", "a"), m("assistente", "b"), m("assistente", "c")], [u("a"), a("b\n\nc")]),
    ],
)
def test_historico_vira_conversa_alternada(historico, esperado):
    assert historico_para_mensagens(historico) == esperado
