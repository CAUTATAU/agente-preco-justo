import pytest

from app.tools.compare_items_tool import compare_items
from app.tools.hourly_rate_tool import hourly_rate
from app.tools.propose_change_tool import propose_change
from app.tools.show_tip_tool import show_tip
from app.tools.simulate_price_tool import simulate_price
from conftest import contexto_de_tool

BUCO = "4f6a1c2e-0b7d-4c1e-9a55-1d2e3f4a5b6c"
HENNA = "8b2d7e10-5c3a-4f2b-8e61-0a9b8c7d6e5f"


def dados(resultado: dict):
    return resultado["content"][0]["json"]


@pytest.mark.parametrize(
    "tool, parametros",
    [
        (simulate_price, {"item_id", "new_price"}),
        (hourly_rate, {"monthly_income", "weekly_hours"}),
        (propose_change, {"kind", "value", "reason", "item_id", "weekly_hours"}),
        (show_tip, {"tip_id"}),
        (compare_items, {"criterion"}),
    ],
)
def test_modelo_ve_so_os_parametros_da_tool(tool, parametros):
    assert set(tool.tool_spec["inputSchema"]["json"]["properties"]) == parametros


# --- simulate_price (buço: custo 8,683798, ideal 12,41, 40 vendas/mês) ---


def test_simula_preco_abaixo_da_meta(sobrancelhas):
    r = simulate_price(item_id=BUCO, new_price=11, tool_context=contexto_de_tool(sobrancelhas))
    assert r["status"] == "success"
    assert {k: dados(r)[k] for k in ("status", "sobraPorUnidade", "sobraPct", "sobraTotalNoMes")} == {
        "status": "amarelo",
        "sobraPorUnidade": "R$ 2,32",
        "sobraPct": "21,1%",
        "sobraTotalNoMes": "R$ 92,65",
    }


def test_simula_preco_com_prejuizo(sobrancelhas):
    r = dados(simulate_price(item_id=BUCO, new_price=8, tool_context=contexto_de_tool(sobrancelhas)))
    assert (r["status"], r["sobraPorUnidade"]) == ("vermelho", "-R$ 0,68")


def test_simula_sem_valor_da_hora_fica_incompleto(sobrancelhas):
    sobrancelhas["valorHora"] = None
    r = dados(simulate_price(item_id=BUCO, new_price=15, tool_context=contexto_de_tool(sobrancelhas)))
    assert r["status"] == "incompleto"


@pytest.mark.parametrize("item_id, preco", [("nao-existe", 10), (BUCO, 0), (BUCO, -5)])
def test_simula_item_inexistente_ou_preco_invalido_e_erro(sobrancelhas, item_id, preco):
    r = simulate_price(item_id=item_id, new_price=preco, tool_context=contexto_de_tool(sobrancelhas))
    assert r["status"] == "error"


# --- compare_items (eval real: o modelo comparou de cabeça e errou a ordem) ---


@pytest.mark.parametrize(
    "criterio, esperado",
    [
        (
            "sobra_por_hora",
            [
                ("Troca de câmara (performance)", "R$ 61,22 por hora"),
                ("Revisão completa", "R$ 32,56 por hora"),
                ("Troca de câmara (comum)", "-R$ 1,78 por hora"),
            ],
        ),
        (
            "sobra_no_mes",
            [
                ("Revisão completa", "R$ 1.953,49 no mês"),
                ("Troca de câmara (performance)", "R$ 255,10 no mês"),
                ("Troca de câmara (comum)", "-R$ 17,75 no mês"),
            ],
        ),
        (
            "sobra_pct",
            [
                ("Revisão completa", "40,7% do preço"),
                ("Troca de câmara (performance)", "24,3% do preço"),
                ("Troca de câmara (comum)", "-1,5% do preço"),
            ],
        ),
    ],
)
def test_compara_itens_do_maior_para_o_menor(bicicletas, criterio, esperado):
    r = dados(compare_items(criterion=criterio, tool_context=contexto_de_tool(bicicletas)))
    assert [(linha["item"], linha["valor"]) for linha in r["ranking"]] == esperado


def test_comparacao_por_hora_ignora_item_sem_tempo(bicicletas):
    bicicletas["itens"][0]["sobraPorHora"] = None
    r = dados(compare_items(criterion="sobra_por_hora", tool_context=contexto_de_tool(bicicletas)))
    assert bicicletas["itens"][0]["nome"] not in [linha["item"] for linha in r["ranking"]]


# --- hourly_rate ---


def test_valor_da_hora_com_a_conta(sobrancelhas):
    r = hourly_rate(monthly_income=3000, weekly_hours=40)
    assert r["status"] == "success"
    assert (dados(r)["valorHora"], dados(r)["valorHoraTexto"]) == (17.31, "R$ 17,31")
    assert "173,33" in dados(r)["conta"]


@pytest.mark.parametrize("renda, horas", [(3000, 0), (3000, 113), (0, 40), (-10, 40)])
def test_valor_da_hora_recusa_entrada_invalida(renda, horas):
    assert hourly_rate(monthly_income=renda, weekly_hours=horas)["status"] == "error"


# --- propose_change ---


def test_proposta_de_preco_vai_para_o_estado(sobrancelhas):
    ctx = contexto_de_tool(sobrancelhas)
    r = propose_change(kind="preco", value=12.4567, reason="Mantém a meta", item_id=BUCO, tool_context=ctx)
    assert r["status"] == "success"
    assert ctx.agent.state.get("propostas") == [
        {"tipo": "preco", "valor": 12.46, "motivo": "Mantém a meta", "itemId": BUCO, "horasSemana": None}
    ]


def test_proposta_de_hora_usa_horas_da_ficha(sobrancelhas):
    ctx = contexto_de_tool(sobrancelhas)
    propose_change(kind="valor_hora", value=17.31, reason="Pela renda desejada", tool_context=ctx)
    assert ctx.agent.state.get("propostas")[0]["horasSemana"] == 40


def test_proposta_repetida_substitui_a_anterior(sobrancelhas):
    ctx = contexto_de_tool(sobrancelhas)
    propose_change(kind="preco", value=12.41, reason="a", item_id=BUCO, tool_context=ctx)
    propose_change(kind="preco", value=13, reason="b", item_id=BUCO, tool_context=ctx)
    assert [p["valor"] for p in ctx.agent.state.get("propostas")] == [13]


def test_no_maximo_tres_propostas(bicicletas):
    ctx = contexto_de_tool(bicicletas)
    for item in bicicletas["itens"]:
        propose_change(kind="preco", value=50, reason="x", item_id=item["id"], tool_context=ctx)
    r = propose_change(kind="valor_hora", value=25, reason="x", tool_context=ctx)
    assert r["status"] == "error"
    assert len(ctx.agent.state.get("propostas")) == 3


@pytest.mark.parametrize(
    "ajuste, kwargs",
    [
        (lambda f: None, {"kind": "preco", "value": 12, "item_id": "nao-existe"}),
        (lambda f: f.update(valorHora=None), {"kind": "preco", "value": 12, "item_id": BUCO}),
        (lambda f: f["itens"][1].update(status="incompleto"), {"kind": "preco", "value": 12, "item_id": BUCO}),
        (lambda f: None, {"kind": "preco", "value": 0, "item_id": BUCO}),
        (lambda f: None, {"kind": "preco", "value": 12}),
        (lambda f: None, {"kind": "valor_hora", "value": 20, "weekly_hours": 200}),
    ],
)
def test_proposta_recusada_nao_entra_no_estado(sobrancelhas, ajuste, kwargs):
    ajuste(sobrancelhas)
    ctx = contexto_de_tool(sobrancelhas)
    r = propose_change(reason="x", tool_context=ctx, **kwargs)
    assert r["status"] == "error"
    assert ctx.agent.state.get("propostas") == []


# --- show_tip ---


def test_dica_vira_acao_do_app(sobrancelhas):
    ctx = contexto_de_tool(sobrancelhas)
    show_tip(tip_id="falta-deslocamento", tool_context=ctx)
    show_tip(tip_id="falta-deslocamento", tool_context=ctx)
    assert ctx.agent.state.get("acoes") == [{"label": "Lançar despesa", "to": "/despesas"}]


def test_dica_desconhecida_ou_sem_acao_e_erro(sobrancelhas):
    sobrancelhas["dicas"].append({"id": "sem-acao", "nivel": "dica", "titulo": "t", "texto": "x"})
    ctx = contexto_de_tool(sobrancelhas)
    assert show_tip(tip_id="inventada", tool_context=ctx)["status"] == "error"
    assert show_tip(tip_id="sem-acao", tool_context=ctx)["status"] == "error"
    assert ctx.agent.state.get("acoes") == []
