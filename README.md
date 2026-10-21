# agent-scratch

Arquetipo de un agente conversacional bancario (Banco Demo, ficticio) organizado en tres capas.
Cada semana del workshop agrega un incremento a este mismo agente hasta la v1.0.

## Requisitos

- Python 3.12 y [uv](https://docs.astral.sh/uv/)
- Docker Desktop (para correr en contenedor y publicar en ACR)
- Acceso a un recurso de Microsoft Foundry con un deployment de `gpt-5-mini` (salvo el día 1, que usa el mock)

## Configuración

```bash
copy .env.example .env
```

| Variable | Valor |
|---|---|
| `FOUNDRY_ENDPOINT` | `https://<tu-recurso>.openai.azure.com` |
| `FOUNDRY_DEPLOYMENT` | nombre del deployment en Foundry |
| `FOUNDRY_AUTH_PROVIDER` | `api_key` o `entra_id` |
| `FOUNDRY_API_KEY` | la key del recurso (solo con `api_key`) |

Con `entra_id` se usa `DefaultAzureCredential`: en local toma tu `az login` y desplegado la Managed Identity.
Requiere el rol **Cognitive Services OpenAI User** en el recurso.

## Arranque

Todas las formas dan el mismo agente en http://127.0.0.1:8000 (Swagger en `/docs`, smoke test en `/health`).

### 1. Local con uv

```bash
uv sync
uv run uvicorn agent.infrastructure.bootstrap:create_app --factory --reload
uv run pytest
```

**Día 1 sin Azure (mock):** en otra terminal levanta el Foundry simulado y en `.env` pon
`FOUNDRY_ENDPOINT=http://127.0.0.1:8100` y cualquier `FOUNDRY_API_KEY`.

```bash
uv run python dev/mock_foundry.py
```

### 2. Docker manual

Construir las imágenes (contexto = raíz del repo):

```bash
docker build -f devops/Dockerfile --target test -t agent:test .
docker build -f devops/Dockerfile --target runtime -t agent:local .
```

Tests dentro del contenedor:

```bash
docker run --rm agent:test
```

Agente contra Foundry real, con las variables de `.env`:

```bash
docker run --rm -p 8000:8000 --env-file .env agent:local
```

En un contenedor local no hay `az login`: usa `FOUNDRY_AUTH_PROVIDER=api_key`. `entra_id` aplica al desplegarlo con Managed Identity.

**Día 1 sin Azure (mock):** mock y agente en una red de Docker.

```bash
docker network create agent-net
docker run -d --rm --name mock-foundry --network agent-net -e MOCK_HOST=0.0.0.0 agent:test python dev/mock_foundry.py
docker run --rm -p 8000:8000 --network agent-net -e FOUNDRY_ENDPOINT=http://mock-foundry:8100 -e FOUNDRY_API_KEY=fake-token agent:local
```

Al terminar: `docker stop mock-foundry` y `docker network rm agent-net`.

### 3. Docker compose

```bash
docker compose -f devops/compose.yaml up --build agent
docker compose -f devops/compose.yaml run --rm --build tests
```

**Día 1 sin Azure (mock):** se suma el overlay `compose.mock.yaml`, que levanta el mock y apunta el agente a él.

```bash
docker compose -f devops/compose.yaml -f devops/compose.mock.yaml up --build agent
```

`tests` está en un profile, por eso lleva `--build`: `compose build` no lo reconstruye solo.

### 4. Publicar en Azure Container Registry

```bash
az acr login --name <acr>
docker build -f devops/Dockerfile --target runtime -t <acr>.azurecr.io/agent:<tag> .
docker push <acr>.azurecr.io/agent:<tag>
```

Esto es para una prueba puntual: el camino normal es el pipeline (ver [Deploy](#deploy)).
La imagen no lleva `.env`; en Azure la configuración llega como env vars de la Container App.

## devops/

| Archivo | Para qué |
|---|---|
| `Dockerfile` | multi-stage sobre `python:3.12-alpine`: `builder` (deps con uv) → `test` (pytest) / `runtime` (imagen para ACR: solo el venv, usuario no root, healthcheck en `/health`) |
| `Dockerfile.dockerignore` | exclusiones del contexto de build (BuildKit lo toma por estar junto al Dockerfile) |
| `compose.yaml` | agente contra Foundry real + servicio de tests |
| `compose.mock.yaml` | overlay del día 1 con el Foundry simulado |

## Deploy

`.github/workflows/deploy-agent.yaml`, en cada push a `main` / `solution` o tag `t*-v*`:

1. **test**: pytest dentro del stage `test` del Dockerfile (también en cada PR).
2. **deploy**: login a Azure por **OIDC** → build del stage `runtime` → push a ACR → `az containerapp update` con la imagen nueva y sus env vars.

Si la variable `ACR_NAME` no está definida, solo corre **test**.

### Dónde vive cada cosa

| Contexto | Qué | Dónde | Quién lo define |
|---|---|---|---|
| Local | `FOUNDRY_*`, key de pruebas | `.env` (no se versiona) | cada participante |
| CI | IDs para OIDC y nombres de recursos (no son secretos) | GitHub → Settings → Secrets and variables → Actions → **Variables** | plataforma, una vez |
| Azure | configuración no secreta (`FOUNDRY_ENDPOINT`, …) | env vars de la Container App | el pipeline, en cada deploy |
| Azure | **secretos** (p. ej. `FOUNDRY_API_KEY`) | **Key Vault** → secret de la Container App que referencia a Key Vault → env var `secretref:` | plataforma, una vez |

**GitHub Secrets queda vacío.** OIDC no usa contraseñas, y el valor de una key nunca pasa por el pipeline:
el workflow solo conoce la URI del secret en Key Vault, y la Container App lo lee con su Managed Identity.
Rotar la key es cambiarla en Key Vault; no requiere tocar el repo ni la imagen.

Con `FOUNDRY_AUTH_PROVIDER=entra_id` (recomendado) no hay ningún secret: la Managed Identity entra directo a Foundry.

### Variables del repo en GitHub

| Variable | Valor |
|---|---|
| `AZURE_CLIENT_ID` | client id de la app registration de CI (credencial federada) |
| `AZURE_TENANT_ID` | tenant de Entra ID |
| `AZURE_SUBSCRIPTION_ID` | suscripción del sandbox |
| `ACR_NAME` | nombre del Azure Container Registry, sin `.azurecr.io` (p. ej. `acrworkshop`) |
| `IMAGE_REPOSITORY` | repositorio del equipo dentro del ACR (p. ej. `team-01/agent`); si no se define, `agent` |
| `RESOURCE_GROUP` | resource group del equipo (`rg-team-NN`) |
| `CONTAINER_APP` | Container App del agente |
| `FOUNDRY_ENDPOINT` | `https://<recurso>.openai.azure.com` |
| `FOUNDRY_DEPLOYMENT` | deployment del modelo, p. ej. `gpt-5-mini` |
| `FOUNDRY_AUTH_PROVIDER` | `entra_id` (recomendado) o `api_key` |
| `APP_IDENTITY_CLIENT_ID` | client id de la Managed Identity del equipo; llega al contenedor como `AZURE_CLIENT_ID` |
| `APP_IDENTITY_ID` | resource id de esa Managed Identity (solo con `api_key`) |
| `FOUNDRY_API_KEY_KV_URI` | `https://<kv>.vault.azure.net/secrets/foundry-api-key` (solo con `api_key`) |

### Setup único (plataforma, antes de la semana 1)

1. **CI → Azure (OIDC):** app registration con credencial federada para el subject
   `repo:<owner>/<repo>:environment:sandbox`, y environment `sandbox` creado en GitHub.
   Roles: **AcrPush** en el ACR y **Contributor** solo en `rg-team-NN`.
2. **Container App → Azure (Managed Identity del equipo):** asignada a la Container App, con
   **Cognitive Services OpenAI User** en Foundry y **AcrPull** en el ACR (`az containerapp registry set --identity ...`).
3. **Solo si Foundry usa `api_key`:** guardar la key una vez en Key Vault (portal o `az keyvault secret set ... --file`,
   para que el valor no quede en el historial de la terminal) y dar **Key Vault Secrets User** a la Managed Identity.

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

## Ramas y tags

- `main`: este arquetipo.
- `solution`: solución de referencia, con un tag por semana: `t1-v0.1`, `t2-v0.2`, …
- `git diff main t1-v0.1` muestra lo que se construye en la semana 1.
