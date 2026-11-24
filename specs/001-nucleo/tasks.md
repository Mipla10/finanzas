# Tareas 001 — Núcleo

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
- **Estado:** Pendiente de aprobación
- **Fecha:** 2026-11-23

## Cómo usar este archivo

1. **Una tarea a la vez, en orden.** Una tarea solo empieza cuando todas
   sus dependencias están marcadas `[x]` (regla 4 de AGENTS.md).
2. **Tests primero.** Se escribe el test de «Tests primero:», se ejecuta y
   se comprueba que falla. Después se escribe el código mínimo que lo hace
   pasar y, al final, se refactoriza.
3. **Hecho cuando.** La tarea está terminada cuando se cumple su línea
   «Hecho cuando:», y además `uv run pytest -q` y
   `uv run ruff check . && uv run ruff format --check .` pasan desde
   `backend/`.
4. **Commit propio.** Se marca la casilla `[x]` y se hace un commit con el
   mensaje indicado (Conventional Commits). Después se detiene el trabajo
   para revisión.
5. **Si la tarea necesita algo que la spec o el plan no dicen**, no se
   improvisa: se propone el cambio primero (regla 5).

**Duración:** cada tarea está pensada para 20–30 minutos.

**Nombres de tests:** los tests de servicios van en
`tests/integration/test_<tema>_service.py` y los de la API en
`tests/integration/test_<tema>_api.py`. Es un detalle más fino que los
nombres de la tabla de trazabilidad del plan (§9). Cada caso límite se
prueba en una función `test_cl_<n>_…` (por ejemplo, `test_cl_23_…`).

---

## Fase 1 — Preparación del entorno

- [x] **T1 · Proyecto backend con uv**
  - **Cubre:** base para todo · Plan §1.2, §1.3, §6.3
  - **Depende de:** —
  - **Tests primero:** `tests/test_smoke.py` comprueba que `import finanzas` funciona.
  - **Hecho cuando:** desde `backend/`, `uv run pytest -q` pasa 1 test y `uv run ruff check .` no reporta errores.
  - **En simple:** se crea la carpeta del backend con Python y las herramientas para probar y revisar el estilo.
  - **Commit:** `chore(001): T1 crear proyecto backend con uv`

- [x] **T2 · PostgreSQL con Docker Compose y `.env.example`**
  - **Cubre:** RNF-6 (sin secretos en git) · Plan §6.1, §6.2
  - **Depende de:** T1
  - **Tests primero:** `tests/integration/test_db_connection.py` ejecuta `SELECT 1` contra `TEST_DATABASE_URL`. Falla mientras la BD no esté levantada.
  - **Hecho cuando:**
    - `docker compose up -d db` deja el servicio sano;
    - existen las bases `finanzas` y `finanzas_test`;
    - el test pasa;
    - `git status` no muestra `.env`.
  - **En simple:** se arranca la base de datos en una «cajita» de Docker y se deja un archivo de ejemplo con la configuración, sin contraseñas reales.
  - **Commit:** `chore(001): T2 postgres en docker compose`

- [x] **T3 · Configuración (`config.py`)**
  - **Cubre:** RNF-4 · Plan §5.6
  - **Depende de:** T1
  - **Tests primero:** `tests/unit/test_config.py`:
    - sin `APP_PASSWORD`, falla;
    - con menos de 12 caracteres, falla;
    - `APP_ENV` vale `production` por defecto y solo acepta `local` o `production`.
  - **Hecho cuando:** `uv run pytest tests/unit/test_config.py` pasa.
  - **En simple:** la app lee su configuración y se niega a arrancar si no tiene contraseña.
  - **Commit:** `feat(001): T3 configuración con contraseña obligatoria`

- [x] **T4 · Reloj inyectable (`Clock`)**
  - **Cubre:** RF-2, RNF-8 · Plan §5.5
  - **Depende de:** T1
  - **Tests primero:** `tests/unit/test_dates.py` comprueba:
    - `SystemClock().today()` usa la zona de Bogotá;
    - un `FixedClock` en 23:59:59-05:00 da el día 23 y, al avanzarlo 1 segundo, da el 24;
    - `tests/unit/test_no_direct_now.py` no encuentra `date.today(`, `datetime.now(` ni `func.now(` en `src/` (salvo dentro de `SystemClock`).
  - **Hecho cuando:** los dos archivos de test pasan.
  - **En simple:** un «reloj» que la app consulta para saber qué día es hoy en Colombia y que los tests pueden detener en el día que quieran.
  - **Commit:** `feat(001): T4 reloj inyectable con hora de Bogotá`

- [x] **T5 · Alembic, sesión de BD y fixture con rollback**
  - **Cubre:** base de la fase 2 · Plan §6.3, §8.2 (`db_session`)
  - **Depende de:** T2, T3
  - **Tests primero:** `tests/integration/test_db_session.py`. Un test inserta en una tabla temporal y el siguiente comprueba que no ve ese dato.
  - **Hecho cuando:** `uv run alembic upgrade head` corre sin errores con la base vacía y el test pasa.
  - **En simple:** se prepara el sistema que crea las tablas y una forma de que cada prueba deje la base de datos limpia al terminar.
  - **Commit:** `chore(001): T5 alembic y sesión de pruebas con rollback`

- [x] **T6 · Integración continua (GitHub Actions)**
  - **Cubre:** RNF-8, criterio de finalización 8 · Plan §5.7
  - **Depende de:** T5
  - **Tests primero:** no aplica. La CI ejecuta los tests que ya existen (T1–T5).
  - **Hecho cuando:**
    - existe `.github/workflows/ci.yml` con ruff, alembic y pytest con `--cov-fail-under=90`;
    - los mismos comandos pasan en local;
    - tras el próximo push, el workflow aparece en verde en GitHub.
  - **En simple:** un robot que, cada vez que se sube código, corre todas las pruebas y avisa si algo se rompió.
  - **Commit:** `ci(001): T6 workflow de lint y tests`

- [x] **T7 · App FastAPI mínima: `/health` y documentación según entorno**
  - **Cubre:** RNF-4 (excepciones), RNF-9 · Plan §4.2, §5.6
  - **Depende de:** T3
  - **Tests primero:** `tests/integration/test_app_api.py` comprueba:
    - `GET /api/v1/health` responde `200` sin contraseña;
    - con `APP_ENV=local`, `/docs` y `/openapi.json` responden `200`;
    - con `production`, responden `404`.
  - **Hecho cuando:** el test pasa y `uv run fastapi dev src/finanzas/main.py` muestra `/docs` en local.
  - **En simple:** la app ya «contesta el teléfono»: tiene una ruta para saber si está viva y una página de documentación que solo existe en tu computador.
  - **Commit:** `feat(001): T7 app mínima con health y docs solo en local`

- [x] **T8 · Contraseña única en todas las rutas**
  - **Cubre:** RNF-4 · Plan §5.6, DT-11
  - **Depende de:** T7
  - **Tests primero:** `tests/integration/test_auth_api.py`, sobre una ruta protegida de prueba:
    - sin cabecera → `401`;
    - con una contraseña incorrecta → `401`;
    - con la correcta → `200`;
    - `/health` sigue siendo público.
  - **Hecho cuando:** el test pasa y la comparación usa `hmac.compare_digest`.
  - **En simple:** se pone la cerradura: sin la contraseña nadie entra, salvo a la ruta de «estoy vivo».
  - **Commit:** `feat(001): T8 proteger la api con contraseña única`

- [x] **T9 · Errores de dominio y formato estándar**
  - **Cubre:** RF-22, RNF-7 · Plan §4.4
  - **Depende de:** T8
  - **Tests primero:** `tests/integration/test_errors_api.py`. Rutas de prueba lanzan `InvalidData`, `NotFound` y `Conflict`, y se comprueba que la respuesta es `422`, `404` y `409` con el formato `{"error": {type, field, message, details}}` y un mensaje del catálogo `domain/messages.py`.
  - **Hecho cuando:** el test pasa.
  - **En simple:** todos los errores se responden igual y en español, para que la web y WhatsApp sepan qué falló.
  - **Commit:** `feat(001): T9 formato estándar de errores`

- [x] **T10 · Errores de validación traducidos al español**
  - **Cubre:** RF-22, RNF-7 · Plan §4.4, riesgo R-3
  - **Depende de:** T9
  - **Tests primero:** mismo archivo que T9. Un JSON con un campo faltante, un tipo equivocado o un texto demasiado largo devuelve `422 invalid_data`, con `field` correcto y un mensaje en español (sin textos en inglés de Pydantic).
  - **Hecho cuando:** el test pasa.
  - **En simple:** cuando envías datos mal escritos, el error te lo dice en español y señala qué campo está mal.
  - **Commit:** `feat(001): T10 traducir errores de validación`

---

## Fase 2 — Modelo de datos y migraciones

- [x] **T11 · Tablas `users` y `accounts`**
  - **Cubre:** RF-4, RNF-5 · CL-33 (a nivel de BD) · Plan §2.1, §2.2
  - **Depende de:** T5
  - **Tests primero:** `tests/integration/test_schema_accounts.py`:
    - un bolsillo sin padre se rechaza;
    - una cuenta no bolsillo con padre se rechaza;
    - un `name_key` duplicado del mismo dueño se rechaza;
    - el mismo nombre con otro dueño se acepta;
    - un padre que es de otro dueño se rechaza (FK compuesta).
  - **Hecho cuando:** la migración `0001` aplica, el test pasa y `alembic downgrade base` funciona.
  - **En simple:** se crean las tablas de usuarios y cuentas, con reglas que la base de datos hace cumplir sola.
  - **Commit:** `feat(001): T11 tablas users y accounts`

- [x] **T12 · Tabla `categories`**
  - **Cubre:** RF-6, RNF-5 · Plan §2.2
  - **Depende de:** T11
  - **Tests primero:** `tests/integration/test_schema_categories.py`. Se rechaza un nombre duplicado en la misma clase y dueño, y se acepta el mismo nombre en otra clase.
  - **Hecho cuando:** la migración aplica y revierte, y el test pasa.
  - **En simple:** se crea la tabla de categorías.
  - **Commit:** `feat(001): T12 tabla categories`

- [x] **T13 · Tabla `movements`**
  - **Cubre:** RF-7, RNF-5 · Plan §2.2 (tabla de forma y `ck_movement_shape`), índices
  - **Depende de:** T12
  - **Tests primero:** `tests/integration/test_schema_movements.py`:
    - cada uno de los 6 casos de la tabla de forma se inserta;
    - se rechazan: un gasto sin categoría, una transferencia con origen igual al destino, un ajuste con dos cuentas, un monto `0`, y una cuenta o categoría de otro dueño.
  - **Hecho cuando:** la migración aplica y revierte, y el test pasa.
  - **En simple:** se crea la tabla de movimientos, que ya impide guardar uno «mal armado».
  - **Commit:** `feat(001): T13 tabla movements con restricciones por tipo`

- [x] **T14 · Tabla `movement_versions`**
  - **Cubre:** RF-20, RNF-2, RNF-5 · Plan §2.2
  - **Depende de:** T13
  - **Tests primero:** `tests/integration/test_schema_versions.py`. Se rechaza un `(movement_id, version_no)` duplicado y una versión que apunta a un movimiento de otro dueño. `tests/integration/test_migrations.py` hace `downgrade base` y `upgrade head` de ida y vuelta.
  - **Hecho cuando:** los dos tests pasan.
  - **En simple:** se crea la tabla donde se guarda cada versión de un movimiento, como el historial de Google Docs.
  - **Commit:** `feat(001): T14 tabla movement_versions`

- [x] **T15 · Fixtures sintéticos**
  - **Cubre:** RNF-5, RNF-6 · Plan §8.2
  - **Depende de:** T14, T4
  - **Tests primero:** `tests/integration/test_fixtures.py` comprueba:
    - `owner_a` y `owner_b` son distintos;
    - `make_account`, `make_category` y `make_movement` crean filas del dueño indicado;
    - `clock` está en 2026-11-23 10:00-05:00.
  - **Hecho cuando:** el test pasa y los nombres de los datos son claramente inventados.
  - **En simple:** «moldes» para crear datos de prueba inventados rápido, con dos usuarios para probar que no se mezclan.
  - **Commit:** `test(001): T15 fixtures sintéticos`

---

## Fase 3 — Dominio y servicios

### 3a. Reglas puras (sin base de datos)

- [x] **T16 · Montos en centavos (`domain/money.py`)**
  - **Cubre:** RF-1 · CL-11, CL-12, CL-13 · Plan §4.1
  - **Depende de:** T9
  - **Tests primero:** `tests/unit/test_money.py`:
    - `0`, `-500000`, `2500.5`, `"25.000"` y `2^53` como monto se rechazan;
    - `123456` se acepta;
    - como saldo, `0`, `-500000` y `2^53 − 1` se aceptan y `2^53` se rechaza.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la regla que asegura que todo el dinero son centavos enteros, sin decimales que se pierdan.
  - **Commit:** `feat(001): T16 validar montos en centavos`

- [x] **T17 · Normalización de textos (`domain/text.py`)**
  - **Cubre:** RF-13 · CL-24, CL-33 · Plan §5.2, §5.3
  - **Depende de:** T9
  - **Tests primero:** `tests/unit/test_text.py`:
    - `"  rappi "`, `"RAPPI"` y `"Rappi"` tienen la misma clave;
    - `"Mc   Donalds"` se muestra como `"Mc Donalds"`;
    - `"   "` cuenta como ausente;
    - «Éxito» y «Exito» tienen claves distintas;
    - se respetan los límites de 60, 40, 80, 500 y 200 caracteres.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la regla que hace que «rappi» y «RAPPI» se reconozcan como el mismo comercio.
  - **Commit:** `feat(001): T17 normalizar nombres y comercio`

- [x] **T18 · Reglas de fecha**
  - **Cubre:** RF-2 · CL-6, CL-8, CL-9, CL-10 · Plan §3.5
  - **Depende de:** T4, T9
  - **Tests primero:** `tests/unit/test_date_rules.py`:
    - mañana se rechaza (futura);
    - una fecha igual al inicio de la cuenta se acepta;
    - un día antes del inicio se rechaza;
    - una fecha de inicio futura para una cuenta se rechaza.
  - **Hecho cuando:** el test pasa.
  - **En simple:** las reglas de qué fechas son válidas: nada del futuro ni de antes de que existiera la cuenta.
  - **Commit:** `feat(001): T18 reglas de fecha`

- [x] **T19 · Forma por tipo y diff de versiones (`domain/movements.py`)**
  - **Cubre:** RF-7 a RF-11, RF-19 · CL-5 · Plan §2.2 (tabla de forma), §3.6
  - **Depende de:** T16, T17
  - **Tests primero:** `tests/unit/test_movement_rules.py`:
    - cada tipo con sus cuentas y categoría válidas pasa, y cada variante inválida falla con el campo correcto;
    - una transferencia de una cuenta a sí misma falla;
    - la categoría debe ser de la clase correcta;
    - el diff detecta los campos cambiados y no cuenta un cambio de comercio que solo difiere en mayúsculas.
  - **Hecho cuando:** el test pasa.
  - **En simple:** las reglas de cómo debe ser cada tipo de movimiento y cómo saber qué cambió al corregir.
  - **Commit:** `feat(001): T19 reglas por tipo y diff de versiones`

- [x] **T20 · Saldo puro, agrupación y advertencias (`domain/balances.py`)**
  - **Cubre:** RF-14, RF-15, RF-16 · Plan §3.1, §3.2, §3.4
  - **Depende de:** T19
  - **Tests primero:** `tests/unit/test_balances.py` y `tests/unit/test_warnings.py`:
    - con los datos de plan §2.4 se obtienen exactamente Lulo `279300000`, Ahorro `351234567`, subtotal `630534567`, Nequi `17150000`, Efectivo `25000000` y total `672684567`;
    - los anulados no cuentan;
    - las archivadas con saldo 0 se ocultan;
    - un saldo negativo produce `negative_balance`;
    - una cuenta archivada con saldo distinto de 0 produce `archived_nonzero_balance`.
  - **Hecho cuando:** los dos tests pasan.
  - **En simple:** la fórmula del saldo (lo inicial, más lo que entra, menos lo que sale) y los avisos cuando algo queda en negativo.
  - **Commit:** `feat(001): T20 saldo derivado y advertencias`

- [x] **T21 · Cálculo del ajuste (`domain/adjustments.py`)**
  - **Cubre:** RF-12 · CL-14, CL-16 · Plan §3.3
  - **Depende de:** T16
  - **Tests primero:** `tests/unit/test_adjustments.py`:
    - si el saldo real es igual al actual, no hay ajuste;
    - si el real es mayor, el ajuste es `in` por la diferencia;
    - si el real es menor, el ajuste es `out`;
    - con real `-500000` y actual `0`, el ajuste es `out` por `500000`.
  - **Hecho cuando:** el test pasa.
  - **En simple:** cuánto y en qué dirección hay que corregir una cuenta para que coincida con lo que dice el banco.
  - **Commit:** `feat(001): T21 cálculo del ajuste`

### 3b. Servicios (con base de datos)

- [x] **T22 · Usuario inicial y categorías precargadas**
  - **Cubre:** RF-3 · Plan §5.4
  - **Depende de:** T15
  - **Tests primero:** `tests/integration/test_bootstrap_service.py`:
    - con la BD vacía, `ensure_initial_user()` crea 1 usuario con 12 categorías de gasto y 4 de ingreso;
    - llamarla otra vez no duplica nada;
    - `get_owner_id()` devuelve ese usuario.
  - **Hecho cuando:** el test pasa y la app ejecuta la siembra al arrancar.
  - **En simple:** la primera vez que arranca, la app te crea como usuario y te deja las categorías básicas listas.
  - **Commit:** `feat(001): T22 usuario inicial y categorías precargadas`

- [x] **T23 · Crear y consultar cuentas**
  - **Cubre:** RF-4 · CL-10, CL-13, CL-33, CL-34 · Plan §2.2, §3.5
  - **Depende de:** T18, T22
  - **Tests primero:** `tests/integration/test_accounts_service.py`:
    - crear las 4 cuentas de §2.4;
    - se aceptan saldos iniciales `0` y `-500000`;
    - se rechazan: una fecha de inicio futura, «nequi» si ya existe «Nequi» (409), un bolsillo cuyo padre es bolsillo, un padre archivado y un padre de otro usuario (404);
    - el listado solo devuelve las cuentas del dueño.
  - **Hecho cuando:** el test pasa.
  - **En simple:** ya se pueden dar de alta Lulo, sus bolsillos, Nequi y el efectivo.
  - **Commit:** `feat(001): T23 crear y consultar cuentas`

- [x] **T24 · Consulta SQL de saldos**
  - **Cubre:** RF-15 · Plan §3.1, DT-1
  - **Depende de:** T20, T23
  - **Tests primero:** `tests/integration/test_balance_property.py`. En 200 escenarios aleatorios con semilla fija, el saldo SQL coincide con el saldo puro de T20, y no incluye movimientos de otro dueño.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la base de datos calcula todos los saldos de una vez, y se comprueba que da lo mismo que la fórmula «a mano».
  - **Commit:** `feat(001): T24 consulta agregada de saldos`

- [x] **T25 · Renombrar y editar saldo y fecha inicial**
  - **Cubre:** RF-5 · Plan §4.2
  - **Depende de:** T23
  - **Tests primero:** `tests/integration/test_accounts_service.py`:
    - renombrar respeta el nombre único;
    - el saldo inicial y la fecha de inicio se editan sin movimientos y se rechazan (409) con movimientos;
    - el tipo y el padre no se pueden cambiar.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** se puede cambiar el nombre de una cuenta, y corregir su saldo inicial solo si aún no se usó.
  - **Commit:** `feat(001): T25 editar cuentas`

- [x] **T26 · Archivar y desarchivar cuentas**
  - **Cubre:** RF-5 · CL-28, CL-29, CL-30 · Plan §4.2
  - **Depende de:** T24, T25
  - **Tests primero:** `tests/integration/test_accounts_service.py`:
    - archivar con saldo distinto de 0 → 409;
    - archivar Lulo con bolsillos activos → 409, nombrando los bolsillos;
    - desarchivar un bolsillo con Lulo archivado → 409;
    - archivar con saldo 0 funciona y desarchivar lo revierte.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** se pueden «guardar en el cajón» las cuentas que ya no usas, siempre que estén en cero.
  - **Commit:** `feat(001): T26 archivar y desarchivar cuentas`

- [x] **T27 · Borrar cuenta (regla «nunca usada»)**
  - **Cubre:** RF-5 · Plan §3.8
  - **Depende de:** T25
  - **Tests primero:** `tests/integration/test_accounts_service.py`:
    - se borra una cuenta sin uso;
    - se rechaza borrar (409) una cuenta usada por un movimiento vigente, por uno anulado, solo por una versión anterior, o que es padre de un bolsillo.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** solo se puede borrar una cuenta creada por error que nunca se usó. Lo demás se conserva para el historial.
  - **Commit:** `feat(001): T27 borrar cuentas nunca usadas`

- [x] **T28 · Categorías: crear, listar y renombrar**
  - **Cubre:** RF-6 · Plan §2.2
  - **Depende de:** T22, T17
  - **Tests primero:** `tests/integration/test_categories_service.py`:
    - crear funciona;
    - un duplicado en la misma clase → 409;
    - el mismo nombre en otra clase se acepta;
    - renombrar a un nombre existente → 409;
    - la clase no se puede cambiar;
    - el listado se filtra por clase.
  - **Hecho cuando:** el test pasa.
  - **En simple:** manejar tus categorías («Domicilios», «Salario»…).
  - **Commit:** `feat(001): T28 crear y renombrar categorías`

- [x] **T29 · Categorías: archivar, desarchivar y borrar**
  - **Cubre:** RF-6 · CL-31, CL-32 · Plan §3.8
  - **Depende de:** T28
  - **Tests primero:** `tests/integration/test_categories_service.py`:
    - archivar y desarchivar funcionan;
    - se borra una categoría precargada sin uso;
    - borrar una categoría usada solo por un movimiento anulado → 409.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** guardar o borrar categorías sin romper el historial.
  - **Commit:** `feat(001): T29 archivar y borrar categorías`

- [x] **T30 · Crear gasto e ingreso**
  - **Cubre:** RF-2, RF-7, RF-8, RF-9 · CL-6, CL-8, CL-9 · Plan §3.5
  - **Depende de:** T19, T23, T28
  - **Tests primero:** `tests/integration/test_movements_service.py`:
    - se crea un gasto y un ingreso, cada uno con su versión 1 y el `created_at` del reloj;
    - sin fecha se usa la de hoy;
    - se rechazan: una fecha de mañana, una anterior al inicio (y se acepta la del día de inicio), una cuenta archivada, una categoría archivada o de la clase incorrecta, y un `type=adjustment`.
  - **Hecho cuando:** el test pasa.
  - **En simple:** ya se pueden registrar gastos e ingresos.
  - **Commit:** `feat(001): T30 registrar gastos e ingresos`

- [x] **T31 · Crear transferencia y rendimiento**
  - **Cubre:** RF-10, RF-11 · CL-3, CL-4, CL-5, CL-12 · Plan §3.5
  - **Depende de:** T30, T24
  - **Tests primero:** `tests/integration/test_movements_service.py`:
    - CL-3: un retiro de cajero de `20000000` a Efectivo más un gasto de `700000` hace que el origen baje `20700000` y Efectivo suba `20000000`;
    - CL-4: una transferencia entre bolsillos no cambia el subtotal;
    - CL-5: una transferencia a la misma cuenta se rechaza;
    - CL-12: un rendimiento de `123456` se suma exacto;
    - una categoría en una transferencia o un rendimiento se rechaza.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** mover plata entre tus cuentas (sin que cuente como gasto) y registrar lo que te paga el ahorro.
  - **Commit:** `feat(001): T31 transferencias y rendimientos`

- [x] **T32 · Advertencias al crear**
  - **Cubre:** RF-14 · CL-1, CL-2 · Plan §3.4
  - **Depende de:** T31
  - **Tests primero:** `tests/integration/test_movements_service.py`:
    - un gasto que deja la cuenta en negativo se guarda y devuelve `negative_balance` con su saldo;
    - CL-2: un gasto antes del ingreso del mismo día produce una advertencia, y al registrar el ingreso ya no la hay;
    - una transferencia revisa las dos cuentas.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** la app te avisa (sin impedirte nada) cuando una cuenta queda en rojo.
  - **Commit:** `feat(001): T32 advertencias de saldo negativo`

- [x] **T33 · Servicio de ajuste**
  - **Cubre:** RF-12, RF-14 · CL-14, CL-15, CL-16 · Plan §3.3
  - **Depende de:** T21, T32
  - **Tests primero:** `tests/integration/test_adjustments_service.py`:
    - CL-14: si ya cuadra, devuelve `already_balanced` y no crea filas;
    - CL-15: un ajuste de Lulo ignora sus bolsillos;
    - CL-16: un saldo real negativo crea un ajuste `out` con advertencia;
    - dos ajustes el mismo día: el segundo parte del primero;
    - la fecha siempre es la de hoy;
    - una cuenta archivada → 409.
  - **Hecho cuando:** el test pasa.
  - **En simple:** le dices a la app «en el banco veo X» y ella crea el movimiento que cuadra la cuenta.
  - **Commit:** `feat(001): T33 ajustes de saldo`

- [ ] **T34 · Corrección básica con versión**
  - **Cubre:** RF-14, RF-19, RF-20 · CL-19, CL-24 · Plan §3.6
  - **Depende de:** T32
  - **Tests primero:** `tests/integration/test_corrections_service.py`:
    - corregir el monto crea la versión 2 con `changed_fields=["amount_cents"]` sin cambiar `created_at`;
    - CL-19: cambiar la cuenta recalcula ambos saldos y advierte si alguno queda negativo;
    - CL-24: cambiar «rappi» por «RAPPI» devuelve `changed=false` y no crea versión.
  - **Hecho cuando:** el test pasa.
  - **En simple:** arreglar un movimiento guardando cómo era antes.
  - **Commit:** `feat(001): T34 corregir movimientos con historial`

- [ ] **T35 · Corrección: rechazos y cuentas o categorías archivadas**
  - **Cubre:** RF-19 · CL-18, CL-20, CL-21, CL-22, CL-23, CL-25 (corregir) · Plan §3.6
  - **Depende de:** T34, T33
  - **Tests primero:** `tests/integration/test_corrections_service.py`:
    - CL-18: corregir un ajuste → 409;
    - CL-20: corregir una transferencia para que el origen sea igual al destino → 422;
    - CL-21: cambiar el tipo → 422;
    - CL-22: corregir la nota con la categoría archivada se permite;
    - CL-23: elegir una categoría archivada → 409;
    - CL-25: corregir un anulado → 409.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** qué no se puede corregir, y por qué los datos viejos se pueden arreglar aunque su cuenta esté guardada.
  - **Commit:** `feat(001): T35 reglas de corrección`

- [ ] **T36 · Corrección concurrente**
  - **Cubre:** RF-19 · Plan §3.6, DT-6, riesgo R-4
  - **Depende de:** T35
  - **Tests primero:** `tests/integration/test_corrections_concurrency.py`. Dos sesiones corrigen el mismo movimiento; la segunda espera el bloqueo de la primera. Al final hay 3 versiones, gana la última y no se usan `sleep` arbitrarios.
  - **Hecho cuando:** el test pasa 20 veces seguidas (`pytest --count` o un bucle).
  - **En simple:** si corriges lo mismo desde la web y desde WhatsApp a la vez, no se pierde ninguno de los dos cambios.
  - **Commit:** `feat(001): T36 correcciones simultáneas`

- [ ] **T37 · Anular**
  - **Cubre:** RF-14, RF-21 · CL-25 (anular), CL-26, CL-27 · Plan §3.7
  - **Depende de:** T32
  - **Tests primero:** `tests/integration/test_void_service.py`:
    - anular guarda el momento y el motivo, y el movimiento deja de contar en el saldo;
    - anular dos veces → 409;
    - CL-26: anular un ingreso que deja la cuenta en negativo advierte;
    - CL-27: anular en una cuenta archivada se permite y advierte `archived_nonzero_balance`;
    - anular un ajuste se permite.
  - **Hecho cuando:** el test pasa.
  - **En simple:** «tachar» un movimiento: deja de contar, pero sigue visible.
  - **Commit:** `feat(001): T37 anular movimientos`

- [ ] **T38 · Historial**
  - **Cubre:** RF-20, RNF-2 · Plan §3.6
  - **Depende de:** T34, T37
  - **Tests primero:** `tests/integration/test_history_service.py`:
    - las versiones salen en orden con su `changed_fields`;
    - al final aparece la anulación con su motivo;
    - un renombre de categoría se refleja en las versiones viejas;
    - ninguna operación borra versiones.
  - **Hecho cuando:** el test pasa.
  - **En simple:** ver todo lo que le pasó a un movimiento desde que se creó.
  - **Commit:** `feat(001): T38 historial de movimientos`

- [ ] **T39 · Listado: filtros, orden y paginación**
  - **Cubre:** RF-17 · CL-35, CL-36, CL-37 · Plan §5.1
  - **Depende de:** T31, T37
  - **Tests primero:** `tests/integration/test_list_service.py`:
    - el orden es fecha, momento de registro e id, todos descendentes;
    - CL-35: filtrar por Nequi incluye las transferencias donde es origen o destino;
    - CL-36: filtrar por Lulo excluye sus bolsillos;
    - CL-37: el rango 1–31 incluye los extremos;
    - filtrar por categoría excluye los tipos sin categoría;
    - los anulados se excluyen salvo que se pidan;
    - `limit` y `offset` funcionan;
    - un rango invertido → 422;
    - una cuenta inexistente o de otro usuario → 404.
  - **Hecho cuando:** el test pasa.
  - **En simple:** buscar tus movimientos por fechas, cuenta, categoría o tipo, página por página.
  - **Commit:** `feat(001): T39 listar y filtrar movimientos`

- [ ] **T40 · Listado: totales**
  - **Cubre:** RF-17 · CL-38 · Plan §5.1, §2.4
  - **Depende de:** T39
  - **Tests primero:** `tests/integration/test_list_service.py`:
    - CL-38: con un ingreso de 100, un rendimiento de 10, un gasto de 30, una transferencia de 50 y un ajuste de 5, se obtienen ingresos 110 (rendimientos 10), gastos 30 y neto 80;
    - los totales cubren todo el filtro, no solo la página;
    - los anulados nunca suman.
  - **Hecho cuando:** los tests nuevos pasan.
  - **En simple:** cuánto entró, cuánto salió y cuánto te quedó en el periodo que buscaste.
  - **Commit:** `feat(001): T40 totales del listado`

- [ ] **T41 · Lista de comercios**
  - **Cubre:** RF-13 · Plan §5.3
  - **Depende de:** T30
  - **Tests primero:** `tests/integration/test_merchants_service.py`:
    - se agrupa por clave y se ordena por usos y luego por el uso más reciente;
    - se muestra la forma más reciente de cada comercio;
    - los anulados no cuentan;
    - nunca aparecen comercios de otro usuario.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la lista de tus comercios frecuentes, para autocompletar más adelante.
  - **Commit:** `feat(001): T41 lista de comercios usados`

- [ ] **T42 · Servicio de saldos agrupados**
  - **Cubre:** RF-15, RF-16 · CL-4 · Plan §3.2
  - **Depende de:** T24, T26
  - **Tests primero:** `tests/integration/test_balances_service.py`:
    - con los datos de §2.4 se obtienen exactamente los saldos, el grupo «Lulo» con `630534567` y el total `672684567`;
    - una archivada con saldo 0 no aparece;
    - una archivada con saldo distinto de 0 aparece marcada.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la foto de cuánto tienes en cada cuenta, en Lulo con sus bolsillos y en total.
  - **Commit:** `feat(001): T42 saldos agrupados y total`

---

## Fase 4 — API

- [ ] **T43 · API de cuentas**
  - **Cubre:** RF-4, RF-5 · Plan §4.2, §4.3
  - **Depende de:** T10, T27, T26
  - **Tests primero:** `tests/integration/test_accounts_api.py`. Los 7 endpoints de cuentas devuelven 201, 200 o 204 según el caso, y 404, 409 o 422 en errores, con el formato estándar y el JSON de ejemplo del plan.
  - **Hecho cuando:** el test pasa y en `/docs` se puede crear una cuenta.
  - **En simple:** la «ventanilla» por la que la web y WhatsApp pedirán crear y manejar cuentas.
  - **Commit:** `feat(001): T43 endpoints de cuentas`

- [ ] **T44 · API de categorías**
  - **Cubre:** RF-6 · Plan §4.2
  - **Depende de:** T10, T29
  - **Tests primero:** `tests/integration/test_categories_api.py`. Se prueban los endpoints de categorías con sus códigos y el filtro `?kind=`.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la ventanilla de las categorías.
  - **Commit:** `feat(001): T44 endpoints de categorías`

- [ ] **T45 · API para crear y ver movimientos**
  - **Cubre:** RF-1, RF-18 · CL-7, CL-11 · Plan §4.1, §4.3
  - **Depende de:** T10, T32
  - **Tests primero:** `tests/integration/test_movements_api.py`:
    - `POST /movements` devuelve `201` con `movement` y `warnings`;
    - CL-7: la fecha `2026-02-31` → 422;
    - CL-11: los montos `0`, `-500000`, `2500.5` y `"25.000"` → 422;
    - `GET /movements/{id}` devuelve todos los datos y el estado.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la ventanilla para registrar un movimiento y verlo.
  - **Commit:** `feat(001): T45 endpoints crear y ver movimiento`

- [ ] **T46 · API para listar movimientos**
  - **Cubre:** RF-17 · Plan §4.3, §5.1
  - **Depende de:** T45, T40
  - **Tests primero:** `tests/integration/test_list_api.py`:
    - los parámetros repetidos (`type=expense&type=income`) funcionan;
    - un `limit` fuera de 1–200 → 422;
    - la respuesta trae `items`, `totals` y `page`.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la ventanilla para buscar movimientos.
  - **Commit:** `feat(001): T46 endpoint de listado`

- [ ] **T47 · API para corregir, anular e historial**
  - **Cubre:** RF-19, RF-20, RF-21 · Plan §4.3
  - **Depende de:** T45, T36, T38
  - **Tests primero:** `tests/integration/test_corrections_api.py`:
    - `PATCH` devuelve `changed` y la versión;
    - `POST /void` devuelve `voided: true`;
    - `GET /history` tiene el formato del plan;
    - los conflictos devuelven 409.
  - **Hecho cuando:** el test pasa.
  - **En simple:** las ventanillas para arreglar, tachar y ver el historial.
  - **Commit:** `feat(001): T47 endpoints de corrección, anulación e historial`

- [ ] **T48 · API de ajuste**
  - **Cubre:** RF-12 · CL-17 · Plan §4.3
  - **Depende de:** T45, T33
  - **Tests primero:** `tests/integration/test_adjustments_api.py`:
    - devuelve `201 adjusted` o `200 already_balanced`;
    - CL-17: enviar un campo `date` → 422, porque el ajuste solo es de hoy.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la ventanilla para cuadrar una cuenta con el banco.
  - **Commit:** `feat(001): T48 endpoint de ajuste`

- [ ] **T49 · API de saldos y comercios**
  - **Cubre:** RF-13, RF-16 · Plan §4.3
  - **Depende de:** T42, T41, T10
  - **Tests primero:** `tests/integration/test_balances_api.py`. `GET /balances` devuelve exactamente el JSON de ejemplo del plan con los datos de §2.4, y `GET /merchants` respeta `limit`.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la ventanilla para preguntar «¿cuánto tengo?».
  - **Commit:** `feat(001): T49 endpoints de saldos y comercios`

- [ ] **T50 · Documentación OpenAPI completa**
  - **Cubre:** RNF-9 · Plan §4.2
  - **Depende de:** T43 a T49
  - **Tests primero:** `tests/integration/test_docs_api.py`. Con `APP_ENV=local`, `/openapi.json` lista los 23 endpoints de §4.2, cada uno con descripción en español y su esquema de error.
  - **Hecho cuando:** el test pasa y la revisión manual de `/docs` muestra los ejemplos.
  - **En simple:** el «manual de instrucciones» de la API, completo y navegable en tu computador.
  - **Commit:** `docs(001): T50 documentación de la api`

---

## Fase 5 — Aislamiento, validación y cierre

- [ ] **T51 · Aislamiento entre usuarios en cada operación**
  - **Cubre:** RNF-5, RF-22 · CL-39 · Plan §8.3
  - **Depende de:** T50
  - **Tests primero:** `tests/integration/test_isolation.py`, parametrizado. `owner_b` intenta, sobre los datos de `owner_a`:
    - leer, listar, corregir, anular y ajustar;
    - usar una cuenta o categoría ajena como `from`, `to` o categoría;
    - ver el historial y pedir saldos y comercios.

    Se espera un `404` con cuerpo idéntico al de un id inexistente, y que los listados y saldos queden vacíos de datos ajenos. Si algo falla, se corrige el servicio en esta misma tarea.
  - **Hecho cuando:** el test pasa.
  - **En simple:** la prueba de que nadie puede ver ni tocar las finanzas de otra persona.
  - **Commit:** `test(001): T51 aislamiento entre usuarios`

- [ ] **T52 · Sin cambios parciales y todo en español**
  - **Cubre:** RF-22, RNF-7 · Plan §4.4
  - **Depende de:** T50
  - **Tests primero:** `tests/integration/test_errors_api.py`:
    - forzar un fallo después de insertar el movimiento y antes de la versión no deja ninguna fila;
    - recorrer todos los errores y advertencias posibles confirma que cada mensaje sale del catálogo en español.
  - **Hecho cuando:** el test pasa.
  - **En simple:** si algo falla, no queda nada a medias; y todo lo que la app dice, lo dice en español.
  - **Commit:** `test(001): T52 atomicidad e idioma de errores`

- [ ] **T53 · Escenario del mes sintético**
  - **Cubre:** RNF-1, criterio de finalización 3 · Plan §2.4, §8.1
  - **Depende de:** T50
  - **Tests primero:** `tests/scenarios/test_month.py`. Por la API se crean las cuentas y los movimientos M1–M8 de §2.4, se corrige M2 y se anula M6. Los saldos, el subtotal, el total y los totales del listado se comparan con los valores fijos del plan.
  - **Hecho cuando:** el test pasa.
  - **En simple:** se simula un mes completo y se comprueba que los números dan exactamente lo calculado a mano.
  - **Commit:** `test(001): T53 escenario de un mes`

- [ ] **T54 · Rendimiento (p95 < 300 ms)**
  - **Cubre:** RNF-3 · Plan §5.7, riesgo R-6
  - **Depende de:** T50
  - **Tests primero:** `tests/perf/test_rnf3.py`, marcado `perf`. Con 10.000 movimientos sintéticos, se mide el p95 de 100 registros y de 100 consultas de saldos.
  - **Hecho cuando:** `uv run pytest -m perf` pasa en local y el resultado se anota en esta tarea.
  - **En simple:** comprobar que la app responde rápido aunque tengas miles de movimientos.
  - **Commit:** `test(001): T54 prueba de rendimiento`

- [ ] **T55 · Dockerfile y servicio `api` en Compose**
  - **Cubre:** Plan §6.1, §6.4, §6.5
  - **Depende de:** T50
  - **Tests primero:** no aplica a pytest. La comprobación es un smoke test manual: tras `docker compose up --build`, `curl localhost:8000/api/v1/health` responde `200`.
  - **Hecho cuando:**
    - `docker compose up --build` levanta `db` y `api`;
    - las migraciones corren solas;
    - `/health` responde `200` y `/docs` se abre con `APP_ENV=local`.
  - **En simple:** toda la app arranca con un solo comando, sin instalar nada más.
  - **Commit:** `chore(001): T55 dockerfile y servicio api`

- [ ] **T56 · Revisión final y cierre de la spec**
  - **Cubre:** RNF-6, RNF-8, RNF-9, criterios de finalización 1, 2, 6, 7 y 8 · Plan §8.4, §9
  - **Depende de:** T51 a T55
  - **Tests primero:** `tests/test_traceability.py` verifica que existe una función `test_cl_<n>_` para cada n de 1 a 39.
  - **Hecho cuando:**
    - `uv run pytest --cov=finanzas --cov-branch --cov-fail-under=90` pasa;
    - ruff queda limpio y la CI está en verde;
    - `git ls-files` no muestra `.env`, bases de datos ni datos reales;
    - `/docs` se revisó a mano;
    - se propone cambiar el estado de la spec a «Implementada».
  - **En simple:** el chequeo final antes de dar por terminado el motor de la app.
  - **Commit:** `chore(001): T56 cierre de la spec 001`

---

## Verificación de cobertura

Cada requisito y caso límite de la trazabilidad del plan (§9) aparece en
al menos una tarea.

| Requisito | Tareas |
|-----------|--------|
| RF-1 | T16, T45 |
| RF-2 | T4, T18, T30 |
| RF-3 | T22 |
| RF-4 | T11, T23, T43 |
| RF-5 | T25, T26, T27, T43 |
| RF-6 | T12, T28, T29, T44 |
| RF-7 | T13, T19, T30 |
| RF-8 | T19, T30 |
| RF-9 | T19, T30 |
| RF-10 | T19, T31 |
| RF-11 | T19, T31 |
| RF-12 | T21, T33, T48 |
| RF-13 | T17, T41, T49 |
| RF-14 | T20, T32, T33, T34, T37 |
| RF-15 | T20, T24, T42 |
| RF-16 | T20, T42, T49 |
| RF-17 | T39, T40, T46 |
| RF-18 | T45 |
| RF-19 | T19, T34, T35, T36, T47 |
| RF-20 | T14, T34, T38, T47 |
| RF-21 | T37, T47 |
| RF-22 | T9, T10, T51, T52 |
| RNF-1 | T53 |
| RNF-2 | T14, T38 |
| RNF-3 | T54 |
| RNF-4 | T3, T7, T8 |
| RNF-5 | T11, T12, T13, T14, T15, T51 |
| RNF-6 | T2, T15, T56 |
| RNF-7 | T9, T10, T52 |
| RNF-8 | T4, T6, T56 |
| RNF-9 | T7, T50, T56 |

| Casos límite | Tareas |
|--------------|--------|
| CL-1, CL-2 | T32 |
| CL-3 | T31 |
| CL-4 | T31, T42 |
| CL-5 | T19, T31 |
| CL-6, CL-8, CL-9 | T18, T30 |
| CL-7 | T45 |
| CL-10 | T18, T23 |
| CL-11 | T16, T45 |
| CL-12 | T16, T31 |
| CL-13 | T16, T23 |
| CL-14, CL-16 | T21, T33 |
| CL-15 | T33 |
| CL-17 | T48 |
| CL-18, CL-20, CL-21, CL-22, CL-23 | T35 |
| CL-19 | T34 |
| CL-24 | T17, T34 |
| CL-25 | T35, T37 |
| CL-26, CL-27 | T37 |
| CL-28, CL-29, CL-30 | T26 |
| CL-31, CL-32 | T29 |
| CL-33 | T11, T23 |
| CL-34 | T23 |
| CL-35, CL-36, CL-37 | T39 |
| CL-38 | T40 |
| CL-39 | T51 |

**Requisitos sin tarea:** ninguno. Los 22 RF, los 9 RNF y los 39 casos
límite están cubiertos. Los criterios de finalización de la spec (§8)
quedan cubiertos por T6 (CI), T51 (aislamiento), T53 (mes sintético),
T54 (rendimiento) y T56 (cobertura, revisión y cierre).
