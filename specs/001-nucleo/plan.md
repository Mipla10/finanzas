# Plan 001 — Núcleo

- **Spec:** [spec.md](spec.md) (borrador v2, MVP)
- **Estado:** Borrador para revisión
- **Fecha:** 2026-11-23

Este documento describe **cómo** se construye la spec 001. Si algo de
aquí contradice la spec, manda la spec, y se corrige primero allí (regla 5
de AGENTS.md). La sección 10 recoge los riesgos y la 11 los cambios
pendientes que este plan propone a otros documentos. La sección 12 resume
el plan en lenguaje no técnico.

---

## 1. Arquitectura

### 1.1 Capas

```
Cliente (curl, Swagger UI, luego web 002 / WhatsApp 005)
        │  HTTP + JSON + contraseña
        ▼
┌──────────────────────────────────────────────┐
│ api/        Routers FastAPI, esquemas        │  traduce HTTP ⇄ Python
│             Pydantic, auth, manejo de errores│
├──────────────────────────────────────────────┤
│ services/   Casos de uso: una función por    │  orquesta y abre/cierra
│             operación de la spec (crear      │  la transacción
│             gasto, anular, ajustar…)         │
├──────────────────────────────────────────────┤
│ domain/     Reglas puras: dinero, fechas,    │  sin FastAPI, sin
│             saldos, validaciones, errores    │  SQLAlchemy, sin red
├──────────────────────────────────────────────┤
│ db/         Modelos SQLAlchemy +             │  única capa que habla
│             repositorios (consultas)         │  con PostgreSQL
└──────────────────────────────────────────────┘
        ▼
    PostgreSQL 16
```

**Responsabilidades de cada capa:**

| Capa | Qué hace | Qué NO hace |
|------|----------|-------------|
| `api/` | Valida la forma del JSON (tipos, campos obligatorios, longitudes). Comprueba la contraseña, obtiene el usuario actual y llama a un servicio. Convierte los errores de dominio en respuestas HTTP. | No contiene reglas de negocio ni SQL. |
| `services/` | Ejecuta un caso de uso completo dentro de **una transacción**: carga datos con los repositorios, aplica las reglas del dominio, guarda, calcula las advertencias y confirma. Todas sus funciones reciben `owner_id`. | No conoce HTTP. |
| `domain/` | Contiene lógica pura y testeable sin base de datos: validar montos y fechas, normalizar textos, calcular saldos y ajustes, comparar versiones y definir los errores tipados. | No importa FastAPI, SQLAlchemy ni nada de red (principio 8). |
| `db/` | Define las tablas (modelos), las consultas eficientes (saldos agregados, listados con filtros) y los bloqueos de fila. **Toda consulta filtra por `owner_id`.** | No decide reglas de negocio. |

**Flujo típico (registrar un gasto):** `POST /movements` → `api` valida el
JSON → `services.movements.create(owner_id, datos, clock)` → `domain`
valida el monto, la fecha y el tipo → `db` comprueba que la cuenta y la
categoría existen, son del dueño y están activas → INSERT del movimiento
y de la versión 1 → `domain` calcula las advertencias con los saldos que
devuelve `db` → COMMIT → respuesta `201`.

### 1.2 Estructura de carpetas del backend

```
backend/
├── pyproject.toml              # dependencias y config de ruff/pytest/coverage
├── uv.lock
├── Dockerfile
├── alembic.ini
├── alembic/
│   └── versions/               # 0001_initial_schema.py, …
├── src/finanzas/
│   ├── main.py                 # crea la app, registra routers y handlers,
│   │                           # verifica config y siembra el usuario inicial
│   ├── config.py               # Settings (lee .env); falla si falta APP_PASSWORD
│   ├── domain/
│   │   ├── money.py            # validación de centavos
│   │   ├── dates.py            # Clock (hoy en Bogotá), reglas de fecha
│   │   ├── text.py             # normalización de nombres y comercio
│   │   ├── movements.py        # tipos, reglas por tipo, diff de versiones
│   │   ├── balances.py         # saldo derivado, subtotales, advertencias
│   │   ├── adjustments.py      # cálculo del ajuste
│   │   ├── errors.py           # InvalidData, NotFound, Conflict
│   │   ├── messages.py         # catálogo de mensajes en español (RNF-7)
│   │   └── defaults.py         # categorías precargadas
│   ├── services/
│   │   ├── accounts.py
│   │   ├── categories.py
│   │   ├── movements.py        # crear, corregir, anular, listar, historial
│   │   ├── adjustments.py
│   │   ├── balances.py
│   │   └── bootstrap.py        # usuario inicial + categorías (idempotente)
│   ├── db/
│   │   ├── base.py             # engine, sesión
│   │   ├── models.py           # User, Account, Category, Movement, MovementVersion
│   │   └── repositories/
│   │       ├── accounts.py
│   │       ├── categories.py
│   │       ├── movements.py
│   │       └── balances.py     # consulta agregada de saldos
│   └── api/
│       ├── deps.py             # get_session, get_clock, require_password, get_owner_id
│       ├── errors.py           # formato estándar de error + handlers
│       ├── schemas/            # modelos Pydantic de request/response
│       └── routers/
│           ├── accounts.py
│           ├── categories.py
│           ├── movements.py
│           ├── balances.py
│           ├── merchants.py
│           └── health.py
└── tests/
    ├── conftest.py             # BD de prueba, FixedClock, cliente HTTP, 2 usuarios
    ├── unit/                   # domain/: sin BD, muy rápidos
    ├── integration/            # API + PostgreSQL real
    │   └── test_isolation.py   # RNF-5: cada operación con 2 usuarios
    ├── scenarios/
    │   └── test_month.py       # criterio 3 / RNF-1: mes sintético fijo
    └── perf/
        └── test_rnf3.py        # RNF-3 (marcado, no corre por defecto)
```

> `services/`, `tests/scenarios/` y `tests/perf/` se añadieron a la
> estructura de AGENTS.md (ver sección 11).

### 1.3 Dependencias (regla 6 de AGENTS.md)

| Paquete | Para qué | Por qué este |
|---------|----------|--------------|
| `fastapi[standard]` | API REST, OpenAPI y Swagger UI (RNF-9) | Elegido en AGENTS.md. Incluye el servidor `uvicorn`. |
| `pydantic`, `pydantic-settings` | Validar el JSON y leer `.env` | Viene con FastAPI y permite tipos estrictos (montos enteros). |
| `sqlalchemy>=2` | ORM y consultas | Elegido en AGENTS.md. |
| `psycopg[binary]` | Driver de PostgreSQL | Driver moderno y oficial para SQLAlchemy 2. |
| `alembic` | Migraciones | Elegido en AGENTS.md. |
| `tzdata` | Zona `America/Bogota` | Garantiza la zona horaria también en imágenes Docker mínimas. |
| **dev:** `pytest`, `pytest-cov`, `httpx`, `ruff` | Tests, cobertura, cliente HTTP de prueba y lint | `httpx` lo exige el `TestClient` de FastAPI. |

Las operaciones se definen **síncronas**: con un solo usuario y PostgreSQL
local, la asincronía no aporta y complica las pruebas. La spec 005 podrá
añadir partes asíncronas para WhatsApp y el LLM.

---

## 2. Modelo de datos

### 2.1 Convenciones
- **Llaves primarias:** `UUID` generado en la aplicación (`uuid4`). Así no
  se puede adivinar el identificador de otros recursos.
- **Dueño:** toda tabla de negocio tiene `owner_id UUID NOT NULL`. Las
  referencias entre tablas usan **llaves foráneas compuestas**
  `(id, owner_id)`, de modo que **la propia base de datos impide** que un
  movimiento apunte a la cuenta de otro usuario. Es la segunda línea de
  defensa de RNF-5.
- **Dinero:** `BIGINT`, en centavos.
- **Fechas de movimiento:** `DATE`.
- **Marcas de tiempo:** `TIMESTAMPTZ`, escritas por la aplicación con el
  `Clock`, para que los tests las controlen.
- **Enums:** tipos `ENUM` de PostgreSQL con valores en inglés.

### 2.2 Tablas

**`users`**

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | UUID | PK |
| `created_at` | TIMESTAMPTZ | NOT NULL |

La spec 004 añadirá email, contraseña, etc.

**`accounts`**

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | UUID | PK |
| `owner_id` | UUID | NOT NULL, FK → `users.id` |
| `name` | VARCHAR(60) | NOT NULL, tal como se muestra (tras recortar espacios) |
| `name_key` | VARCHAR(60) | NOT NULL, normalizado (ver 5.3) |
| `type` | `account_type` ENUM(`bank`,`pocket`,`digital_wallet`,`cash`) | NOT NULL |
| `parent_id` | UUID | NULL. FK compuesta `(parent_id, owner_id)` → `accounts(id, owner_id)` |
| `initial_balance_cents` | BIGINT | NOT NULL (puede ser ≤ 0) |
| `start_date` | DATE | NOT NULL |
| `archived_at` | TIMESTAMPTZ | NULL = activa |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Restricciones e índices de `accounts`:
- `UNIQUE (id, owner_id)`, destino de las llaves foráneas compuestas.
- `UNIQUE (owner_id, name_key)`: nombre único por usuario (RF-4).
- `CHECK ((type = 'pocket') = (parent_id IS NOT NULL))`: solo los
  bolsillos tienen padre.
- `CHECK (parent_id <> id)`.
- Un CHECK no puede leer otras filas, así que estas reglas se validan en
  el servicio: «el padre es un banco activo», «la fecha de inicio no es
  futura» y «archivar solo con saldo 0».
- Índice `(owner_id)`.

**`categories`**

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | UUID | PK |
| `owner_id` | UUID | NOT NULL, FK → `users.id` |
| `name` | VARCHAR(40) | NOT NULL |
| `name_key` | VARCHAR(40) | NOT NULL |
| `kind` | `category_kind` ENUM(`expense`,`income`) | NOT NULL, no editable |
| `archived_at` | TIMESTAMPTZ | NULL = activa |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Restricciones de `categories`:
- `UNIQUE (id, owner_id)`.
- `UNIQUE (owner_id, kind, name_key)` (RF-6).

**`movements`**: el estado **actual** de cada movimiento.

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | UUID | PK |
| `owner_id` | UUID | NOT NULL, FK → `users.id` |
| `type` | `movement_type` ENUM(`expense`,`income`,`transfer`,`yield`,`adjustment`) | NOT NULL, no editable |
| `amount_cents` | BIGINT | NOT NULL, `CHECK (amount_cents > 0)` |
| `date` | DATE | NOT NULL |
| `from_account_id` | UUID | NULL. FK compuesta → `accounts(id, owner_id)` |
| `to_account_id` | UUID | NULL. FK compuesta → `accounts(id, owner_id)` |
| `category_id` | UUID | NULL. FK compuesta → `categories(id, owner_id)` |
| `adjustment_direction` | `adjustment_direction` ENUM(`in`,`out`) | NULL salvo en los ajustes |
| `merchant` | VARCHAR(80) | NULL. Forma mostrada (recortada) |
| `merchant_key` | VARCHAR(80) | NULL. Forma normalizada, para comparar y agrupar |
| `note` | VARCHAR(500) | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL. Momento de registro: **nunca cambia** (RF-2) |
| `updated_at` | TIMESTAMPTZ | NOT NULL |
| `current_version` | INTEGER | NOT NULL, empieza en 1 |
| `voided_at` | TIMESTAMPTZ | NULL = vigente |
| `void_reason` | VARCHAR(200) | NULL |

**Regla clave:** el dinero **sale** de `from_account_id` y **entra** a
`to_account_id`, para todos los tipos. Así el saldo se calcula con una
sola fórmula:

| Tipo | `from_account_id` | `to_account_id` | `category_id` | `adjustment_direction` |
|------|------|------|------|------|
| `expense` | obligatoria | NULL | obligatoria (clase `expense`) | NULL |
| `income` | NULL | obligatoria | obligatoria (clase `income`) | NULL |
| `transfer` | obligatoria | obligatoria y ≠ origen | NULL | NULL |
| `yield` | NULL | obligatoria | NULL | NULL |
| `adjustment`, dirección `in` | NULL | obligatoria | NULL | `in` |
| `adjustment`, dirección `out` | obligatoria | NULL | NULL | `out` |

Esta tabla se implementa como un `CHECK` por tipo, llamado
`ck_movement_shape`. Si el código tiene un error, la base de datos lo
rechaza. La regla «la categoría es de la clase correcta» se valida en el
servicio.

Índices de `movements`:
- `(owner_id, date DESC, created_at DESC, id DESC)`: listado con su orden
  exacto.
- `(owner_id, from_account_id) WHERE voided_at IS NULL` y
  `(owner_id, to_account_id) WHERE voided_at IS NULL`: cálculo de saldos.
- `(owner_id, category_id)`: filtro por categoría y regla de borrado.
- `(owner_id, merchant_key)`: lista de comercios.

**`movement_versions`**: una fila por **cada** versión, incluida la
inicial. Es solo de inserción y nunca se actualiza ni se borra (RF-20).

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | UUID | PK |
| `owner_id` | UUID | NOT NULL |
| `movement_id` | UUID | NOT NULL. FK compuesta `(movement_id, owner_id)` → `movements(id, owner_id)` |
| `version_no` | INTEGER | NOT NULL |
| `amount_cents`, `date`, `from_account_id`, `to_account_id`, `category_id`, `merchant`, `merchant_key`, `note` | (como en `movements`) | Copia completa de esa versión |
| `changed_fields` | TEXT[] | NOT NULL (`{}` en la versión 1) |
| `created_at` | TIMESTAMPTZ | NOT NULL. Momento del cambio |

Restricciones e índices de `movement_versions`:
- `UNIQUE (movement_id, version_no)`.
- Índices: `(owner_id, from_account_id)`, `(owner_id, to_account_id)` y
  `(owner_id, category_id)`, para la regla «nunca usada» al borrar
  (RF-5 y RF-6).
- `movements` también necesita `UNIQUE (id, owner_id)` para recibir esta
  llave foránea.

**Comercios:** **no** tienen tabla, porque la spec dice que no son una
entidad. La lista se obtiene agrupando `movements.merchant_key`.

### 2.3 Diagrama entidad-relación

```mermaid
erDiagram
    USERS ||--o{ ACCOUNTS : "es dueño de"
    USERS ||--o{ CATEGORIES : "es dueño de"
    USERS ||--o{ MOVEMENTS : "es dueño de"
    ACCOUNTS ||--o{ ACCOUNTS : "padre de (bolsillos)"
    ACCOUNTS ||--o{ MOVEMENTS : "origen (from)"
    ACCOUNTS ||--o{ MOVEMENTS : "destino (to)"
    CATEGORIES ||--o{ MOVEMENTS : "clasifica"
    MOVEMENTS ||--|{ MOVEMENT_VERSIONS : "tiene versiones"

    USERS {
        uuid id PK
        timestamptz created_at
    }
    ACCOUNTS {
        uuid id PK
        uuid owner_id FK
        varchar name
        varchar name_key
        account_type type
        uuid parent_id FK
        bigint initial_balance_cents
        date start_date
        timestamptz archived_at
    }
    CATEGORIES {
        uuid id PK
        uuid owner_id FK
        varchar name
        varchar name_key
        category_kind kind
        timestamptz archived_at
    }
    MOVEMENTS {
        uuid id PK
        uuid owner_id FK
        movement_type type
        bigint amount_cents
        date date
        uuid from_account_id FK
        uuid to_account_id FK
        uuid category_id FK
        adjustment_direction adjustment_direction
        varchar merchant
        varchar merchant_key
        varchar note
        timestamptz created_at
        int current_version
        timestamptz voided_at
        varchar void_reason
    }
    MOVEMENT_VERSIONS {
        uuid id PK
        uuid owner_id
        uuid movement_id FK
        int version_no
        bigint amount_cents
        date date
        text_array changed_fields
        timestamptz created_at
    }
```

### 2.4 Ejemplo con datos sintéticos

En este ejemplo, hoy es **2026-11-23** y todas las cuentas empiezan el
2026-11-01. Los identificadores están abreviados.

**Cuentas**

| id | name | type | parent_id | initial_balance_cents |
|----|------|------|-----------|----------------------:|
| A1 | Lulo | bank | — | 150000000 ($ 1.500.000) |
| A2 | Ahorro | pocket | A1 | 300000000 ($ 3.000.000) |
| A3 | Nequi | digital_wallet | — | 20000000 ($ 200.000) |
| A4 | Efectivo | cash | — | 5000000 ($ 50.000) |

**Movimientos**

| id | type | amount_cents | date | from | to | category | merchant | estado |
|----|------|-------------:|------|------|----|----------|----------|--------|
| M1 | income | 200000000 | 11-01 | — | A1 | Salario | — | vigente |
| M2 | expense | 2500000 | 11-03 | A3 | — | Domicilios | Rappi | vigente (v2) |
| M3 | transfer | 20000000 | 11-05 | A1 | A4 | — | — | vigente (retiro de cajero) |
| M4 | expense | 700000 | 11-05 | A1 | — | Comisiones bancarias | — | vigente |
| M5 | transfer | 50000000 | 11-06 | A1 | A2 | — | — | vigente |
| M6 | expense | 8000000 | 11-10 | A4 | — | Alimentación | — | **anulado** |
| M7 | yield | 1234567 | 11-20 | — | A2 | — | — | vigente |
| M8 | adjustment (`out`) | 350000 | 11-23 | A3 | — | — | — | vigente |

**Versiones de M2:** primero se registró con el monto equivocado y luego
se corrigió.

| movement_id | version_no | amount_cents | changed_fields | created_at |
|-------------|-----------:|-------------:|----------------|------------|
| M2 | 1 | 2300000 | `{}` | 2026-11-03 12:10-05 |
| M2 | 2 | 2500000 | `{amount_cents}` | 2026-11-03 18:40-05 |

**Cómo se obtuvo M8:** el saldo real de Nequi en la app del banco era
$ 171.500 (`17150000`). El saldo calculado antes del ajuste era
`20000000 − 2500000 = 17500000`. La diferencia es `−350000`, así que se
creó un ajuste `out` por `350000`.

**Saldos resultantes (valores esperados del test de RNF-1):**

| Cuenta | Cálculo | Saldo |
|--------|---------|------:|
| Lulo (propio) | 150000000 + 200000000 − 20000000 − 700000 − 50000000 | **279300000** |
| Ahorro | 300000000 + 50000000 + 1234567 | **351234567** |
| Subtotal Lulo + bolsillos | 279300000 + 351234567 | **630534567** |
| Nequi | 20000000 − 2500000 − 350000 | **17150000** |
| Efectivo | 5000000 + 20000000 (M6 anulado no cuenta) | **25000000** |
| **Total general** | 630534567 + 17150000 + 25000000 | **672684567** ($ 6.726.845,67) |

**Totales del listado de noviembre (RF-17):**
- **Ingresos:** `201234567`, de los cuales `1234567` son rendimientos.
- **Gastos:** `3200000`.
- **Neto:** `198034567`.

Las transferencias M3 y M5, el ajuste M8 y el movimiento anulado M6 no
cuentan.

**Ampliación para el escenario del mes (criterio de finalización 3).**
El criterio 3 de la spec pide dos bolsillos y una transferencia entre
bolsillos. El escenario completo (`tests/scenarios/test_month.py`) añade
a lo anterior:

| id | name | type | parent_id | initial_balance_cents |
|----|------|------|-----------|----------------------:|
| A5 | Viajes | pocket | A1 | 0 ($ 0) |

| id | type | amount_cents | date | from | to | category | merchant | estado |
|----|------|-------------:|------|------|----|----------|----------|--------|
| M9 | transfer | 10000000 | 11-21 | A2 | A5 | — | — | vigente (entre bolsillos) |

Con la ampliación cambian solo los saldos de los dos bolsillos:

| Cuenta | Cálculo | Saldo |
|--------|---------|------:|
| Ahorro | 351234567 − 10000000 | **341234567** |
| Viajes | 0 + 10000000 | **10000000** |
| Subtotal Lulo + bolsillos | 279300000 + 341234567 + 10000000 | **630534567** (no cambia) |
| **Total general** | 630534567 + 17150000 + 25000000 | **672684567** (no cambia) |

Los totales del listado tampoco cambian, porque M9 es una transferencia.
El listado de noviembre muestra 8 movimientos: M1 a M5, M7, M8 y M9.
Los demás ejemplos del plan (§4.3) y el fixture `month_scenario` usan
solo el ejemplo base A1–A4, M1–M8.

---

## 3. Algoritmos (pseudocódigo)

### 3.1 Saldo derivado actual (RF-15)

Las fechas nunca son futuras (RF-2) ni anteriores al inicio de la cuenta
(RF-4), así que el saldo actual es la suma de **todos** los movimientos
vigentes:

```
función saldo_actual(cuenta, movimientos):
    saldo ← cuenta.initial_balance_cents
    para cada m en movimientos:
        si m.voided_at no es NULL: continuar          # anulados no cuentan
        si m.to_account_id   = cuenta.id: saldo ← saldo + m.amount_cents
        si m.from_account_id = cuenta.id: saldo ← saldo − m.amount_cents
    devolver saldo
```

Esta versión pura vive en `domain/balances.py` y se usa en los tests
unitarios. En producción se calcula **en una sola consulta SQL para todas
las cuentas** del usuario (`db/repositories/balances.py`):

```sql
SELECT a.id,
       a.initial_balance_cents + COALESCE(SUM(f.delta), 0) AS balance_cents
FROM accounts a
LEFT JOIN (
    SELECT to_account_id   AS account_id,  amount_cents AS delta
      FROM movements WHERE owner_id = :owner AND voided_at IS NULL AND to_account_id IS NOT NULL
    UNION ALL
    SELECT from_account_id AS account_id, -amount_cents AS delta
      FROM movements WHERE owner_id = :owner AND voided_at IS NULL AND from_account_id IS NOT NULL
) f ON f.account_id = a.id
WHERE a.owner_id = :owner
GROUP BY a.id;
```

Un test de propiedades comprueba, con movimientos aleatorios sintéticos,
que la versión pura y la SQL dan **siempre** el mismo resultado.

> El saldo **a una fecha** está fuera de la spec 001. Cuando lo pida la
> spec 003, bastará con añadir `AND date <= :fecha` a ambas ramas.

### 3.2 Subtotal banco + bolsillos y total (RF-16)

```
función consultar_saldos(owner):
    saldos ← consulta_3_1(owner)                  # {cuenta_id: saldo}
    cuentas ← cuentas_de(owner)
    visibles ← [c en cuentas si c.archived_at es NULL o saldos[c.id] ≠ 0]
    grupos ← []
    para cada banco en cuentas con type = 'bank':
        hijos ← [c en cuentas si c.parent_id = banco.id]
        si hijos no está vacío:
            grupos.agregar({banco, subtotal: saldos[banco.id] + Σ saldos[h.id] de hijos})
    total ← Σ saldos[c.id] para TODAS las cuentas   # cada una una sola vez
    devolver {visibles con saldo y marca archivada, grupos, total}
```

### 3.3 Cálculo del ajuste (RF-12)

```
función ajustar(owner, cuenta_id, saldo_real, clock):
    INICIO TRANSACCIÓN
    cuenta ← bloquear_fila(accounts, cuenta_id, owner)   # SELECT … FOR UPDATE
    si cuenta no existe: error NotFound
    si cuenta archivada: error Conflict("cuenta archivada")
    actual ← saldo_actual(cuenta)          # solo el saldo propio, sin bolsillos
    diferencia ← saldo_real − actual
    si diferencia = 0:
        COMMIT; devolver {estado: "ya_cuadra", saldo: actual}
    si diferencia > 0: dirección ← 'in'  ; to ← cuenta ; from ← NULL
    si diferencia < 0: dirección ← 'out' ; from ← cuenta; to ← NULL
    m ← insertar movimiento(type='adjustment', amount=|diferencia|,
                            date=clock.today(), dirección, from, to)
    insertar versión 1 de m
    advertencias ← detectar_advertencias(owner, {cuenta.id})
    COMMIT
    devolver {movimiento: m, advertencias}
```

El bloqueo de fila hace que dos ajustes simultáneos sobre la misma cuenta
se ejecuten uno detrás del otro. Así el segundo ya ve el primero (RF-12,
varios ajustes en un día).

### 3.4 Detección de advertencias (RF-14)

```
función detectar_advertencias(owner, cuentas_afectadas):
    saldos ← consulta_3_1(owner) restringida a cuentas_afectadas
    advertencias ← []
    para cada c en cuentas_afectadas:
        si saldos[c] < 0:
            advertencias.agregar({code: "negative_balance", cuenta: c, saldo: saldos[c]})
        si c está archivada y saldos[c] ≠ 0:
            advertencias.agregar({code: "archived_nonzero_balance", cuenta: c, saldo: saldos[c]})
    devolver advertencias
```

**Cuentas afectadas** por cada operación:
- **Crear:** las cuentas `from` y `to` del movimiento.
- **Corregir:** las cuentas `from` y `to` de la versión anterior **y** de
  la nueva. Si el gasto cambió de cuenta, las dos se revisan.
- **Anular:** las cuentas `from` y `to` del movimiento anulado.
- **Ajustar:** la cuenta ajustada.

Las advertencias se calculan **dentro** de la transacción, después del
cambio, para ver el estado ya actualizado.

### 3.5 Crear un movimiento (RF-7 a RF-11)

```
función crear(owner, datos, clock):
    si datos.type = 'adjustment': error InvalidData("type", "usa el endpoint de ajustes")
    validar_monto(datos.amount_cents)                       # > 0, entero
    fecha ← datos.date o clock.today()
    si fecha > clock.today(): error InvalidData("date", "no se admiten fechas futuras")
    validar_forma(datos.type, from, to, category)           # tabla de 2.2
    para cada cuenta en {from, to} no nulas:
        c ← obtener(accounts, id, owner)  o  error NotFound(campo)
        si c archivada: error Conflict(campo, "cuenta archivada")
        si fecha < c.start_date: error InvalidData("date", "anterior al inicio de <c>")
    si hay categoría:
        k ← obtener(categories, id, owner) o error NotFound("category_id")
        si k archivada: error Conflict("category_id", "categoría archivada")
        si k.kind no coincide con el tipo: error InvalidData("category_id", "clase incorrecta")
    comercio, clave ← normalizar_comercio(datos.merchant)  # 5.3
    nota ← recortar(datos.note) o NULL si queda vacía
    INSERT movimiento (created_at = updated_at = clock.now(), current_version = 1)
    INSERT versión 1 (changed_fields = {})
    advertencias ← detectar_advertencias(owner, {from, to})
    COMMIT
```

### 3.6 Corrección con historial (RF-19, RF-20)

```
función corregir(owner, id, cambios, clock):
    INICIO TRANSACCIÓN
    m ← bloquear_fila(movements, id, owner)  o  error NotFound
    si m.voided_at no es NULL:     error Conflict("movimiento anulado")
    si m.type = 'adjustment':      error Conflict("los ajustes no se corrigen; anúlalo")
    si "type" en cambios y cambios.type ≠ m.type:
                                   error InvalidData("type", "no se puede cambiar el tipo")
    nuevo ← copia de m con cambios aplicados (comercio y nota normalizados)
    cambiados ← campos donde nuevo ≠ m          # el comercio se compara por merchant_key
    si cambiados está vacío:
        COMMIT; devolver {movimiento: m, cambiado: false, advertencias: []}
    validar nuevo con las reglas de 3.5, EXCEPTO:
        · una cuenta o categoría que NO cambió se acepta aunque esté archivada
        · una cuenta o categoría NUEVA debe existir, ser del dueño y estar activa
    UPDATE movimiento ← nuevo, updated_at = clock.now(),
           current_version = m.current_version + 1     # created_at NO cambia
    INSERT versión (version_no = current_version, copia de nuevo,
                    changed_fields = cambiados, created_at = clock.now())
    advertencias ← detectar_advertencias(owner, cuentas(m) ∪ cuentas(nuevo))
    COMMIT
    devolver {movimiento: nuevo, cambiado: true, advertencias}
```

**Dos correcciones casi simultáneas:** el `SELECT … FOR UPDATE` hace que
la segunda espere a que la primera termine. Después aplica sus cambios
sobre la versión ya corregida y crea la versión siguiente. Gana la última
y ambas quedan en el historial (RF-19).

**Historial** (`GET /movements/{id}/history`): se devuelven las filas de
`movement_versions` ordenadas por `version_no`, con sus `changed_fields`,
y al final un evento `voided` si `voided_at` no es NULL. Los nombres de
cuenta y categoría se resuelven con su **nombre actual** (decisión C-5).

### 3.7 Anulación (RF-21)

```
función anular(owner, id, motivo, clock):
    INICIO TRANSACCIÓN
    m ← bloquear_fila(movements, id, owner)  o  error NotFound
    si m.voided_at no es NULL: error Conflict("ya está anulado")
    UPDATE m SET voided_at = clock.now(), void_reason = recortar(motivo) o NULL
    advertencias ← detectar_advertencias(owner, cuentas(m))
    COMMIT
```

Anular está permitido aunque la cuenta o la categoría estén archivadas.
**No** se crea una versión, porque la anulación es un estado del
movimiento.

### 3.8 Regla «nunca usada» para borrar (RF-5, RF-6)

```
cuenta borrable ⇔ NO EXISTE fila en movements o movement_versions con esa cuenta
                  en from_account_id o to_account_id
                  Y NO EXISTE cuenta con parent_id = esa cuenta
categoría borrable ⇔ NO EXISTE fila en movements o movement_versions con ese category_id
```

Los movimientos anulados siguen en `movements`, así que cuentan como uso.

---

## 4. Contrato de la API REST

### 4.1 Convenciones
- **Base:** `/api/v1`. JSON en UTF-8.
- **Autenticación:** cabecera `Authorization: Bearer <APP_PASSWORD>` en
  toda petición (ver 5.6).
- **Nombres:** los campos y los valores de enums van en inglés
  (convención de código); los mensajes, en español.
- **Dinero:** campos `*_cents` de tipo entero **estricto**. `2500.5`,
  `"2500000"` y `2.5e6` se rechazan con `422`. El valor absoluto máximo
  es `9007199254740991` (2^53 − 1), el límite técnico de RF-1; más allá,
  `422`.
- **Fechas:** `"YYYY-MM-DD"`. Las marcas de tiempo van en ISO 8601 con
  zona, por ejemplo `"2026-11-23T10:15:00-05:00"`.
- **Advertencias:** toda operación que modifica datos devuelve
  `"warnings": [...]` (lista vacía si no hay ninguna).
- **Listas:** todo listado responde un objeto con la lista en `items`,
  también `GET /accounts` y `GET /categories`:
  `{ "items": [ ... ] }`. `GET /movements` añade `totals` y `page`
  (ver 4.3).
- **PATCH:** solo cambia lo que viene en el JSON; un campo ausente no
  cambia.
  - En `PATCH /movements/{id}`, enviar `null` borra un dato opcional
    (`merchant`, `note`). En un campo obligatorio para el tipo
    (`amount_cents`, `date`, cuentas, categoría de gasto o ingreso),
    `null` responde `422`.
  - En `PATCH /accounts/{id}`, `null` equivale a no enviar el campo:
    nombre, saldo inicial y fecha de inicio no se pueden borrar.
  - `PATCH /categories/{id}` exige `name`.

### 4.2 Endpoints

| Método y ruta | Qué hace | RF | Éxito |
|---------------|----------|----|-------|
| `GET /health` | Estado del servicio | — | 200 |
| `POST /accounts` | Crear cuenta | RF-4 | 201 |
| `GET /accounts?include_archived=false` | Listar cuentas | RF-4 | 200 |
| `GET /accounts/{id}` | Ver cuenta | RF-4 | 200 |
| `PATCH /accounts/{id}` | Renombrar o editar saldo y fecha inicial (si no tiene movimientos) | RF-5 | 200 |
| `POST /accounts/{id}/archive` | Archivar | RF-5 | 200 |
| `POST /accounts/{id}/unarchive` | Desarchivar | RF-5 | 200 |
| `DELETE /accounts/{id}` | Borrar (si nunca se usó) | RF-5 | 204 |
| `POST /accounts/{id}/adjustments` | Ajustar al saldo real | RF-12 | 201 o 200 |
| `POST /categories` | Crear categoría | RF-6 | 201 |
| `GET /categories?kind=&include_archived=false` | Listar categorías | RF-6 | 200 |
| `PATCH /categories/{id}` | Renombrar | RF-6 | 200 |
| `POST /categories/{id}/archive` · `/unarchive` | Archivar o desarchivar | RF-6 | 200 |
| `DELETE /categories/{id}` | Borrar (si nunca se usó) | RF-6 | 204 |
| `POST /movements` | Crear gasto, ingreso, transferencia o rendimiento | RF-7 a RF-11 | 201 |
| `GET /movements` | Listar, filtrar y totales | RF-17 | 200 |
| `GET /movements/{id}` | Ver movimiento | RF-18 | 200 |
| `PATCH /movements/{id}` | Corregir | RF-19 | 200 |
| `POST /movements/{id}/void` | Anular | RF-21 | 200 |
| `GET /movements/{id}/history` | Historial de versiones | RF-20 | 200 |
| `GET /balances` | Saldos, subtotales y total | RF-15, RF-16 | 200 |
| `GET /merchants?limit=20` | Comercios usados | RF-13 | 200 |

### 4.3 Ejemplos

**Crear un bolsillo**: `POST /api/v1/accounts`
```json
{
  "name": "Ahorro",
  "type": "pocket",
  "parent_id": "6f1c…a1",
  "initial_balance_cents": 300000000,
  "start_date": "2026-11-01"
}
```
→ `201 Created`
```json
{
  "id": "9b2e…a2",
  "name": "Ahorro",
  "type": "pocket",
  "parent_id": "6f1c…a1",
  "initial_balance_cents": 300000000,
  "start_date": "2026-11-01",
  "archived": false,
  "created_at": "2026-11-23T09:00:00-05:00"
}
```

**Registrar un gasto**: `POST /api/v1/movements`
```json
{
  "type": "expense",
  "amount_cents": 2500000,
  "date": "2026-11-03",
  "from_account_id": "c4d0…a3",
  "category_id": "e7aa…k1",
  "merchant": "  rappi ",
  "note": "Almuerzo"
}
```
→ `201 Created`
```json
{
  "movement": {
    "id": "1a2b…m2",
    "type": "expense",
    "amount_cents": 2500000,
    "date": "2026-11-03",
    "from_account": {"id": "c4d0…a3", "name": "Nequi"},
    "to_account": null,
    "category": {"id": "e7aa…k1", "name": "Domicilios"},
    "adjustment_direction": null,
    "merchant": "rappi",
    "note": "Almuerzo",
    "voided": false,
    "voided_at": null,
    "void_reason": null,
    "version": 1,
    "created_at": "2026-11-03T12:10:00-05:00"
  },
  "warnings": []
}
```

**Transferencia que deja la cuenta en negativo**: la respuesta es `201`
con advertencia:
```json
{
  "movement": { "id": "…", "type": "transfer", "amount_cents": 90000000, "...": "..." },
  "warnings": [
    {
      "code": "negative_balance",
      "account": {"id": "c4d0…a3", "name": "Nequi"},
      "balance_cents": -72850000,
      "message": "La cuenta Nequi quedó con saldo negativo."
    }
  ]
}
```

**Ajuste**: `POST /api/v1/accounts/c4d0…a3/adjustments`
```json
{ "real_balance_cents": 17150000 }
```
→ `201 Created`
```json
{
  "status": "adjusted",
  "movement": { "id": "…m8", "type": "adjustment", "amount_cents": 350000,
                "adjustment_direction": "out", "date": "2026-11-23", "...": "..." },
  "warnings": []
}
```
Si la cuenta ya cuadra → `200 OK`:
```json
{ "status": "already_balanced", "movement": null, "balance_cents": 17150000, "warnings": [] }
```

**Listar con filtros**:
`GET /api/v1/movements?date_from=2026-11-01&date_to=2026-11-30&account_id=c4d0…a3&type=expense&type=income&limit=50&offset=0`
→ `200 OK`
```json
{
  "items": [ { "id": "…", "type": "expense", "...": "..." } ],
  "totals": {
    "income_cents": 201234567,
    "yield_cents": 1234567,
    "expense_cents": 3200000,
    "net_cents": 198034567
  },
  "page": { "limit": 50, "offset": 0, "total_items": 7 }
}
```

**Parámetros de `GET /movements`:**

| Parámetro | Qué hace |
|-----------|----------|
| `date_from`, `date_to` | Rango de fechas, ambos inclusivos |
| `account_id`, `category_id`, `type` | Se pueden repetir; dentro de cada uno se combinan con «o» |
| `include_voided` | `false` por defecto |
| `limit`, `offset` | Paginación (ver 5.1) |

**Corregir**: `PATCH /api/v1/movements/1a2b…m2`
```json
{ "amount_cents": 2500000 }
```
→ `200 OK`
```json
{ "movement": { "...": "...", "version": 2 }, "changed": true, "warnings": [] }
```
Si no hay cambios reales, la respuesta es `200` con `"changed": false` y
no se crea versión.

**Anular**: `POST /api/v1/movements/…m6/void`
```json
{ "reason": "Registrado dos veces" }
```
→ `200 OK` con `{ "movement": {…, "voided": true}, "warnings": [] }`

**Historial**: `GET /api/v1/movements/1a2b…m2/history` → `200 OK`
```json
{
  "movement_id": "1a2b…m2",
  "versions": [
    { "version": 1, "created_at": "2026-11-03T12:10:00-05:00", "changed_fields": [],
      "amount_cents": 2300000, "date": "2026-11-03", "from_account": {"id": "…", "name": "Nequi"},
      "to_account": null, "category": {"id": "…", "name": "Domicilios"},
      "merchant": "rappi", "note": "Almuerzo" },
    { "version": 2, "created_at": "2026-11-03T18:40:00-05:00", "changed_fields": ["amount_cents"],
      "amount_cents": 2500000, "...": "..." }
  ],
  "voided": null
}
```
Si el movimiento está anulado, `"voided"` es
`{ "at": "...", "reason": "..." }`.

**Saldos**: `GET /api/v1/balances` → `200 OK`
```json
{
  "accounts": [
    { "id": "…a1", "name": "Lulo",     "type": "bank",           "parent_id": null,   "archived": false, "balance_cents": 279300000 },
    { "id": "…a2", "name": "Ahorro",   "type": "pocket",         "parent_id": "…a1",  "archived": false, "balance_cents": 351234567 },
    { "id": "…a3", "name": "Nequi",    "type": "digital_wallet", "parent_id": null,   "archived": false, "balance_cents": 17150000 },
    { "id": "…a4", "name": "Efectivo", "type": "cash",           "parent_id": null,   "archived": false, "balance_cents": 25000000 }
  ],
  "groups": [
    { "bank_id": "…a1", "name": "Lulo", "subtotal_cents": 630534567 }
  ],
  "total_cents": 672684567
}
```

**Comercios**: `GET /api/v1/merchants?limit=20` → `200 OK`
```json
{ "items": [ { "merchant": "rappi", "uses": 12 }, { "merchant": "D1", "uses": 7 } ] }
```

### 4.4 Formato estándar de errores y códigos HTTP

Todo error tiene la misma forma:
```json
{
  "error": {
    "type": "invalid_data",
    "field": "date",
    "message": "No se admiten fechas futuras.",
    "details": []
  }
}
```
- **`field`** es la ruta del campo que falló (`"amount_cents"`,
  `"from_account_id"`…) o `null` si el error no es de un campo concreto.
  En los parámetros de consulta que se pueden repetir (`account_id`,
  `category_id`, `type` en `GET /movements`), la ruta incluye la
  posición del valor que falló, contando desde 0: `"type.0"` es el
  primer `type` de la URL.
- **`details`** lista los errores adicionales cuando falla más de un
  campo, cada uno con `{field, message}`.

| HTTP | `type` | Cuándo (ejemplos) |
|------|--------|-------------------|
| 401 | `unauthorized` | Falta la contraseña o es incorrecta |
| 404 | `not_found` | El recurso no existe **o es de otro usuario** (RF-22), incluidos los IDs usados en filtros |
| 409 | `conflict` | Nombre duplicado, cuenta o categoría archivada en un movimiento nuevo, archivar con saldo ≠ 0 o con bolsillos activos, borrar algo usado, corregir un anulado o un ajuste, anular dos veces |
| 422 | `invalid_data` | Monto ≤ 0 o no entero, fecha futura, inexistente o anterior al inicio, forma inválida para el tipo, categoría de clase incorrecta, cambio de tipo, rango invertido, longitudes excedidas, `limit` fuera de rango |
| 500 | `internal` | Fallo inesperado. Mensaje genérico, sin detalles internos (no es un caso de la spec; existe por robustez) |

Los errores de validación de Pydantic se convierten a este mismo formato
con un handler propio. Así el cliente nunca ve el formato por defecto de
FastAPI.

---

## 5. Detalles técnicos que la spec delegó al plan

### 5.1 Paginación
- Se pagina con `limit` y `offset`. `limit` vale 50 por defecto, con
  mínimo 1 y máximo 200. `offset` es ≥ 0.
- **Orden total y estable:** `date DESC, created_at DESC, id DESC`. El
  `id` desempata los movimientos registrados en el mismo instante.
- `page.total_items` cuenta el conjunto filtrado completo. Los `totals`
  se calculan sobre ese mismo conjunto completo, en una consulta aparte
  con `SUM … FILTER`, no sobre la página.

### 5.2 Longitudes máximas

| Campo | Mínimo | Máximo |
|-------|--------|--------|
| Nombre de cuenta | 1 | 60 |
| Nombre de categoría | 1 | 40 |
| Comercio | 1 (si no, se trata como ausente) | 80 |
| Nota | 1 (si no, se trata como ausente) | 500 |
| Motivo de anulación | 1 (si no, se trata como ausente) | 200 |

Las longitudes se miden **después** de recortar espacios.

### 5.3 Normalización de textos

```
función forma_mostrada(texto):
    t ← quitar espacios al inicio y al final
    t ← reemplazar secuencias de espacios internos por uno solo
    devolver t, o NULL si queda vacío

función clave(texto):
    devolver casefold(forma_mostrada(texto))
```

`casefold` es un `lower` más agresivo, pensado para Unicode.

- Se aplica igual a los nombres de cuentas y categorías (`name_key`) y al
  comercio (`merchant_key`).
- **No** se quitan tildes: «Éxito» y «Exito» son comercios distintos. La
  spec solo pide igualar espacios y mayúsculas.
- **Lista de comercios:** se agrupa por `merchant_key` entre los
  movimientos **vigentes** del usuario. Se ordena por número de usos
  (descendente) y, a igual uso, por último uso (descendente). Para cada
  clave se muestra la forma mostrada más reciente.
  - **Tope (`limit`):** 20 por defecto (§4.2), con mínimo 1 y máximo 200,
    los mismos límites que el listado de movimientos (§5.1). Fuera de ese
    rango, `422`.
  - **«Último uso» y «más reciente»:** se decide por la **fecha del
    movimiento** y, en el mismo día, por su **momento de registro**
    (`created_at`), ambos descendentes. Es el mismo orden que el listado
    (§5.1). Si aun así empatan, se desempata por `id` para elegir la forma
    mostrada y por `merchant_key` para ordenar la lista, así el resultado
    es siempre el mismo.

### 5.4 Categorías precargadas
- Viven en `domain/defaults.py`, como una lista inmutable de
  `(nombre, clase)` con los 12 gastos y 4 ingresos de RF-3.
- `services/bootstrap.py → ensure_initial_user()` corre al arrancar la
  app:
  - si `users` está vacía, crea el usuario y sus categorías en una sola
    transacción;
  - si ya existe un usuario, no hace nada (es **idempotente**: se puede
    ejecutar muchas veces y el resultado es el mismo).
- Para la spec 004, la misma función de siembra de categorías se reutiliza
  al registrar cada usuario nuevo.
- **Usuario actual:** hasta la spec 004, `get_owner_id()` devuelve el id
  del único usuario, cacheado al arrancar. Los servicios **siempre**
  reciben `owner_id` como parámetro, y los tests de aislamiento lo
  sustituyen para simular un segundo usuario.

### 5.5 Fijar «hoy» en los tests

```python
# domain/dates.py — interfaz pura
BOGOTA = ZoneInfo("America/Bogota")

class Clock(Protocol):
    def now(self) -> datetime: ...          # con zona horaria
    def today(self) -> date: ...            # = now() en Bogotá, como fecha

class SystemClock:   now = datetime.now(BOGOTA)
class FixedClock:    construido con un instante fijo; se puede avanzar en el test
```

- Los servicios reciben `clock` como parámetro. FastAPI lo inyecta con la
  dependencia `get_clock()`, que en producción devuelve `SystemClock`.
- En `tests/conftest.py`,
  `app.dependency_overrides[get_clock] = lambda: FixedClock("2026-11-23T10:00-05:00")`.
- Hay un test específico del cambio de día: con `FixedClock` a las
  `23:59:59-05:00` del día 23, la fecha 24 es futura y se rechaza; a las
  `00:00:00-05:00` del 24, se acepta.
- Ningún código usa `date.today()`, `datetime.now()` ni `now()` de
  PostgreSQL. Una regla de revisión y un test que busca esas llamadas en
  `src/` lo comprueban.

### 5.6 Protección con contraseña única (RNF-4)
- **Configuración:** la variable `APP_PASSWORD` se lee en `config.py`. Si
  falta, tiene menos de 12 caracteres o contiene caracteres que no sean
  ASCII imprimibles sin espacios (`!`…`~`), `Settings` lanza un error y
  **la app no arranca**. Motivo: viaja en una cabecera HTTP, que solo
  admite ASCII; una «ñ» o una tilde la harían imposible de enviar.
- **Entorno:** la variable `APP_ENV` acepta `local` o `production`, y vale
  `production` por defecto. Si alguien olvida configurarla, queda la
  opción más segura.
- **Verificación:** la dependencia global `require_password` lee
  `Authorization: Bearer <valor>` y la compara con
  `hmac.compare_digest`, una comparación en tiempo constante que no
  revela por timing cuántos caracteres acertaste. Si no coincide, responde
  `401 unauthorized`.
- **Excepciones (RNF-4):**
  - `GET /api/v1/health` es **siempre** público.
  - `/docs` y `/openapi.json` se registran **solo si `APP_ENV=local`**.
    En ese caso no piden contraseña, porque no tienen datos, y Swagger UI
    trae un botón «Authorize» para escribirla.
  - En `production`, FastAPI se crea con `docs_url=None`,
    `redoc_url=None` y `openapi_url=None`, así que esas rutas responden
    `404`.
- **Repositorio:** la contraseña nunca está en git. `.env.example` lleva
  un marcador vacío y los tests usan un valor de prueba fijo, no secreto.

### 5.7 Integración continua (CI)

Archivo `.github/workflows/ci.yml`, que corre en cada `push` y en cada
pull request:

```yaml
jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_USER: finanzas, POSTGRES_PASSWORD: finanzas, POSTGRES_DB: finanzas_test }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready
    env:
      DATABASE_URL: postgresql+psycopg://finanzas:finanzas@localhost:5432/finanzas_test
      APP_PASSWORD: ci-password-not-secret
    defaults: { run: { working-directory: backend } }
    steps:
      - checkout
      - instalar uv (astral-sh/setup-uv)
      - uv sync --frozen
      - uv run ruff check .
      - uv run ruff format --check .
      - uv run alembic upgrade head
      - uv run pytest --cov=finanzas --cov-fail-under=90
```

- **RNF-3** (rendimiento) está marcado con `@pytest.mark.perf` y no corre
  en CI, porque la máquina de CI varía. Se ejecuta en local con
  `uv run pytest -m perf`. Por defecto, pytest lo excluye
  (`addopts = "-m 'not perf'"`).
- **Base de datos de tests:** cada test corre dentro de una transacción
  que se deshace al final (rollback). Así los tests no se contaminan entre
  sí y son rápidos. Las migraciones se aplican una vez por sesión.

---

## 6. Entorno local

### 6.1 Docker Compose (`docker-compose.yml` en la raíz)

| Servicio | Imagen | Qué hace |
|----------|--------|----------|
| `db` | `postgres:16` | Base de datos en el puerto 5432, con volumen `pgdata` para no perder datos al reiniciar y healthcheck `pg_isready`. Crea `finanzas` y `finanzas_test`. |
| `api` | `build: ./backend` | Al arrancar ejecuta `alembic upgrade head` y después el servidor en el puerto 8000. Espera a que `db` esté sano y lee `.env`. |

Dos formas de trabajar:
- **Todo en Docker:** `docker compose up`.
- **Solo la BD en Docker** (recomendado para desarrollar): `docker
  compose up -d db`, y la API en local con `uv` para tener recarga
  automática.

### 6.2 Variables (`.env.example`, que sí va en git)

```
POSTGRES_USER=finanzas
POSTGRES_PASSWORD=finanzas
POSTGRES_DB=finanzas
DATABASE_URL=postgresql+psycopg://finanzas:finanzas@localhost:5432/finanzas
TEST_DATABASE_URL=postgresql+psycopg://finanzas:finanzas@localhost:5432/finanzas_test
APP_PASSWORD=
APP_ENV=local
```

Se copia a `.env`, que está ignorado por git, y se rellena
`APP_PASSWORD`. Las credenciales de Postgres de ejemplo solo sirven en
local; en producción (Neon) se usan otras, configuradas en el proveedor.

### 6.3 Comandos (desde `backend/`, salvo indicación)

| Acción | Comando |
|--------|---------|
| Levantar la BD | `docker compose up -d db` (desde la raíz) |
| Instalar dependencias | `uv sync` |
| Aplicar migraciones | `uv run alembic upgrade head` |
| Crear una migración | `uv run alembic revision --autogenerate -m "<mensaje>"` |
| Servidor de desarrollo | `uv run fastapi dev src/finanzas/main.py` → http://localhost:8000/docs |
| Tests | `uv run pytest -q` |
| Tests con cobertura | `uv run pytest --cov=finanzas --cov-fail-under=90` |
| Rendimiento (RNF-3) | `uv run pytest -m perf` |
| Lint y formato | `uv run ruff check . && uv run ruff format --check .` |

### 6.4 Dockerfile del backend (resumen)
- Imagen base `python:3.12-slim`. Se instala `uv` y se ejecuta
  `uv sync --frozen --no-dev`.
- Se copian `src/` y `alembic/`.
- `CMD`: migrar y después `fastapi run src/finanzas/main.py --port 8000`.
- El contenedor corre con un usuario sin privilegios.

---

### 6.5 Levantar todo desde cero (primera vez)

1. `cp .env.example .env` y escribir una `APP_PASSWORD` de 12 caracteres
   o más.
2. `docker compose up -d db` para arrancar PostgreSQL.
3. `cd backend && uv sync` para instalar Python y las dependencias.
4. `uv run alembic upgrade head` para crear las tablas.
5. `uv run fastapi dev src/finanzas/main.py`. Al arrancar se crean el
   usuario inicial y sus categorías.
6. Abrir http://localhost:8000/docs, pulsar «Authorize», escribir la
   contraseña y probar los endpoints.
7. `uv run pytest -q` para confirmar que todo pasa.

---

## 7. Decisiones técnicas

| # | Decisión | Alternativa descartada | Por qué |
|---|----------|------------------------|---------|
| DT-1 | El saldo se **calcula en cada consulta** con SQL agregado | Guardar una columna `balance` que se actualiza en cada movimiento | El principio 3 prohíbe un saldo guardado: podría descuadrarse. Con 10.000 movimientos, calcularlo cuesta milisegundos. |
| DT-2 | Columnas `from_account_id` y `to_account_id` uniformes para todos los tipos | Un monto con signo (`-2500000` para gastos) | El principio 2 exige montos positivos. Además, con from/to una transferencia es una sola fila y el saldo sale de una sola fórmula. |
| DT-3 | Tabla `movement_versions` con **todas** las versiones, incluida la inicial | *Event sourcing* (guardar solo eventos y reconstruir el estado) | El historial queda completo y fácil de consultar sin la complejidad de reconstruir estados. `movements` es una «foto» rápida del estado actual. |
| DT-4 | La anulación es un estado del movimiento (`voided_at`) | Un contra-asiento (un movimiento inverso) | Lo decidiste en la spec: evita listados llenos de pares que se cancelan. |
| DT-5 | El aislamiento usa `owner_id` en todo, más llaves foráneas compuestas `(id, owner_id)` | Row Level Security (RLS) de PostgreSQL | RLS es potente, pero exige configurar variables por sesión y es difícil de depurar para empezar. Las llaves compuestas ya impiden en la BD las referencias cruzadas. RLS se puede reevaluar en la spec 004. |
| DT-6 | Bloqueo pesimista (`SELECT … FOR UPDATE`) al corregir, anular y ajustar | Bloqueo optimista (rechazar con `409` si otro cambió antes) | La spec pide que «gane la última y ambas queden en el historial», no que se rechace. |
| DT-7 | UUID como llave primaria | Enteros autoincrementales | Un id `/movements/42` deja adivinar otros ids y revela cuántos registros hay. Los UUID no se pueden adivinar, lo que refuerza RNF-5. |
| DT-8 | API síncrona | API `async` | Con un usuario y PostgreSQL local no hay ganancia, y los tests se complican. |
| DT-9 | Paginación `limit`/`offset` | Paginación por cursor (*keyset*) | Es más simple de usar y de probar. El cursor solo conviene con cientos de miles de filas. |
| DT-10 | `Clock` inyectado como dependencia | Librerías que «congelan» el tiempo (`freezegun`, `time-machine`) | Evita una dependencia extra y no parchea el reloj global. También cubre `created_at`, porque no se usa `now()` de la BD. |
| DT-11 | Contraseña en la cabecera `Authorization: Bearer` | HTTP Basic o cookie de sesión | Basic hace que el navegador muestre un diálogo propio. Las cookies exigen protección CSRF (un tipo de ataque entre sitios web). Bearer es estándar y funciona igual desde la web y desde WhatsApp. |
| DT-12 | `ENUM` de PostgreSQL para los tipos | Tablas de catálogo (`movement_types`) | Los valores son fijos y conocidos. Un catálogo solo añade joins. |
| DT-13 | Capa `services/` separada | Lógica de negocio dentro de los routers | El principio 8 exige un dominio separado. Los servicios también sirven a WhatsApp (005) y al importador (006) sin pasar por HTTP. |
| DT-14 | Tests contra **PostgreSQL real**, con rollback por test | SQLite en memoria | El principio 5 lo exige. Además, SQLite no tiene `ENUM`, ni `FOR UPDATE`, ni los mismos `CHECK`: los tests pasarían y producción fallaría. |
| DT-15 | Sin tabla de comercios | Tabla `merchants` | La spec dice que el comercio no es una entidad. Agrupar `merchant_key` basta. |

---

## 8. Estrategia de tests

**TDD:** primero se escribe el test que falla, después el código
(AGENTS.md, regla 3).

### 8.1 Niveles

| Nivel | Qué cubre | Dónde | BD |
|-------|-----------|-------|----|
| Unitarios | `domain/`: montos, fechas y `Clock`, normalización, forma por tipo, saldo puro, cálculo del ajuste, diff de versiones, advertencias | `tests/unit/` | No |
| Integración | Cada endpoint, cada RF y cada caso límite (CL-1 a CL-39) por HTTP con `TestClient` | `tests/integration/` | PostgreSQL real |
| Aislamiento | Cada operación con dos usuarios (RNF-5) | `tests/integration/test_isolation.py` | PostgreSQL real |
| Escenario | El mes de la sección 2.4 con sus valores esperados exactos (RNF-1, criterio 3) | `tests/scenarios/test_month.py` | PostgreSQL real |
| Propiedades | El saldo puro y el saldo SQL coinciden en 200 escenarios aleatorios con semilla fija | `tests/integration/test_balance_property.py` | PostgreSQL real |
| Rendimiento | p95 < 300 ms con 10.000 movimientos (RNF-3) | `tests/perf/` | PostgreSQL local, manual |

### 8.2 Fixtures sintéticos (`tests/conftest.py`)

Un *fixture* es un dato o una preparación que pytest entrega a cada test
que lo pide.

- **`db_session`:** abre una transacción al empezar y la deshace al
  terminar, así cada test parte de cero.
- **`clock`:** un `FixedClock` en `2026-11-23T10:00-05:00`, que se puede
  avanzar dentro del test.
- **`client`:** un `TestClient` con la contraseña de prueba y las
  dependencias `get_clock` y `get_owner_id` sustituidas.
- **`owner_a` y `owner_b`:** dos usuarios creados directamente en la BD,
  cada uno con sus categorías precargadas.
- **Constructores** `make_account(...)`, `make_category(...)` y
  `make_movement(...)`: tienen valores por defecto razonables y nombres
  claramente inventados («Banco Prueba», «Comercio X»).
- **`month_scenario`:** carga exactamente los datos de la sección 2.4.

**Sin datos reales ni aleatoriedad sin semilla.** No se usa ninguna
librería de datos falsos: todos los valores están escritos a mano o salen
de `random.Random(42)`. El generador sigue siendo aleatorio, pero con la
semilla fija produce siempre la misma secuencia, así que el test es
reproducible.

### 8.3 Aislamiento (RNF-5)
- **Un test parametrizado por operación:** `owner_a` crea los recursos y
  `owner_b` intenta leer, listar, corregir, anular, ajustar, usar como
  `from` o `to` o como categoría, ver el historial y pedir saldos y
  comercios.
- **Resultado esperado:** `404` idéntico al de un id inexistente (se
  compara el cuerpo completo), y los listados y saldos no incluyen nada
  del otro usuario.
- **Segunda línea de defensa:** un test inserta directamente en la BD un
  movimiento con la cuenta de otro dueño y comprueba que la FK compuesta
  lo rechaza.

### 8.4 Cobertura
- La meta es ≥ 90 % de **líneas y ramas** en `src/finanzas`
  (`--cov-branch`). La CI falla por debajo de esa cifra.
- Solo se excluyen bloques `if TYPE_CHECKING:`. Nada de `# pragma: no
  cover` para esquivar la meta.

---

## 9. Trazabilidad

Cada requisito de la spec, con la parte del plan que lo cubre y los tests
que lo verifican. Todos los tests de integración viven en
`tests/integration/`.

| Requisito | Dónde se cubre en el plan | Tests que lo verifican |
|-----------|---------------------------|------------------------|
| RF-1 Montos en centavos | §2.1, §4.1, `domain/money.py` | `unit/test_money.py` (incluye el límite 2^53 − 1); CL-11, CL-12, CL-13 |
| RF-2 Fechas | §3.5, §5.5 | `unit/test_dates.py` (incluye medianoche); CL-6, CL-7, CL-8, CL-9 |
| RF-3 Usuario inicial y categorías | §5.4 | `test_bootstrap.py` (crea 16 categorías, es idempotente); CL-31 |
| RF-4 Crear cuenta | §2.2 `accounts`, §4.2 | `test_accounts.py`; CL-10, CL-13, CL-33, CL-34 |
| RF-5 Editar, archivar y borrar cuenta | §3.8, §4.2 | `test_accounts.py`; CL-28, CL-29, CL-30 |
| RF-6 Categorías | §2.2 `categories`, §3.8 | `test_categories.py`; CL-22, CL-23, CL-31, CL-32 |
| RF-7 Datos comunes | §2.2 (tabla de forma y `ck_movement_shape`) | `unit/test_movement_shape.py`, `test_movements.py` |
| RF-8 Gasto | §3.5 | `test_movements.py`; CL-1, CL-3, CL-23 |
| RF-9 Ingreso | §3.5 | `test_movements.py`; CL-38 |
| RF-10 Transferencia | §3.5 | `test_movements.py`; CL-3, CL-4, CL-5 |
| RF-11 Rendimiento | §3.5 | `test_movements.py`; CL-12, CL-38 |
| RF-12 Ajuste | §3.3 | `unit/test_adjustments.py`, `test_adjustments.py`; CL-14 a CL-18 |
| RF-13 Comercio y nota | §5.2, §5.3 | `unit/test_text.py`, `test_merchants.py`; CL-24 |
| RF-14 Advertencias | §3.4 | `unit/test_warnings.py`; CL-1, CL-2, CL-16, CL-19, CL-26, CL-27 |
| RF-15 Saldo por cuenta | §3.1 | `unit/test_balances.py`, `test_balance_property.py`, `scenarios/test_month.py` |
| RF-16 Saldo agrupado y total | §3.2 | `test_balances_api.py`; CL-4; `scenarios/test_month.py` |
| RF-17 Listar y filtrar | §4.3, §5.1 | `test_list_movements.py`; CL-35 a CL-38 |
| RF-18 Ver movimiento | §4.2 | `test_movements.py` |
| RF-19 Corregir | §3.6 | `test_corrections.py` (incluye una prueba de concurrencia con dos conexiones); CL-19 a CL-25 |
| RF-20 Historial | §2.2 `movement_versions`, §3.6 | `test_history.py` |
| RF-21 Anular | §3.7 | `test_void.py`; CL-18, CL-25, CL-26, CL-27 |
| RF-22 Errores y operaciones completas | §4.4 | `test_errors.py` (formato, que no queden cambios parciales, tipos y campos); CL-39 |
| RNF-1 Exactitud | §2.4, §8.1 | `scenarios/test_month.py` (valores fijos) |
| RNF-2 Trazabilidad | §2.2 (versiones solo de inserción), §3.6, §3.7 | `test_history.py`, `test_void.py` (nada se borra); revisión: no existe ningún endpoint ni SQL que borre movimientos o versiones |
| RNF-3 Rendimiento | §5.7, §8.1 | `perf/test_rnf3.py` (manual, en local) |
| RNF-4 Acceso | §5.6 | `test_auth.py` (`401` sin contraseña o con una incorrecta; la app no arranca sin `APP_PASSWORD`; `/health` es público; `/docs` y `/openapi.json` responden `200` con `APP_ENV=local` y `404` con `production`) |
| RNF-5 Aislamiento | §2.1, §5.4, §8.3 | `test_isolation.py` (todas las operaciones y la FK compuesta) |
| RNF-6 Datos sintéticos | §6.2, §8.2, `.gitignore` | Revisión en cada PR |
| RNF-7 Idioma | §4.4, `domain/messages.py` | `test_errors.py`: todo mensaje de error o advertencia sale del catálogo en español, incluidos los errores de Pydantic traducidos |
| RNF-8 Verificabilidad | §5.5, §5.7, §8.4 | CI con `--cov-fail-under=90`; `FixedClock` en todos los tests |
| RNF-9 Interfaz documentada | §4, FastAPI/OpenAPI | `test_docs.py` (`/openapi.json` responde y lista todos los endpoints); revisión de `/docs` |

Los 22 RF y los 9 RNF tienen cobertura, así como los 39 casos límite.

---

## 10. Riesgos

Nada de la spec es imposible. Estos puntos son más costosos o requieren
una decisión tuya. **No los he cambiado por mi cuenta.**

| # | Riesgo | Impacto | Qué propongo |
|---|--------|---------|--------------|
| R-1 | **RNF-4 dice «toda petición»**, pero Swagger UI necesita cargar `/openapi.json` sin contraseña para ser explorable (RNF-9). Los dos requisitos chocan. | Medio | **Resuelto:** `/health` siempre es público; `/docs` y `/openapi.json` solo en local y desactivados en producción. Ya está recogido en RNF-4. |
| R-2 | **Límite técnico de monto.** La spec dice «sin monto máximo», pero JavaScript (la web de la 002) solo representa enteros exactos hasta 2^53−1 ≈ 9 × 10^15 centavos (unos 90 billones de pesos). | Bajo | **Resuelto:** se rechazan los montos y saldos mayores, como límite técnico y no de negocio. Ya está recogido en RF-1. |
| R-3 | **Mensajes en español (RNF-7):** Pydantic genera sus mensajes de validación en inglés. | Medio (trabajo extra) | Un handler que traduce cada tipo de error de Pydantic usando el catálogo `domain/messages.py`. |
| R-4 | **Probar la concurrencia de RF-19** (dos correcciones «casi a la vez») exige un test con dos conexiones y dos hilos. Es más difícil de escribir y puede ser inestable. | Medio | Un test con dos sesiones, sin `sleep` arbitrarios: la segunda espera el bloqueo de la primera. |
| R-5 | **Contraseña única sin límite de intentos.** Si se desplegara antes de la 004, alguien podría probar contraseñas sin freno. | Bajo (mientras sea local) | Mínimo de 12 caracteres. El límite de intentos queda para la 004. No desplegar antes de la 004. |
| R-6 | **RNF-3 depende del equipo.** p95 < 300 ms se mide en tu computador, no en CI. | Bajo | Se mide en local, que es lo que dice la spec. Si el equipo es muy lento, se revisan los índices antes de tocar el diseño. |
| R-7 | **Crecimiento futuro.** El saldo calculado en cada consulta es rápido con 10.000 movimientos, pero con años de datos y la importación del Excel (006) podría ir más lento. | Bajo hoy | No se cambia nada ahora (principio 3). Si hiciera falta, una caché derivada y recalculable sería compatible con la constitución. |
| R-8 | **Volumen de tests de aislamiento.** Probar cada operación con dos usuarios multiplica los tests. | Bajo | Tests parametrizados, una sola función para todas las operaciones. |

---

## 11. Cambios pendientes en otros documentos

Los tres cambios fueron **aprobados y aplicados** el 2026-11-23:

1. **AGENTS.md, estructura de carpetas:** se añadieron `services/`,
   `tests/scenarios/` y `tests/perf/`.
2. **spec.md, RNF-4:** `/health` es siempre público. La documentación de
   la API y su esquema son públicos solo en local y están desactivados en
   producción (R-1).
3. **spec.md, RF-1:** se añadió el límite técnico de 2^53 − 1 centavos
   (R-2).

No quedan cambios pendientes.

---

## 12. Explicación simple

- **Qué vamos a construir:** el «motor» de la app, sin pantallas
  todavía. Es como el motor de un carro: no tiene volante ni asientos,
  pero es lo que hace que funcione. Le hablas mandándole mensajes con un
  formato fijo (eso es la **API**), y te responde con tus saldos y
  movimientos.

- **Cómo está organizado:** en cuatro pisos, como un restaurante:
  - **`api`** es el mesero: toma tu pedido, revisa que esté bien escrito
    y te trae la respuesta.
  - **`services`** es el jefe de cocina: decide los pasos de cada plato
    (registrar un gasto, anular, ajustar).
  - **`domain`** es el recetario: las reglas puras («un monto debe ser
    positivo», «el saldo es el inicial más lo que entra menos lo que
    sale»).
  - **`db`** es la despensa: donde se guarda todo, en PostgreSQL.

- **Cómo se guardan los datos:** en tablas, como hojas de Excel, pero
  con reglas que la base de datos hace cumplir sola.
  - Hay tablas para usuarios, cuentas, categorías, movimientos y el
    historial de versiones de cada movimiento.
  - Cada fila lleva la marca de su **dueño**, para que nadie vea lo de
    otro.
  - El saldo **no se guarda**: se recalcula siempre sumando los
    movimientos. Así es imposible que se descuadre, como un cuaderno donde
    nunca borras con borrador.

- **Cómo se manejan los errores:** corregir un movimiento guarda una
  copia de cómo era antes, como el historial de versiones de Google Docs.
  Anular lo tacha sin borrarlo: sigue visible, pero ya no cuenta.

- **Cómo sabemos que funciona:**
  - Cientos de pruebas automáticas revisan cada regla. Una de ellas
    simula un mes completo con datos inventados y comprueba que los saldos
    den exactamente los números calculados a mano en este plan.
  - Cada vez que subes código a GitHub, un robot (la **CI**) corre todas
    las pruebas y el revisor de estilo. Si algo falla, te avisa.

- **Cómo lo usas en tu computador:**
  - **Docker** arranca la base de datos en una «cajita» aislada, sin
    instalar PostgreSQL a mano.
  - **uv** instala Python y las librerías.
  - **Alembic** crea las tablas.
  - Después abres una página (`/docs`) donde puedes probar todo con
    botones, protegida con tu contraseña.

- **Qué queda por decidir:** nada. Las tres dudas de la sección 11 ya
  están resueltas. La página de pruebas `/docs` solo existe en tu
  computador. En internet está apagada, como una puerta trasera que
  tapiamos antes de abrir el local al público.
