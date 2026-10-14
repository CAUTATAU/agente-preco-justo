"""Serviço interno do agente: só o backend Node chama, pela rede privada do Railway, com X-Agent-Key."""

import asyncio
import logging
import os
import secrets
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent import agent_factory
from app.schemas import PedidoChat, RespostaChat

logging.getLogger("strands").setLevel(logging.WARNING)  # em DEBUG o Strands loga o pedido inteiro
logger = logging.getLogger("uvicorn.error")

AGENT_KEY = os.environ.get("AGENT_KEY", "")
if len(AGENT_KEY) < 32:
    raise RuntimeError("AGENT_KEY precisa ter pelo menos 32 caracteres.")

PARADAS_DE_RECUSA = {"refusal", "content_filtered"}  # no Converse do Bedrock a recusa chega como content_filtered
TEXTO_RECUSA = "Não consigo ajudar com isso. Posso responder sobre os preços e custos da sua ficha."
INDISPONIVEL = "O assistente está indisponível agora. Tente de novo em alguns minutos."

app = FastAPI(title="Agente Preço Justo", docs_url=None, redoc_url=None, openapi_url=None)


def erro(status: int, mensagem: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": mensagem})


def texto_da_resposta(mensagens: list) -> str:
    """Todo texto do assistente nesta pergunta: o modelo divide a resposta em volta das chamadas de
    ferramenta (e às vezes termina sem texto), então só a última mensagem perderia parte dela."""
    textos = [b["text"].strip() for m in mensagens if m["role"] == "assistant" for b in m["content"] if b.get("text", "").strip()]
    return "\n\n".join(textos)


@app.middleware("http")
async def exige_chave_do_node(request: Request, call_next):
    chave = request.headers.get("x-agent-key", "")
    if request.url.path != "/health" and not secrets.compare_digest(chave.encode(), AGENT_KEY.encode()):
        # 403 e não 401: o PWA trata 401 como sessão expirada e deslogaria a pessoa
        return erro(403, "Acesso negado.")
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def corpo_invalido(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # só onde e o quê: os valores recusados podem conter dados da ficha
    logger.info("corpo inválido: %s", [(e["loc"], e["type"]) for e in exc.errors()])
    return erro(400, "Não consegui ler a pergunta. Atualize o app e tente de novo.")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=RespostaChat)
async def chat(pedido: PedidoChat):
    if not pedido.consentimento:
        return erro(403, "Para usar o assistente, autorize o envio dos dados da sua ficha.")

    agente = agent_factory.create_agent(pedido.contexto, pedido.historico)
    ficha = "<ficha>" + pedido.contexto.model_dump_json() + "</ficha>"  # dado, não instrução: fica fora do system prompt
    inicio, n_historico = time.perf_counter(), len(agente.messages)
    try:
        resultado = await asyncio.wait_for(
            agente.invoke_async([{"text": ficha}, {"text": pedido.pergunta}], limits={"turns": 4}), timeout=60
        )
    except Exception as e:  # modelo fora, cota, credencial ou tempo esgotado: para a pessoa é "indisponível"
        logger.warning("modelo falhou: %s", type(e).__name__)
        return erro(503, INDISPONIVEL)

    uso = resultado.metrics.accumulated_usage
    ferramentas = {nome: m.call_count for nome, m in resultado.metrics.tool_metrics.items()}
    logger.info(
        "chat stop=%s in=%d cache_write=%d cache_read=%d out=%d tools=%s ms=%d",
        resultado.stop_reason, uso["inputTokens"], uso.get("cacheWriteInputTokens", 0),
        uso.get("cacheReadInputTokens", 0), uso["outputTokens"], ferramentas,
        (time.perf_counter() - inicio) * 1000,
    )  # nunca a ficha, a pergunta ou a resposta

    if resultado.stop_reason in PARADAS_DE_RECUSA:
        return RespostaChat(resposta=TEXTO_RECUSA)
    propostas = agente.state.get("propostas")
    texto = texto_da_resposta(agente.messages[n_historico:]) or ("Deixei uma sugestão abaixo." if propostas else TEXTO_RECUSA)
    return RespostaChat(resposta=texto, propostas=propostas, acoes=agente.state.get("acoes"))
