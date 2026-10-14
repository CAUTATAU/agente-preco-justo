import os
from functools import cache

from botocore.config import Config
from strands import Agent, ModelRetryStrategy
from strands.models import BedrockModel, CacheConfig
from strands.types.content import Messages

from app.agent.prompts import SYSTEM_PROMPT
from app.schemas import Contexto, Mensagem
from app.tools.compare_items_tool import compare_items
from app.tools.hourly_rate_tool import hourly_rate
from app.tools.propose_change_tool import propose_change
from app.tools.show_tip_tool import show_tip
from app.tools.simulate_price_tool import simulate_price

TOOLS = [simulate_price, compare_items, hourly_rate, propose_change, show_tip]


@cache
def modelo() -> BedrockModel:
    # Criado no primeiro pedido, não no import: testes e healthcheck não dependem de credenciais AWS
    return BedrockModel(
        model_id=os.getenv("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        max_tokens=2000,  # teto, não custo: paga-se só o que é gerado (respostas medidas: 180–260 tokens)
        temperature=0.3,
        boto_client_config=Config(read_timeout=30, retries={"max_attempts": 2, "mode": "standard"}),
        # Medido em 2026-10-14: o prefixo (prompt + tools + ficha) passa de ~5,2 mil tokens, acima do mínimo de 4.096
        # do Haiku 4.5. A 2ª chamada do loop de ferramentas lê do cache: ~30% mais barato por pergunta com ferramenta.
        cache_config=CacheConfig(strategy="auto"),
    )


def historico_para_mensagens(historico: list[Mensagem]) -> Messages:
    """O Converse exige começar pelo usuário e alternar papéis; a pergunta nova entra depois, como "user"."""
    mensagens: Messages = []
    for msg in historico:
        role = "user" if msg.papel == "usuario" else "assistant"
        if not mensagens and role == "assistant":
            continue
        if mensagens and mensagens[-1]["role"] == role:
            mensagens[-1]["content"][0]["text"] += "\n\n" + msg.texto
        else:
            mensagens.append({"role": role, "content": [{"text": msg.texto}]})
    if mensagens and mensagens[-1]["role"] == "user":
        mensagens.pop()
    return mensagens


def create_agent(contexto: Contexto, historico: list[Mensagem]) -> Agent:
    """Um agente novo por pedido: nada fica guardado no servidor entre perguntas (RNF06)."""
    return Agent(
        model=modelo(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=historico_para_mensagens(historico),
        state={"contexto": contexto.model_dump(), "propostas": [], "acoes": []},
        # A cota do Haiku 4.5 é 10 chamadas/min: espera 5 s, 5 s e 10 s (o padrão do Strands iria até 4 min,
        # além dos 60 s do pedido)
        retry_strategy=ModelRetryStrategy(max_attempts=4, initial_delay=5, max_delay=20),
        callback_handler=None,  # o padrão imprime a resposta no stdout, que vira log do Railway
    )
