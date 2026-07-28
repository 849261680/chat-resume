# Chat Resume 

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUh0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/849261680/chat-resume)

Chat Resume es un centro de trabajo para la búsqueda de empleo impulsado por IA que demuestra capacidades de ingeniería de Agentes: desde la carga del currículum y el análisis de la descripción del puesto (JD), el llamado a herramientas estructuradas y la modificación mediante diffs confirmados por el usuario, hasta la exportación y simulaciones de entrevistas por voz, creando un ciclo completo de búsqueda de empleo.

- Runtime ReAct impulsado por OpenAI Agents SDK
- Tool calling estructurado
- Puerta de confirmación de diffs Human-in-the-loop
- Eventos de herramientas en streaming via SSE
- Reproducción / reanudación de sesiones
- Evaluación de Agentes (Agent eval)
- Observabilidad de Agentes

## Capacidades Principales

- Análisis de currículum cargado: Soporta PDF, DOC, DOCX, TXT; genera un currículum estructurado tras el análisis en el backend.
- Centro de edición de currículum: Edición estructurada, vista previa en tiempo real, guardado automático, configuración de diseño, adaptación a una página y exportación.
- Gestión de JD: Guarda la empresa objetivo, el puesto objetivo y el texto de la JD, con soporte para OCR de imágenes de JD.
- Resume Agent: Realiza llamadas a herramientas estilo ReAct basadas en el currículum actual, la JD objetivo y el contexto de la conversación.
- Reescritura confirmada por el usuario: Todas las herramientas de modificación muestran primero un diff; los cambios se escriben en el currículum solo tras la confirmación del usuario.
- Resumen de coincidencia de JD: Una misma herramienta devuelve palabras clave coincidentes, palabras clave faltantes, cambios confirmados, sugerencias de hechos a completar y los principales gaps (Top gaps) a reforzar prioritariamente.
- Simulación de entrevista: Crea sesiones de entrevista por voz basadas en el currículum y el puesto objetivo, guardando las respuestas y generando reportes.
- Agent eval: Proporciona casos de prueba y scripts de calificación para verificar la mejora de palabras clave, la corrección de las llamadas a herramientas y las reglas de decisión.

## Flujo Principal del Usuario

```text
Carga/Creación de currículum
  -> Edición estructurada
  -> Llenado o reconocimiento de JD
  -> Análisis de coincidencia del Resume Agent
  -> Llamada a herramientas para generar resumen de coincidencia / Top gaps / diff de modificaciones
  -> Aplicación de cambios tras confirmación del usuario
  -> Vista previa, adaptación a una página, exportación
  -> Inicio de simulación de entrevista basada en el currículum
```

## ¿Por qué es un sistema de Agentes?

El LLM no puede modificar directamente los datos del currículum, solo puede proponer cambios estructurados a través de herramientas restringidas.

```text
Observe (Observar)
  -> Lee el currículum actual, la JD objetivo, el historial de chat y los diffs confirmados
Reason (Razonar)
  -> Determina si el usuario quiere consultar, analizar la coincidencia o modificar el currículum
Act (Actuar)
  -> Llama a herramientas de análisis de solo lectura o herramientas de modificación
Confirm (Confirmar)
  -> Las herramientas de modificación se ejecutan primero en un contexto de vista previa, generando un diff que espera la confirmación del usuario
Persist (Persistir)
  -> Tras la confirmación del usuario, se ejecuta sobre el resume_content real y se escribe en la base de datos
Replay (Reproducir)
  -> Si la conexión SSE se interrumpe, se puede reproducir y recuperar mediante el cursor de eventos de sesión
```

La salida del Agente no es una "afirmación en lenguaje natural de que se ha modificado". El contenido del currículum solo se escribe si la llamada a la herramienta es exitosa y pasa por la puerta de confirmación.

## Herramientas del Agente

Las herramientas del Resume Agent se dividen actualmente en dos categorías: análisis de solo lectura y modificaciones de escritura.

Las herramientas de solo lectura se ejecutan automáticamente:

- `generate_job_match_summary`: Genera un resumen de coincidencia del puesto, devolviendo `matched_keywords`, `missing_keywords`, `resume_changes`, `fact_gaps` y `top_gaps`.

Las herramientas de modificación requieren confirmación del usuario:

- `update_summary`: Actualiza el resumen personal, ajustando el posicionamiento profesional y el resumen de capacidades principales de todo el currículum.
- `update_profile`: Actualiza el objetivo laboral, headline, ubicación y enlaces públicos en la información personal; no modifica nombre, correo electrónico ni teléfono.
- `upsert_job_application`: Crea o actualiza la empresa objetivo, el puesto objetivo y la JD.
- `update_item_fields`: Actualiza campos que no son bullet points en entradas de trabajo, proyectos o educación (ej. puesto, descripción del proyecto, rol, stack tecnológico, campo de grado académico).
- `update_skills`: Actualiza los nombres de las categorías de habilidades y la lista de habilidades, permitiendo reemplazo o fusión.
- `add_resume_item`: Agrega nuevas entradas de trabajo, proyecto, educación, habilidad, idioma o entradas personalizadas; requiere que el usuario proporcione una fuente de hechos clara.
- `remove_resume_item`: Elimina entradas existentes de trabajo, proyecto, educación, habilidad, idioma o personalizadas.
- `update_overview`: Actualiza la descripción general de un proyecto.
- `update_bullet`: Actualiza un punto (bullet point) existente.
- `add_bullet`: Agrega un nuevo punto.
- `remove_bullet`: Elimina un punto.

Cada herramienta de modificación devuelve un diff estructurado que incluye el estado antes, después y la razón del cambio. El frontend muestra una tarjeta de confirmación y los cambios se aplican al currículum solo si el usuario los acepta.

## Límites de la capacidad de coincidencia de JD

La coincidencia de JD actual es una consolidación ligera de palabras clave, cadenas de evidencia y brechas de capacidad; no es un modelo de coincidencia semántica completa.

Lo que hace:

- Extrae palabras clave en chino e inglés de la JD.
- Tras excluir los campos de la JD, determina coincidencias y faltantes en el cuerpo del currículum.
- Resume los diffs confirmados en la sesión actual, indicando qué expresiones se han reforzado.
- Agrupa palabras clave faltantes dispersas en 2-3 brechas de capacidad, por ejemplo: experiencia en implementación de RAG, llamadas a herramientas de Agente y orquestación de flujos de trabajo, experiencia en infraestructura de ingeniería.

Lo que NO hace actualmente:

- Demostrar que el usuario realmente posee una capacidad faltante.
- Inventar experiencias que no tengan evidencia en el currículum.

## Reliability and eval (Fiabilidad y Evaluación)

El proyecto incluye tres capas de verificación:

- Pruebas de backend que cubren los límites del runtime, recuperación de sesiones, ejecución de herramientas, cursor SSE y resúmenes de coincidencia de puestos.
- Playwright en el frontend que cubre la carga, el flujo de trabajo del editor, la confirmación de diffs, la exportación, la autenticación, el dashboard, i18n y el flujo de entrevistas.
- Herramientas de calificación de Agent eval que cubren la corrección de llamadas a herramientas, reglas de decisión "optimize-first", mejora de palabras clave de JD y un LLM-as-judge opcional.

Resultados de la última validación local:

```text
backend basedpyright: passed
backend key tests: 128 passed
frontend type-check: passed
frontend build: passed
frontend e2e: 55 passed
```

## Arquitectura del Sistema

```text
Frontend (Next.js / React)
  -> FastAPI HTTP API
  -> ResumeAgentStreamService
  -> OpenAI Agents SDK ResumeAgentRuntime
  -> Resume Tools
  -> Tool Confirmation Gate
  -> ResumeService / AgentSessionStore
  -> Database
```

## Stack Tecnológico

- Frontend: Next.js 16.2, React 18, TypeScript, Tailwind CSS, next-intl
- Backend: FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, uv
- Agente: OpenAI Agents SDK
- Voz: Diálogo de voz en tiempo real de Volcengine
- Pruebas: pytest, Playwright

## Directorios Principales

```text
backend/app/entrypoints/http/  # Rutas de FastAPI
backend/app/agents/resume/     # Definición del Agente de currículum y contexto de prompts
backend/app/runtime/           # Adaptación del runtime de OpenAI Agents SDK, confirmaciones y recuperación
backend/app/tools/resume/      # Herramientas de currículum
backend/app/services/          # Servicios de negocio
backend/app/state/             # Almacenamiento de sesión del Agente y reproducción de SSE
frontend/src/app/              # Páginas de Next.js
frontend/src/components/       # Componentes de frontend
frontend/src/hooks/            # Hooks de negocio a nivel de página
frontend/src/i18n/             # Configuración de internacionalización
frontend/locales/              # Archivos de traducción chino e inglés
eval/                          # Scripts y casos de prueba de Agent eval
```

## Inicio Local

Requisitos:

- Python 3.11+
- Node.js 18+
- uv
- npm

Iniciar frontend y backend:

```bash
./restart.sh
```

Direcciones predeterminadas:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

Inicio individual:

```bash
./backend.sh
./frontend.sh
```

## Variables de Entorno

Archivos de ejemplo:

- `backend/.env.example`
- `frontend/.env.example`

Mínimos necesarios para local:

```bash
# backend/.env
DATABASE_URL=sqlite:///./chat_resume.db
SECRET_KEY=your-secret-key-here
OPENAI_AGENTS_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_AGENTS_MODEL=gpt-5.5
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_THINKING_TYPE=disabled
OPENROUTER_API_KEY=
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL=deepseek/deepseek-v4-pro
OPENROUTER_JOB_MATCH_MODEL=deepseek/deepseek-v4-pro
OPENROUTER_RESUME_PARSER_MODEL=deepseek/deepseek-v4-pro
FRONTEND_URL=http://localhost:3000
BACKEND_CORS_ORIGINS=http://localhost:3000,https://localhost:3000

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Al cambiar el Agente de optimización de currículum a la API oficial de DeepSeek, configure `OPENAI_AGENTS_PROVIDER=deepseek`, `OPENAI_AGENTS_MODEL=deepseek-v4-pro` y complete `DEEPSEEK_API_KEY`. Esta rama utiliza Chat Completions compatible con OpenAI, con `DEEPSEEK_THINKING_TYPE=disabled` por defecto para evitar errores de reproducción de `reasoning_content` después de la confirmación de herramientas.

### Evaluación del Agente

La evaluación del Resume Agent mantiene el método de ejecución local en `eval/` y, al mismo tiempo, produce artefactos compatibles con el estándar de OpenAI Agents SDK:

- `openai_agents_eval.trace`: Escribe el `RunConfig.workflow_name`, `trace_id`, `group_id` y metadatos del SDK; permite la localización en Traces cuando se utiliza un proveedor real de OpenAI.
- `openai_agents_eval.dataset_item`: Convierte los casos locales al formato de item de dataset, incluyendo entrada, decisión esperada, herramienta esperada, palabras clave y contenido prohibido.
- `openai_agents_eval.model_sample`: Convierte las respuestas del Agente, llamadas a herramientas y el estado final del currículum en una muestra para el evaluador (grader sample).
- `openai_agents_eval.grader`: Proporciona la configuración del grader de Python de OpenAI para calificar decisiones, llamadas a herramientas, palabras clave, contenido prohibido y formato de respuesta.

Evaluación normal:

```bash
cd backend
uv run python ../eval/run_eval.py --cases TC001 --output ../eval/results/latest.json
```

Ejemplo dorado de currículum excelente:

```bash
cd backend
uv run python ../eval/run_excellent_eval.py --cases excellent-002 --output ../eval/results/excellent_latest.json
```

El proveedor de OpenAI por defecto utiliza `OPENAI_API_KEY`; al cambiar a `OPENAI_AGENTS_PROVIDER=deepseek`, utiliza `DEEPSEEK_API_KEY`. La rama compatible con DeepSeek aún puede calificarse localmente, pero no subirá los traces a la plataforma de OpenAI.

Capacidades opcionales configurables según necesidad:

- Login de Google: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`
- Suscripción de PayPal: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_PLAN_ID`, `PAYPAL_WEBHOOK_ID`
- Entrevista de voz end-to-end de Doubao: `VOLCENGINE_DIALOGUE_*`, `VOLCENGINE_ACCESS_TOKEN`, `VOLCENGINE_TTS_*`

## Base de Datos

```bash
cd backend
uv run alembic upgrade head
```

## Pruebas

```bash
# Backend
cd backend
uv run --extra dev python -m pytest tests

# Type-check de frontend
cd frontend
npm run type-check

# Construcción de frontend
npm run build

# E2E
npm run e2e
```

## Diseño

Para las normas de diseño del frontend, vea [DESIGN.md](./DESIGN.md).
