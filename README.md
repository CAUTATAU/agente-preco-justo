# Agente Preço Justo

Assistente de IA do [Preço Justo](../pwa-preco-justo): responde perguntas em linguagem simples sobre a ficha de custos do microempreendedor (RF18, RF20, RF23) e sugere mudanças que **só valem depois do aceite da pessoa** (RF24).

O agente **não calcula preço**. Os números vêm do motor `calc.ts` e do consultor `advisor.ts` do PWA, que rodam offline. As ferramentas deste serviço só fazem contas pequenas e testadas: o semáforo de um preço novo, o valor da hora e a ordenação dos itens.

**Stack:** Python 3.13 · FastAPI · Strands Agents 1.60 · Claude Haiku 4.5 no Amazon Bedrock

```
PWA ──POST /api/agent/chat (JWT)──▶ backend Node ──POST /chat (X-Agent-Key, rede privada)──▶ este serviço ──▶ Bedrock
```

Este serviço não tem domínio público nem banco e não guarda nada entre perguntas. Login, limites de uso (5/min e 30/dia por pessoa, 100/dia no total) e o formato de erro para o PWA ficam no backend Node.

## Rodando localmente

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/python
cp .envexample .env      # preencha AGENT_KEY (32+ caracteres)
aws login                # credenciais do Bedrock; o botocore[crt] permite ao boto3 usar essa sessão
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --env-file .env
```

No backend Node, use `AGENT_URL=http://localhost:8000` e a mesma `AGENT_KEY`.

| Comando | O que faz |
| --- | --- |
| `.venv/Scripts/python -m pytest -q` | Testes (não chamam o Bedrock; também rodam no CI) |
| `.venv/Scripts/python scripts/eval.py` | 12 perguntas no Bedrock real (~US$ 0,10). Rode antes de mudar prompt, modelo ou parâmetros |
| `docker build -t agente-preco-justo .` | Imagem usada no Railway |

## Contrato da API

### `POST /chat` (chamado pelo Node; o PWA chama `POST /api/agent/chat` no Node)

Cabeçalhos: `X-Agent-Key: <AGENT_KEY>` e `Content-Type: application/json`. Sem a chave, a resposta é 403. Nunca é 401, para o PWA não deslogar a pessoa.

```jsonc
{
  "consentimento": true,          // a pessoa autorizou enviar a ficha (RNF06); false → 403
  "contexto": { ... },            // resumo já calculado pelo PWA: veja montarContexto abaixo
  "historico": [                  // até 6 mensagens anteriores, só texto
    { "papel": "usuario", "texto": "..." },
    { "papel": "assistente", "texto": "..." }
  ],
  "pergunta": "posso baixar o preço do buço?"   // 1 a 500 caracteres
}
```

Exemplos completos de `contexto`, gerados pelo `calc.ts`/`advisor.ts` reais, estão em [`test/fixtures/`](test/fixtures). Os modelos e os limites de cada campo estão em [`app/schemas.py`](app/schemas.py). Campos fora do contrato são descartados e não chegam à IA.

**Resposta 200:**

```jsonc
{
  "resposta": "Com **R$ 11,00**, sobram R$ 2,32 por atendimento (21,1%)...",  // texto; só **negrito** e linhas "- "
  "propostas": [   // até 3 cartões; nada muda sem o "Aceitar"
    { "tipo": "preco", "valor": 12.41, "motivo": "...", "itemId": "<id do item>", "horasSemana": null },
    { "tipo": "valor_hora", "valor": 17.31, "motivo": "...", "itemId": null, "horasSemana": 40 }
  ],
  "acoes": [ { "label": "Lançar despesa", "to": "/despesas" } ]   // botões das dicas do próprio app
}
```

**Erros:** sempre `{ "error": "mensagem em português" }`.

| HTTP | Quando |
| --- | --- |
| 400 | Corpo inválido ou fora dos limites |
| 403 | Sem `X-Agent-Key` válida ou sem consentimento |
| 503 | Bedrock fora, cota estourada (10 chamadas/min no Haiku 4.5) ou tempo esgotado (60 s) |

Se o modelo recusar a pergunta, a resposta é 200 com um texto amigável e sem propostas.

`GET /health` responde `{ "status": "ok" }` sem chave e sem chamar o modelo.

### Regras para o front (PWA)

1. Sem internet (`useOnline`), o chat fica desligado com um aviso; o resto do app continua funcionando.
2. Consentimento: chave desligada por padrão, pedida no primeiro uso do chat e repetida em Ajustes. Fica salva só no aparelho e nunca liga sozinha. O texto deve dizer que o resumo da ficha (nomes de itens e insumos e números, sem o nome do negócio) e as perguntas vão para a AWS (Amazon Bedrock, EUA).
3. Monte o `contexto` na hora da pergunta, com o `useCalc()` atual.
4. Cartão de proposta: mostre o "antes → depois" recalculado no `calc.ts`. No **Aceitar**, valide com `itemSchema` / `businessSchema` e só então chame `saveItem({...item, price: valor})` ou `setBusiness({...business, hourlyRate: valor, weeklyHours: horasSemana})`. Ignore a proposta se o `itemId` não existir mais.
5. Em `acoes`, só navegue se o `to` for igual ao `action.to` de uma dica do próprio app.
6. Mostre `resposta` como texto (nada de `dangerouslySetInnerHTML`), interpretando apenas `**negrito**` e linhas `- `.

### `montarContexto` (referência para o PWA)

```ts
// src/lib/agentContext.ts — o chat só aparece com business preenchido
import { type CalcResult, occupiedHours } from './calc'
import { type Tip, explainItem } from './advisor'
import type { AppData } from './schemas'

const r2 = (v: number) => Math.round(v * 100) / 100
const ordem = { vermelho: 0, amarelo: 1, incompleto: 2, verde: 3 }

export function montarContexto(data: AppData, calc: CalcResult, tips: Tip[]) {
  const b = data.business!, o = calc.overhead
  return {
    tipo: b.type, valorHora: b.hourlyRate, horasSemana: b.weeklyHours, metaSobraPct: b.targetMargin,
    despesas: { porMes: r2(o.expensesMonthly), ferramentasPorMes: r2(o.toolsMonthly), totalPorMes: r2(o.totalMonthly),
      porHora: r2(o.perHour), horasMes: r2(o.monthlyHours),
      lista: data.expenses.slice(0, 50).map((e) => ({ categoria: e.category, valor: e.amount })),   // sem description (texto livre)
      ferramentas: data.tools.slice(0, 50).map((t) => ({ nome: t.name, porMes: r2(t.everyMonths > 0 ? t.cost / t.everyMonths : 0) })) },
    resumo: { sobraMesTotal: r2(calc.items.reduce((s, c) => s + c.monthlyProfit, 0)), horasOcupadasMes: r2(occupiedHours(data)) },
    itens: [...calc.items].sort((a, b) => ordem[a.status] - ordem[b.status]).slice(0, 50).map((c) => ({
      id: c.item.id, nome: c.item.name, preco: c.price, custoTotal: c.total,   // sem arredondar: paridade do semáforo
      partes: { material: r2(c.material), trabalho: r2(c.labor), despesas: r2(c.fixed), perdas: r2(c.loss) },
      precoMinimo: c.minPrice, precoIdeal: c.idealPrice, sobra: r2(c.profit), sobraPct: Math.round(c.margin * 1000) / 10,
      sobraPorHora: c.hoursPerUnit > 0 ? r2(c.profit / c.hoursPerUnit) : null, minutos: r2(c.hoursPerUnit * 60),
      status: c.status, vendasMes: c.item.monthlyVolume, sobraMes: r2(c.monthlyProfit), faltando: c.missing,
      explicacao: explainItem(c, data),
      insumosMaisCaros: [...c.materialLines].sort((a, b) => b.perUnit - a.perUnit).slice(0, 3)
        .map((l) => ({ nome: l.name, porUnidade: r2(l.perUnit) })),
    })),
    dicas: tips.filter((t) => !data.dismissedTips.includes(t.id)).slice(0, 40)
      .map((t) => ({ id: t.id, nivel: t.level, titulo: t.title, texto: t.text, acao: t.action })),
  }
}
```

## Deploy no Railway

Este serviço fica no mesmo projeto do backend Node e do Postgres, **sem domínio público**. Healthcheck em `/health`.

| Variável | Valor |
| --- | --- |
| `PORT` | `8000` (o Node chama `http://${{agente.RAILWAY_PRIVATE_DOMAIN}}:8000`) |
| `AGENT_KEY` | Mesmo valor do serviço Node, **selado** |
| `AWS_REGION` | `us-east-1` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Usuário IAM só do agente (`bedrock:InvokeModel*` no perfil `us.` do Haiku 4.5), **selados** |
| `MODEL_ID` | Opcional; padrão `us.anthropic.claude-haiku-4-5-20251001-v1:0` |

## Custo

- **Cache de prompt ligado** (`CacheConfig(strategy="auto")`). O prefixo (prompt + ferramentas + ficha) tem ~5,2 mil tokens, acima do mínimo de 4.096 do Haiku 4.5. A 2ª chamada do loop de ferramentas lê do cache.
- **Por pergunta, medido em 2026-10-14:**

  | Tipo de pergunta | Custo |
  | --- | --- |
  | Com ferramenta | ~US$ 0,009 (sem cache: ~US$ 0,013) |
  | Repetida em até 5 min | ~US$ 0,002 |
  | Só uma chamada | ~US$ 0,001 a mais (paga a gravação no cache) |

- **`max_tokens=2000`** é só um teto. Paga-se o que é gerado, e as respostas medidas ficaram entre 180 e 260 tokens.
- **O log de cada pedido** mostra `cache_write` e `cache_read`, para acompanhar se o cache está funcionando.

## Limitações conhecidas

- **Prolixo:** o Haiku 4.5 às vezes passa do limite de 5 frases, principalmente quando ajuda a calcular a hora. Nos últimos evals, 11 de 12 casos passaram; o caso que falha muda entre rodadas.
- **Atribuição de custo:** o modelo pode ligar um número certo da ficha ao custo errado. Exemplo visto: atribuiu ao gás os R$ 60 da conta de luz. O eval confere se o número existe, não a que custo ele se refere.
- **Cota do Bedrock:** 10 chamadas/min ao Haiku 4.5 (1 a 3 por pergunta). Em throttling o agente tenta de novo por até ~20 s e depois responde 503.
- **Ainda não testado:** uma recusa de segurança real (`content_filtered`) e a política IAM mínima, que depende do usuário IAM existir.
- **Haiku 5.5:** está no Bedrock e custa ~10× menos, mas o acesso é liberado por conta. Para migrar: `MODEL_ID=global.anthropic.claude-haiku-5-5`, tirar `temperature` e usar `additional_request_fields={"output_config": {"effort": "low"}}`. O cache continua funcionando, porque o mínimo do 5.5 é de 512 tokens. Depois, rodar o eval.
