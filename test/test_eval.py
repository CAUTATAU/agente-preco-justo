"""O verificador de números do eval precisa reprovar o erro real visto na Fase 0."""

import pytest

from conftest import carregar
from scripts.eval import custo_dolares, numeros_inventados


# Haiku 4.5 no perfil us., por milhão de tokens: entrada 1,10; gravar no cache 1,375 (1,25×); ler 0,11 (0,1×); saída 5,50
@pytest.mark.parametrize(
    "campo, esperado",
    [("inputTokens", 1.10), ("cacheWriteInputTokens", 1.375), ("cacheReadInputTokens", 0.11), ("outputTokens", 5.50)],
)
def test_custo_conta_cada_tipo_de_token(campo, esperado):
    uso = {"inputTokens": 0, "outputTokens": 0, "cacheWriteInputTokens": 0, "cacheReadInputTokens": 0, campo: 1_000_000}
    assert custo_dolares(uso) == pytest.approx(esperado)


def test_custo_sem_campos_de_cache():
    assert custo_dolares({"inputTokens": 1_000_000, "outputTokens": 0}) == pytest.approx(1.10)


def test_reprova_porcentagem_calculada_pelo_modelo():
    # Fase 0: a ficha diz "ocupam 32%"; o modelo respondeu "68% ociosa" (100 - 32)
    assert numeros_inventados("Sua jornada fica 68% ociosa.", carregar("sobrancelhas"), []) == ["% inventado: 68.0"]


def test_aceita_numeros_da_ficha_arredondados_para_exibir():
    resposta = "Cada buço custa R$ 8,68 e sobram R$ 6,32 (42%). No mês, R$ 252,65."
    assert numeros_inventados(resposta, carregar("sobrancelhas"), []) == []


def test_aceita_numeros_devolvidos_pela_ferramenta():
    tool = [{"status": "success", "content": [{"json": {"sobraPorUnidade": "R$ 2,32", "sobraPct": "21,1%"}}]}]
    assert numeros_inventados("Sobra R$ 2,32 (21,1%).", carregar("sobrancelhas"), tool) == []
