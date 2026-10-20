# agent-scratch

Arquetipo de un agente conversacional bancario (Banco Demo, ficticio) organizado en tres capas.
Cada semana del workshop agrega un incremento a este mismo agente hasta la v1.0.

## Setup

```bash
uv sync
copy .env.example .env                 # completar FOUNDRY_*
uv run python dev/mock_foundry.py      # opcional: Foundry simulado en :8100
uv run uvicorn agent.infrastructure.bootstrap:create_app --factory --reload
uv run pytest
```

Smoke test: http://127.0.0.1:8000/health

## Capas

```
src/agent/
├── domain/            reglas y contratos; no importa nada externo
│   ├── models.py      Intent, Message (+ AgentReply, Usage, AgentTurn)
│   ├── errors.py      fallas del agente
│   └── ports.py       interfaces: ChatModel, ConversationStore
├── application/       casos de uso; solo conocen los puertos
│   └── chat_service.py
└── infrastructure/    todo lo que toca el mundo exterior
    ├── api/           FastAPI (entrada HTTP)
    ├── llm/           ChatModel → Microsoft Foundry + credenciales api_key | entra_id
    ├── persistence/   ConversationStore → memoria
    ├── prompts/       system prompt por dominio
    ├── config/        settings (FOUNDRY_*)
    └── bootstrap.py   conecta cada puerto con su implementación
```

Regla: `infrastructure → application → domain`, nunca al revés.

| Tema | domain | application | infrastructure |
|---|---|---|---|
| T1 Conversa | `AgentReply`, `Usage`, `AgentError` | `ChatService` | `api/`, `llm/` Foundry, `persistence/` memoria |
| T2 Sabe | `Citation`, puerto `KnowledgeBase` | recuperar contexto | `search/` AI Search |
| T3 Actúa | `PendingAction`, puerto `ToolGateway` | `ApproveAction` | `mcp/`, Agent Framework en `llm/` |
| T4 Opera | — | — | Cosmos DB en `persistence/`, `telemetry/` |

## Semana 1 · T1 Conversa

Busca los `TODO S1` / `TODO S2` en el código.

**S1**
- [ ] `domain/models.py`: `AgentReply` como contrato del structured output
- [ ] `infrastructure/llm/credentials.py`: credencial según `FOUNDRY_AUTH_PROVIDER`
- [ ] `infrastructure/llm/foundry_chat_model.py`: `complete()` con `chat.completions.parse`
- [ ] `application/chat_service.py`: `handle()` con system prompt + historial + mensaje
- [ ] `infrastructure/api/`: `ChatRequest`, `ChatResponse` y `POST /chat`
- [ ] `infrastructure/bootstrap.py`: conectar todo

**S2**
- [ ] Historial por sesión, sin guardar turnos fallidos
- [ ] `domain/errors.py`: timeout, rate limit y salida inválida → HTTP 504 / 429 / 502
- [ ] `Usage`: latencia y tokens por turno

**Autónomo:** pytest con 5 conversaciones de prueba; latencia y tokens anotados aquí.

**Gate T1:** `/chat` responde con output válido, tests en verde y 2 trade-offs de modelo y costo explicados.

## Docker

`Dockerfile` multi-stage sobre `python:3.12-alpine`:

| Stage | Para qué | Contiene |
|---|---|---|
| `builder` | instalar dependencias con `uv` | venv de runtime |
| `test` | correr pytest en contenedor | venv + dev, `tests/`, `dev/` |
| `runtime` | imagen para ACR | solo el venv; usuario no root, healthcheck en `/health` |

```bash
docker compose run --rm tests          # pytest dentro del contenedor
docker compose up --build agent        # agente en :8000 contra el mock de Foundry
```

Publicar en Azure Container Registry:

```bash
az acr login --name <acr>
docker build --target runtime -t <acr>.azurecr.io/agent:<tag> .
docker push <acr>.azurecr.io/agent:<tag>
```

O construir directo en Azure, sin Docker local: `az acr build --registry <acr> --target runtime -t agent:<tag> .`

En producción las variables `FOUNDRY_*` llegan como env vars del contenedor (Container Apps), no por `.env`.

## Ramas y tags

- `main`: este arquetipo.
- `solution`: solución de referencia, con un tag por semana: `t1-v0.1`, `t2-v0.2`, …
- `git diff main t1-v0.1` muestra lo que se construye en la semana 1.
