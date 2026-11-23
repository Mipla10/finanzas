# Constitución — finanzas

Principios no negociables del proyecto. Toda spec, plan y línea de código
debe respetarlos. Cambiar un principio requiere editar este documento
primero, con su razón.

## 1. Registrar un gasto toma segundos
El flujo de registro rápido (web y WhatsApp) es la funcionalidad más
importante: máximo 3 toques o un mensaje, con valores por defecto
inteligentes (última cuenta usada, fecha de hoy). Toda decisión de UX se
evalúa contra este flujo. La web es mobile-first y se instala como PWA.
**Razón:** el proyecto existe porque editar el Excel era tan engorroso que
dejaba de registrar gastos. Si registrar no es más rápido que no
registrar, la app fracasa aunque todo lo demás funcione.

## 2. El dinero es exacto: enteros en centavos
Todo monto se guarda como entero en centavos de COP (`BIGINT` en BD, `int`
en Python, nunca `float`). Los montos son siempre positivos y el tipo de
movimiento define el signo. El formateo a pesos ocurre solo en la capa de
presentación.
**Razón:** los flotantes acumulan errores de redondeo y los intereses y
algunas compras traen centavos. Un saldo que no cuadra por un peso
destruye la confianza en toda la app.

## 3. Los movimientos son la única fuente de verdad
El saldo de cada cuenta se calcula como saldo inicial + movimientos; nunca
se guarda un saldo editable. Hay cinco tipos: gasto, ingreso,
transferencia (un solo movimiento con cuenta origen y destino; no cuenta
como gasto ni como ingreso), rendimiento (ingreso) y ajuste (cuadra el
saldo con el valor real del banco; no cuenta como gasto ni como
ingreso). Los bolsillos de Lulo
son cuentas con cuenta padre. Los movimientos se corrigen o se anulan con
rastro; nunca se borran en silencio.
**Razón:** un saldo derivado no puede descuadrarse y deja la historia
auditable, que es justo lo que necesitan la conciliación (007), los
reportes (003) y el ML (008).

## 4. Multiusuario y privacidad por diseño
Toda entidad (cuentas, movimientos, categorías, comercios, versiones)
tiene un dueño, y ningún usuario puede ver ni modificar datos de otro:
toda lectura y escritura se filtra por usuario. El registro de usuarios
llega en una spec posterior (004). Hasta entonces existe un único
usuario, pero el modelo de datos ya es multiusuario y ninguna versión
desplegada queda abierta sin protección. El repositorio es público, pero
los datos reales nunca entran a git: nada de extractos, exportes del
Excel, bases de datos ni `.env`. Los fixtures y demos usan datos
sintéticos. En WhatsApp, cada número de teléfono se asocia a un usuario;
el webhook verifica la firma de Meta e ignora los números no
registrados. Al LLM se envía solo el mensaje a interpretar y el contexto
mínimo de ese usuario (nombres de sus cuentas y categorías), nunca su
historial.
**Razón:** la app se compartirá con conocidos. Añadir el dueño después
obligaría a migrar cada tabla y revisar cada consulta, y una fuga entre
usuarios expondría las finanzas de otra persona. Son datos reales y el
código es portafolio público: un dato filtrado no tiene vuelta atrás.

## 5. Tests primero, sobre todo donde hay dinero
Cada comportamiento nuevo empieza con un test que falla (TDD). El dominio
(saldos, transferencias, validaciones) se prueba con tests unitarios puros
y la API con tests de integración contra PostgreSQL. La cobertura del
backend debe ser ≥ 90 %. El flujo de registro rápido tiene al menos un
test E2E. CI corre lint y tests en cada push.
**Razón:** un bug de dinero es silencioso: la app sigue funcionando y
mostrando números equivocados. Los tests son la única red de seguridad, y
además demuestran rigor en un portafolio de ciencia de datos.

## 6. Spec primero, una versión funcional a la vez
Nada se implementa sin una spec aprobada en `specs/`. Cada spec del
roadmap (001–008) entrega una versión usable de punta a punta antes de
empezar la siguiente. Si el código necesita algo que la spec no dice, se
actualiza primero la spec.
**Razón:** SDD evita construir de más y deja documentado el porqué de cada
decisión. Las versiones incrementales me dan una app útil desde la 002, no
al final.

## 7. Costo mínimo y portabilidad
Se priorizan planes gratuitos (Vercel, Neon, Render) y se acepta pagar
(~5 USD/mes, Railway) solo cuando hace falta un servidor siempre encendido
para WhatsApp. El backend corre en Docker y se configura con variables de
entorno, así que puede cambiar de proveedor sin tocar código. Las
dependencias externas (LLM, WhatsApp) quedan detrás de interfaces
intercambiables.
**Razón:** es un proyecto personal de estudiante. Si un plan gratuito
desaparece o el LLM cambia de precio, debo poder migrar en una tarde.

## 8. Núcleo de datos limpio y separado
La lógica de dominio (Python puro, sin FastAPI ni SQLAlchemy) se separa
de la API y de la persistencia. El esquema se versiona con migraciones de
Alembic y se mantiene consultable con SQL estándar.
**Razón:** el valor de portafolio está en el análisis (reportes, ML). Un
dominio puro es fácil de probar y un esquema limpio hace que el análisis
con pandas o SQL sea directo.
