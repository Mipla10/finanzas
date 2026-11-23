# AGENTS.md — finanzas

## Proyecto
App de finanzas personales para uso propio, compartible con conocidos
(multiusuario por diseño), y portafolio de ciencia de datos. Reemplaza una plantilla de Excel: registrar un gasto debe tomar
segundos. Tiene tres partes:
- **Backend** (FastAPI + PostgreSQL): cuentas, movimientos, saldos,
  categorías, reportes y webhook de WhatsApp.
- **Web** (React + Vite, PWA mobile-first): registro rápido, movimientos,
  saldos y reportes.
- **Agente de WhatsApp**: cada número de teléfono se asocia a un
  usuario. Un LLM extrae monto, tipo, cuenta, comercio y
  categoría de un mensaje en lenguaje natural y pide confirmación antes
  de guardar.

Cuentas: Lulo Bank (principal + bolsillos, uno de ahorro con
rendimientos), Nequi y efectivo. Tipos de movimiento: gasto, ingreso,
transferencia entre cuentas propias, rendimiento y ajuste de saldo.

Los principios no negociables están en `docs/constitution.md`.

## Roadmap de specs
Cada spec entrega una versión funcional de punta a punta.

| Spec | Versión | Alcance |
|------|---------|---------|
| 001 | Núcleo | Cuentas, movimientos, saldos, categorías. API + BD + tests. Toda entidad con dueño. |
| 002 | Web | App responsive/PWA: registro rápido, lista de movimientos, saldos. |
| 003 | Reportes | Gasto por categoría, mes a mes, presupuesto vs. real. |
| 004 | Usuarios | Registro de usuarios, autenticación y aislamiento verificado entre usuarios. |
| 005 | WhatsApp | Agente con LLM y confirmación; número de teléfono ↔ usuario. El backend pasa a Railway. |
| 006 | Importar | Historial desde mi plantilla de Excel. |
| 007 | Conciliación | Extractos PDF (Nequi, Lulo), solo para conciliar. |
| 008 | ML | Sugerencia de categorías e insights. |

## Stack
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (tipado),
  Alembic, uv, Ruff, pytest (+ pytest-cov).
- **Frontend:** React + Vite + TypeScript, PWA, Vitest, Playwright (E2E).
- **BD:** PostgreSQL (Neon en producción, Docker en local).
- **Despliegue:** Docker Compose en local. Producción: frontend en Vercel,
  BD en Neon, backend en Render free (specs 001–004) y en Railway Hobby
  desde la 005.
- **Integraciones (spec 005):** WhatsApp Cloud API de Meta y un LLM en la
  nube con salida estructurada validada con Pydantic, detrás de una
  interfaz intercambiable.

## Estructura de carpetas
```
.
├── AGENTS.md
├── README.md
├── docker-compose.yml         # api + postgres (+ web) en local
├── .env.example               # variables sin valores reales
├── docs/
│   └── constitution.md
├── specs/
│   └── 001-nucleo/
│       ├── spec.md            # qué y por qué
│       ├── plan.md            # cómo (diseño técnico)
│       └── tasks.md           # tareas pequeñas y ordenadas
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── alembic/               # migraciones
│   ├── src/finanzas/
│   │   ├── domain/            # lógica pura: dinero, saldos, reglas
│   │   ├── db/                # modelos SQLAlchemy, repositorios
│   │   ├── api/               # routers FastAPI, esquemas Pydantic
│   │   ├── integrations/      # whatsapp/, llm/ (desde 005)
│   │   └── main.py
│   └── tests/
│       ├── unit/              # dominio, sin BD
│       └── integration/       # API + PostgreSQL
├── frontend/
│   ├── package.json
│   ├── src/
│   └── tests/                 # Vitest + e2e/ (Playwright)
└── data/                      # IGNORADA por git: datos reales locales
```

## Comandos
- Levantar todo en local: `docker compose up`
- Backend (desde `backend/`):
  - Instalar: `uv sync`
  - Servidor de desarrollo: `uv run fastapi dev src/finanzas/main.py`
  - Tests: `uv run pytest -q`
  - Cobertura: `uv run pytest --cov=finanzas --cov-fail-under=90`
  - Lint/formato: `uv run ruff check . && uv run ruff format --check .`
  - Migraciones: `uv run alembic upgrade head` /
    `uv run alembic revision --autogenerate -m "<mensaje>"`
- Frontend (desde `frontend/`):
  - Instalar: `npm install` · Desarrollo: `npm run dev`
  - Tests: `npm test` · E2E: `npx playwright test` · Lint: `npm run lint`

## Convenciones
- **Idioma:** identificadores, tablas, commits y nombres de archivo en
  inglés. Interfaz, mensajes del bot, specs y docs en español.
- **Dinero:** `int` en centavos de COP (`BIGINT` en BD). Nunca `float`.
  Formatear a pesos solo en la presentación. Montos siempre positivos; el
  tipo define el signo.
- **Saldos:** siempre derivados (saldo inicial + movimientos). No existe
  una columna de saldo editable.
- **Borrado:** los movimientos se anulan o corrigen con rastro, no se
  eliminan.
- **Capas:** `domain/` no importa FastAPI, SQLAlchemy ni nada de red.
- **Dueño:** toda entidad tiene un usuario dueño. Ninguna consulta ni
  escritura se hace sin filtrar por el usuario autenticado. Cada
  funcionalidad incluye un test que comprueba que un usuario no ve ni
  modifica datos de otro.
- **Python:** type hints en todas las funciones públicas; Ruff sin
  errores.
- **TypeScript:** modo `strict`.
- **Fechas:** se guardan con zona horaria y se muestran en
  `America/Bogota`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`…)
  con referencia a la spec, p. ej. `feat(001): calcular saldo derivado`.

## Reglas
1. **Lee antes de tocar código:** `docs/constitution.md` y la spec activa
   en `specs/` (spec, plan y tareas).
2. **Datos reales nunca en git:** ni extractos, ni el Excel, ni dumps de
   BD, ni `.env`, ni números de teléfono o tokens. Usa datos sintéticos en
   tests y ejemplos. Si ves un dato real a punto de entrar a un commit,
   detente y avisa.
3. **Tests primero:** escribe el test que falla, luego el código mínimo
   que lo hace pasar, luego refactoriza.
4. **Una tarea a la vez:** toma una sola tarea de `tasks.md`, termínala
   (tests en verde) y detente para revisión antes de la siguiente.
5. **Cambios primero en la spec:** si la implementación requiere algo que
   la spec no dice (endpoint, campo, dependencia, cambio de esquema),
   propón el cambio a la spec y espera aprobación. No edites `specs/` ni
   `docs/constitution.md` sin petición explícita.
6. **Sin dependencias nuevas** sin justificarlas en el `plan.md` de la
   spec.
7. **Migraciones:** todo cambio de esquema va en una migración de Alembic
   nueva; nunca edites una migración ya aplicada.

## Al terminar cualquier tarea
- Ejecuta los tests y el lint de la parte que tocaste (backend y/o
  frontend) y confirma en tu respuesta que todo pasa, incluida la
  cobertura ≥ 90 % del backend.
- Indica qué tarea de `tasks.md` quedó completa.
