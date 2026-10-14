"""Eval com o Bedrock real (custa centavos): roda os casos de eval_casos.json pela rota /chat.

Checagens em toda resposta: sem jargão, todo R$ e % vem da ficha ou de uma ferramenta (RN07),
nunca diz que alterou algo (RN06) e respeita o tamanho. Por caso: ferramentas e propostas esperadas.
Rode antes de mudar prompt, modelo ou parâmetros:

    .venv/Scripts/python scripts/eval.py
"""

import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("AGENT_KEY", "eval-local-" + "x" * 32)

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.agent import agent_factory  # noqa: E402

# US$ por milhão de tokens, Haiku 4.5 no perfil us. (gravar no cache = 1,25× a entrada; ler = 0,1×)
PRECOS = {"inputTokens": 1.10, "cacheWriteInputTokens": 1.375, "cacheReadInputTokens": 0.11, "outputTokens": 5.50}


def custo_dolares(uso: dict) -> float:
    return sum(uso.get(campo, 0) / 1e6 * preco for campo, preco in PRECOS.items())

JARGAO = re.compile(
    r"\b(margem|markup|rateio|ratear|custo fixo|overhead|custo vari[aá]vel|cmv|ponto de equil[ií]brio|"
    r"break-even|pr[oó]-labore|deprecia[cç][aã]o|lucro l[ií]quido|lucro bruto|faturamento|precifica[cç][aã]o)\b",
    re.IGNORECASE,
)
ALTEROU = re.compile(r"\b(alterei|salvei|atualizei|mudei|troquei|já alterado|foi alterado|foi atualizado)\b", re.IGNORECASE)
REAIS = re.compile(r"(-?)R\$\s?(-?[\d.]+,\d{2})")
PORCENTO = re.compile(r"(-?\d+(?:,\d+)?)\s?%")


def para_float(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def numeros_do_texto(texto: str) -> tuple[list[float], list[float]]:
    texto = texto.replace(" ", " ")
    reais = [para_float(v) * (-1 if s else 1) for s, v in REAIS.findall(texto)]
    return reais, [para_float(v) for v in PORCENTO.findall(texto)]


def permitidos(ficha: dict, resultados_tools: list) -> tuple[set[float], set[float]]:
    """Todo número da ficha (crus e os escritos nos textos) e dos resultados das ferramentas."""
    crus: set[float] = set()

    def coletar(valor):
        if isinstance(valor, bool):
            return
        if isinstance(valor, (int, float)):
            crus.add(float(valor))
        elif isinstance(valor, dict):
            for v in valor.values():
                coletar(v)
        elif isinstance(valor, list):
            for v in valor:
                coletar(v)

    coletar(ficha)
    coletar(resultados_tools)
    texto = json.dumps([ficha, resultados_tools], ensure_ascii=False)
    reais, pcts = numeros_do_texto(texto)
    return crus | set(reais), crus | set(pcts)


def perto(x: float, aceitos: set[float], tolerancia: float) -> bool:
    return any(abs(x - v) <= tolerancia for v in aceitos)


def numeros_inventados(resposta: str, ficha: dict, tools: list) -> list[str]:
    """R$ e % da resposta que não estão na ficha nem nas ferramentas (arredondar para exibir é aceito)."""
    reais_ok, pcts_ok = permitidos(ficha, tools)
    reais, pcts = numeros_do_texto(resposta)
    return [f"R$ inventado: {v}" for v in reais if not perto(v, reais_ok, 0.006)] + [
        f"% inventado: {v}" for v in pcts if not perto(v, pcts_ok, 0.5 if float(v).is_integer() else 0.051)
    ]


def carregar_ficha(nome: str) -> dict:
    return json.loads((RAIZ / "test" / "fixtures" / f"{nome}.json").read_text(encoding="utf-8"))


def resultados_das_tools(agente) -> list:
    return [
        bloco["toolResult"]
        for msg in agente.messages
        for bloco in msg["content"]
        if "toolResult" in bloco
    ]


def avaliar(caso: dict, corpo: dict, agente) -> list[str]:
    falhas = []
    resposta = corpo["resposta"]
    ficha = carregar_ficha(caso["ficha"])
    tools = resultados_das_tools(agente)

    if m := JARGAO.search(resposta):
        falhas.append(f"jargão: {m.group(0)!r}")
    if m := ALTEROU.search(resposta):
        falhas.append(f"disse que alterou: {m.group(0)!r}")

    falhas += numeros_inventados(resposta, ficha, tools)

    linhas_lista = [linha for linha in resposta.splitlines() if linha.strip().startswith("- ")]
    corrido = " ".join(linha for linha in resposta.splitlines() if not linha.strip().startswith("- "))
    frases = len(re.findall(r"[.!?](?:\s|$)", corrido)) + len(linhas_lista)
    if len(linhas_lista) > 4:
        falhas.append(f"{len(linhas_lista)} linhas de lista (máx. 4)")
    if frases > 5:
        falhas.append(f"{frases} frases (máx. 5)")

    chamadas = agente.event_loop_metrics.tool_metrics
    falhas += [f"não chamou {t}" for t in caso.get("ferramentas", []) if t not in chamadas]
    falhas += [f"não citou {t!r}" for t in caso.get("contem", []) if t.lower() not in resposta.lower()]

    esperadas = caso.get("propostas")
    tipos = [p["tipo"] for p in corpo["propostas"]]
    if esperadas == [] and tipos:
        falhas.append(f"propôs sem poder: {tipos}")
    elif isinstance(esperadas, str) and esperadas not in tipos:
        falhas.append(f"não propôs {esperadas}")
    return falhas


def main_eval() -> int:
    casos = json.loads((Path(__file__).parent / "eval_casos.json").read_text(encoding="utf-8"))
    capturados = []
    original = agent_factory.create_agent

    def capturar(*args):
        agente = original(*args)
        capturados.append(agente)
        return agente

    agent_factory.create_agent = capturar
    cliente = TestClient(main.app)
    total_custo, reprovados = 0.0, 0

    for n, caso in enumerate(casos):
        if n:
            time.sleep(6)  # a cota do Haiku 4.5 é 10 chamadas/min; sem pausa a própria rodada estoura
        pedido ={"consentimento": True, "contexto": carregar_ficha(caso["ficha"]), "pergunta": caso["pergunta"]}
        r = cliente.post("/chat", json=pedido, headers={"X-Agent-Key": main.AGENT_KEY})
        if r.status_code != 200:
            reprovados += 1
            print(f"\nFALHOU [{caso['ficha']}] {caso['pergunta']}\n  HTTP {r.status_code}: {r.json()}")
            continue
        corpo, agente = r.json(), capturados[-1]
        total_custo += custo_dolares(agente.event_loop_metrics.accumulated_usage)
        falhas = avaliar(caso, corpo, agente)
        reprovados += bool(falhas)
        print(f"\n{'FALHOU' if falhas else 'ok'} [{caso['ficha']}] {caso['pergunta']}")
        for falha in falhas:
            print(f"  ✗ {falha}")
        print("  " + corpo["resposta"].replace("\n", "\n  "))
        if corpo["propostas"] or corpo["acoes"]:
            print(f"  propostas={corpo['propostas']} acoes={corpo['acoes']}")

    print(f"\n{len(casos) - reprovados}/{len(casos)} casos passaram · custo da rodada ~US$ {total_custo:.3f}")
    return 1 if reprovados else 0


if __name__ == "__main__":
    sys.exit(main_eval())
