"""Contrato da API. O PWA monta o `contexto` com o montarContexto do README.

Campos que não estão declarados aqui são descartados pelo Pydantic e não chegam à IA (RNF06).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Reais = Annotated[float, Field(ge=-1e10, le=1e10, allow_inf_nan=False)]
Num = Annotated[float, Field(ge=0, le=1e10, allow_inf_nan=False)]


class Partes(BaseModel):
    material: Reais
    trabalho: Reais
    despesas: Reais
    perdas: Reais


class Insumo(BaseModel):
    nome: str = Field(max_length=80)
    porUnidade: Reais


class Item(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    nome: str = Field(min_length=1, max_length=80)
    preco: Reais
    custoTotal: Reais
    partes: Partes
    precoMinimo: Reais
    precoIdeal: Reais
    sobra: Reais
    sobraPct: Reais
    sobraPorHora: Reais | None = None
    minutos: Num
    status: Literal["incompleto", "vermelho", "amarelo", "verde"]
    vendasMes: Num
    sobraMes: Reais
    faltando: list[Annotated[str, Field(max_length=120)]] = Field(default=[], max_length=6)
    explicacao: list[Annotated[str, Field(max_length=400)]] = Field(default=[], max_length=8)
    insumosMaisCaros: list[Insumo] = Field(default=[], max_length=3)


class Acao(BaseModel):
    label: str = Field(max_length=40)
    # só rotas internas do app: "//host" seria tratado como URL externa pelo React Router
    to: str = Field(max_length=120, pattern=r"^/([A-Za-z0-9_?=&-][A-Za-z0-9/_?=&-]*)?$")


class Dica(BaseModel):
    id: str = Field(max_length=80)
    nivel: Literal["alerta", "dica"]
    titulo: str = Field(max_length=120)
    texto: str = Field(max_length=600)
    acao: Acao | None = None


class Despesa(BaseModel):
    categoria: str = Field(max_length=60)
    valor: Num


class Ferramenta(BaseModel):
    nome: str = Field(max_length=80)
    porMes: Num


class Despesas(BaseModel):
    porMes: Num
    ferramentasPorMes: Num
    totalPorMes: Num
    porHora: Num
    horasMes: Num
    lista: list[Despesa] = Field(default=[], max_length=50)
    ferramentas: list[Ferramenta] = Field(default=[], max_length=50)


class Resumo(BaseModel):
    sobraMesTotal: Reais
    horasOcupadasMes: Num


class Contexto(BaseModel):
    tipo: Literal["servico", "producao"]
    valorHora: Num | None = None
    horasSemana: float = Field(ge=0, le=112, allow_inf_nan=False)
    metaSobraPct: float = Field(ge=0, le=90, allow_inf_nan=False)
    despesas: Despesas
    resumo: Resumo
    itens: list[Item] = Field(max_length=50)
    dicas: list[Dica] = Field(default=[], max_length=40)


class Mensagem(BaseModel):
    papel: Literal["usuario", "assistente"]
    texto: str = Field(min_length=1, max_length=2000)


class PedidoChat(BaseModel):
    # O aceite do envio dos dados à IA fica no termo de uso do cadastro (decisão da equipe sobre o RNF06)
    contexto: Contexto
    historico: list[Mensagem] = Field(default=[], max_length=6)
    pergunta: str = Field(min_length=1, max_length=500)


class Proposta(BaseModel):
    tipo: Literal["preco", "valor_hora"]
    valor: float
    motivo: str
    itemId: str | None = None
    horasSemana: float | None = None


class RespostaChat(BaseModel):
    resposta: str
    propostas: list[Proposta] = []
    acoes: list[Acao] = []
