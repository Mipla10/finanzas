# Spec 001 — Núcleo

- **Estado:** Borrador v2, simplificada para el MVP (pendiente de aprobación)
- **Fecha:** 2026-11-23
- **Roadmap:** primera versión funcional (001 de 008)

## 1. Contexto y objetivo

### Contexto
Hoy llevo mis finanzas en una plantilla de Excel. Funciona, pero editar
las hojas es tan engorroso que termino sin registrar gastos, y entonces
los saldos dejan de reflejar la realidad. La app completa (web, WhatsApp,
reportes, importación, conciliación, ML) va a depender de un mismo
núcleo: cuentas, movimientos, categorías y saldos.

### Objetivo
Construir ese núcleo **sin interfaz gráfica ni WhatsApp**. Se accede por
una interfaz programática y debe ser correcto, exacto y auditable. Al
terminar esta spec debo poder:

1. Dar de alta mis cuentas reales (Lulo Bank y sus bolsillos, Nequi y
   efectivo) con su saldo inicial.
2. Registrar gastos, ingresos, transferencias, rendimientos y ajustes.
3. Saber en todo momento cuánto dinero tengo en cada cuenta y en total.
4. Consultar y filtrar mi historial.
5. Corregir o anular errores sin perder el rastro de lo que cambió.

### Por qué primero y por qué tan pequeño
Todas las specs siguientes (002–008) leen y escriben sobre este núcleo.
Un saldo mal calculado o una transferencia contada como gasto se
propagaría a todo lo demás. Por eso esta versión prioriza la exactitud y
la trazabilidad, y deja fuera todo lo que no sea imprescindible para
registrar y consultar (ver sección 7).

## 2. Usuarios

| Usuario | Descripción |
|---------|-------------|
| **Yo (propietario)** | Único usuario en esta versión. Estudiante en Colombia que maneja pesos colombianos (COP) en Lulo Bank, Nequi y efectivo. |
| **Conocidos (futuros)** | Personas con las que compartiré la app cuando exista el registro de usuarios (spec 004). Cada uno tendrá sus propias cuentas, categorías y movimientos. |
| **Clientes del núcleo (futuros)** | La app web (002), el agente de WhatsApp (005) y el importador (006). Consumen las mismas capacidades y necesitan errores claros y predecibles. |

La app es **multiusuario por diseño**: toda cuenta, categoría, movimiento
y versión pertenece a un usuario, y ningún usuario puede ver ni modificar
datos de otro. Hasta la spec 004 existe un único usuario, creado al
iniciar el sistema por primera vez, y todo le pertenece.

## 3. Historias de usuario

- **HU-1:** Como propietario, quiero crear mis cuentas con su saldo
  inicial para que el sistema parta de mi dinero real.
- **HU-2:** Como propietario, quiero que los bolsillos de Lulo se agrupen
  bajo Lulo para ver el saldo de cada bolsillo y el de Lulo en conjunto.
- **HU-3:** Como propietario, quiero empezar con categorías básicas que
  pueda editar, para registrar desde el primer día sin configurar nada.
- **HU-4:** Como propietario, quiero registrar un gasto o un ingreso con
  monto, fecha, cuenta, categoría, comercio y nota para que mi historial
  sea completo.
- **HU-5:** Como propietario, quiero registrar transferencias entre mis
  cuentas (incluidos los retiros de cajero y los movimientos entre
  bolsillos) sin que cuenten como gasto ni como ingreso, para que mis
  totales no se inflen.
- **HU-6:** Como propietario, quiero registrar los rendimientos de mis
  cuentas como ingreso para saber cuánto me genera el ahorro.
- **HU-7:** Como propietario, quiero ajustar hoy el saldo de una cuenta al
  valor real que veo en el banco, dejando constancia del ajuste, para
  corregir descuadres sin buscar el error movimiento por movimiento.
- **HU-8:** Como propietario, quiero consultar el saldo actual de cada
  cuenta y el total para saber cuánto dinero tengo.
- **HU-9:** Como propietario, quiero listar mis movimientos filtrando por
  fechas, cuenta, categoría y tipo, y ver sus totales, para revisar en qué
  se va mi dinero.
- **HU-10:** Como propietario, quiero corregir o anular un movimiento y
  ver su historial de cambios para arreglar errores sin perder el rastro.
- **HU-11:** Como propietario, quiero que el sistema me advierta cuando
  una cuenta queda en negativo, sin impedirme registrar, para detectar
  errores o registros desordenados.

## 4. Requisitos funcionales

Los criterios de aceptación siguen la notación EARS:
- **Ubicuo:** «El sistema deberá…»
- **Por evento:** «Cuando…, el sistema deberá…»
- **Por estado:** «Mientras…, el sistema deberá…»
- **No deseado:** «Si…, entonces el sistema deberá…»
- **Opcional:** «Donde…, el sistema deberá…»

### 4.1 Dinero y fechas (transversal)

**RF-1. Montos en centavos**
- El sistema deberá recibir y devolver todo monto y todo saldo como un
  número entero de **centavos de COP**. Por ejemplo, $ 25.000 se expresa
  como `2500000` y $ 1.234,56 como `123456`.
- El sistema deberá aceptar los montos de movimientos solo si son enteros
  estrictamente positivos.
- Si un monto o un saldo supera en valor absoluto 9.007.199.254.740.991
  centavos (2^53 − 1, el mayor entero que un navegador representa sin
  error), entonces el sistema deberá rechazarlo. Es un límite técnico,
  no de negocio.
- Si el monto de un movimiento es cero, negativo, no entero o no
  numérico, entonces el sistema deberá rechazar la operación.
- El sistema deberá aceptar saldos (saldo inicial de una cuenta y saldo
  real de un ajuste) que sean enteros positivos, cero o negativos.
- Interpretar texto como «25.000,50» y mostrar montos en formato de pesos
  no es responsabilidad del núcleo (spec 002).

**RF-2. Fechas**
- El sistema deberá registrar cada movimiento con una fecha de
  calendario, sin hora.
- El sistema deberá calcular «hoy» según la fecha de Bogotá.
- Cuando no se indique fecha, el sistema deberá usar hoy.
- Si la fecha es posterior a hoy o no existe en el calendario (p. ej.
  31 de febrero), entonces el sistema deberá rechazar el movimiento.
- Si la fecha es anterior a la fecha de inicio de alguna cuenta
  involucrada, entonces el sistema deberá rechazar el movimiento. Una
  fecha igual a la fecha de inicio sí se acepta.
- El sistema deberá guardar el momento de registro de cada movimiento
  para ordenar los movimientos de un mismo día. Una corrección no cambia
  ese momento.

### 4.2 Usuario inicial

**RF-3. Usuario inicial y categorías precargadas**
- Cuando el sistema se inicie por primera vez, deberá crear un único
  usuario dueño de todos los datos.
- Cuando cree ese usuario, el sistema deberá precargarle estas
  categorías, que se pueden editar, archivar y borrar como cualquier
  otra:
  - **Gasto:** Alimentación, Domicilios, Transporte, Vivienda, Servicios,
    Salud, Educación, Entretenimiento, Ropa, Suscripciones, Comisiones
    bancarias, Otros.
  - **Ingreso:** Salario, Freelance, Regalos, Otros.
- El sistema deberá arrancar sin cuentas precargadas.

### 4.3 Cuentas

**RF-4. Crear cuenta**
- Cuando cree una cuenta, el sistema deberá exigir: nombre, tipo (banco,
  bolsillo, billetera digital o efectivo), saldo inicial y fecha de
  inicio (por defecto, hoy).
- El sistema deberá interpretar el saldo inicial como el saldo al
  **comenzar** el día de inicio. Los movimientos de esa misma fecha se le
  suman.
- Donde la cuenta sea de tipo bolsillo, el sistema deberá exigir una
  cuenta padre activa de tipo banco.
- Si el nombre ya existe en otra cuenta del mismo usuario (sin distinguir
  mayúsculas ni espacios sobrantes), entonces el sistema deberá rechazar
  la creación. Usuarios distintos pueden repetir nombres.
- Si la fecha de inicio es posterior a hoy, entonces el sistema deberá
  rechazar la creación.

**RF-5. Editar, archivar y borrar cuenta**
- El sistema deberá permitir renombrar una cuenta, aplicando la regla de
  nombre único de RF-4.
- El sistema no deberá permitir cambiar el tipo ni la cuenta padre.
- Donde la cuenta no tenga movimientos, el sistema deberá permitir
  editar su saldo inicial y su fecha de inicio. Si tiene movimientos,
  entonces deberá rechazarlo; el saldo se corrige con un ajuste (RF-12).
- Cuando archive una cuenta, el sistema deberá impedir crear movimientos
  nuevos en ella. Los movimientos existentes se pueden seguir corrigiendo
  y anulando.
- Si el saldo actual de la cuenta es distinto de cero, entonces el
  sistema deberá rechazar el archivado.
- Si la cuenta es un banco con bolsillos activos, entonces el sistema
  deberá rechazar el archivado indicando qué bolsillos se deben archivar
  primero.
- Cuando desarchive una cuenta, el sistema deberá volver a aceptar
  movimientos nuevos en ella. Si es un bolsillo cuyo banco está
  archivado, entonces deberá rechazar el desarchivado.
- Donde la cuenta nunca haya sido usada (ni en movimientos, anulados
  incluidos, ni en versiones anteriores, ni como padre de un bolsillo),
  el sistema deberá permitir borrarla. En cualquier otro caso deberá
  rechazar el borrado.

### 4.4 Categorías

**RF-6. Gestionar categorías**
- Cuando cree una categoría, el sistema deberá exigir nombre y clase
  (gasto o ingreso).
- Si el mismo usuario ya tiene una categoría con ese nombre en la misma
  clase (sin distinguir mayúsculas ni espacios sobrantes), entonces el
  sistema deberá rechazar la creación o el renombrado. El mismo nombre en
  clases distintas sí se permite.
- Cuando renombre una categoría, el sistema deberá mostrar el nombre
  nuevo en todos los movimientos y versiones que la usan.
- El sistema no deberá permitir cambiar la clase de una categoría.
- Cuando archive una categoría, el sistema deberá dejar de aceptarla en
  movimientos nuevos y en correcciones que la elijan, y conservarla en
  los movimientos que ya la tienen.
- El sistema deberá permitir desarchivar una categoría.
- Donde la categoría nunca haya sido usada (ni en movimientos, anulados
  incluidos, ni en versiones anteriores), el sistema deberá permitir
  borrarla. En cualquier otro caso deberá rechazar el borrado.
- Las categorías son planas: no hay subcategorías.

### 4.5 Movimientos

**RF-7. Datos comunes de un movimiento**
- El sistema deberá registrar en cada movimiento: tipo, monto, fecha,
  cuenta(s) y, opcionalmente, comercio y nota.
- El sistema deberá admitir cinco tipos: **gasto**, **ingreso**,
  **transferencia**, **rendimiento** y **ajuste**.
- Si una cuenta indicada en un movimiento nuevo está archivada, entonces
  el sistema deberá rechazarlo.
- Si se indica una categoría en una transferencia, un rendimiento o un
  ajuste, entonces el sistema deberá rechazar la operación.

**RF-8. Gasto**
- Cuando registre un gasto, el sistema deberá exigir una cuenta de origen
  y una categoría activa de clase gasto, y restar el monto del saldo de
  esa cuenta.
- Si la categoría no existe, está archivada o es de clase ingreso,
  entonces el sistema deberá rechazar el gasto.
- Una comisión bancaria se registra como un gasto normal.

**RF-9. Ingreso**
- Cuando registre un ingreso, el sistema deberá exigir una cuenta de
  destino y una categoría activa de clase ingreso, y sumar el monto al
  saldo de esa cuenta.
- Si la categoría no existe, está archivada o es de clase gasto,
  entonces el sistema deberá rechazar el ingreso.

**RF-10. Transferencia entre cuentas propias**
- Cuando registre una transferencia, el sistema deberá exigir una cuenta
  de origen y una de destino, restar el monto del origen y sumarlo al
  destino.
- El sistema deberá permitir transferencias entre cualquier par de
  cuentas activas del usuario, incluidos principal ↔ bolsillo y
  bolsillo ↔ bolsillo.
- El sistema deberá permitir registrar un retiro de cajero como una
  transferencia hacia la cuenta de efectivo.
- El sistema no deberá contar una transferencia como gasto ni como
  ingreso en ningún total.
- Si el origen y el destino son la misma cuenta, entonces el sistema
  deberá rechazar la transferencia.

**RF-11. Rendimiento**
- Cuando registre un rendimiento, el sistema deberá exigir una cuenta de
  destino y sumar el monto a su saldo.
- El sistema deberá permitir rendimientos en cualquier cuenta.
- El sistema deberá contar los rendimientos como ingreso en los totales,
  e informarlos también por separado.

**RF-12. Ajuste de saldo**
- Cuando indique el saldo real que veo hoy en una cuenta, el sistema
  deberá compararlo con el saldo actual **propio** de esa cuenta (en un
  banco, sin incluir sus bolsillos) y crear un movimiento de tipo ajuste
  con fecha de hoy.
- El sistema deberá guardar en el ajuste el monto calculado (valor
  absoluto de la diferencia) y una dirección explícita: **entrada** si
  el saldo real es mayor, **salida** si es menor.
- Si la diferencia es cero, entonces el sistema no deberá crear ningún
  movimiento e informará que la cuenta ya cuadra.
- El sistema deberá permitir varios ajustes en el mismo día. Cada uno se
  calcula sobre el saldo que ya incluye los anteriores.
- El sistema no deberá permitir ajustes con una fecha distinta de hoy.
- El sistema no deberá recalcular un ajuste cuando después cambie el
  pasado. Para volver a cuadrar se hace otro ajuste.
- El sistema no deberá permitir corregir un ajuste. Sí deberá permitir
  anularlo (RF-21).
- El sistema no deberá contar un ajuste como gasto ni como ingreso en
  ningún total, pero sí deberá mostrarlo en el listado y el historial.

**RF-13. Comercio y nota**
- El sistema deberá tratar como el mismo comercio los textos que solo se
  diferencian en espacios sobrantes o en mayúsculas y minúsculas (p. ej.
  «rappi », «RAPPI» y «Rappi»).
- El sistema deberá tratar un comercio o una nota vacíos, o con solo
  espacios, como ausentes.
- El sistema deberá ofrecer la lista de comercios que ha usado el
  usuario, y nunca los de otros usuarios.
- Si el comercio o la nota superan la longitud máxima definida en el
  plan, entonces el sistema deberá rechazar la operación.

**RF-14. Advertencias**
- Cuando cualquier operación (crear, corregir, anular o ajustar) deje en
  negativo el saldo actual de una cuenta, el sistema deberá guardar la
  operación y devolver una advertencia con la cuenta y su saldo
  resultante.
- Cuando una corrección o anulación deje una cuenta archivada con saldo
  distinto de cero, el sistema deberá guardar la operación y advertirlo.
- El sistema no deberá bloquear ninguna operación por un saldo negativo.

### 4.6 Saldos

**RF-15. Saldo por cuenta**
- El sistema deberá calcular el saldo actual de cada cuenta como:
  saldo inicial + entradas (ingresos, rendimientos, transferencias
  recibidas y ajustes de entrada) − salidas (gastos, transferencias
  enviadas y ajustes de salida), contando solo los movimientos no
  anulados.
- El sistema no deberá guardar un saldo editable. El saldo se deriva
  siempre de los movimientos.

**RF-16. Saldo agrupado y total**
- Cuando consulte los saldos, el sistema deberá devolver el saldo propio
  de cada cuenta y, por cada banco con bolsillos, un subtotal «banco +
  bolsillos».
- El sistema deberá devolver un total general que sume el saldo de cada
  cuenta una sola vez, incluidas las archivadas.
- El sistema deberá mostrar las cuentas archivadas solo si su saldo es
  distinto de cero, marcadas como archivadas.

### 4.7 Consulta de movimientos

**RF-17. Listar y filtrar**
- El sistema deberá listar los movimientos por fecha descendente y,
  dentro del mismo día, por momento de registro descendente.
- El sistema deberá permitir filtrar por rango de fechas (ambos extremos
  incluidos), una o varias cuentas, una o varias categorías y uno o
  varios tipos. Los filtros se combinan con «y» entre sí y con «o»
  dentro de cada uno.
- Donde se filtre por cuenta, el sistema deberá incluir solo esa cuenta
  (no sus bolsillos) y las transferencias en las que sea origen o
  destino.
- Donde se filtre por categoría, el sistema deberá excluir los tipos que
  no llevan categoría.
- El sistema deberá excluir por defecto los movimientos anulados. Donde
  se pidan, deberá incluirlos marcados como anulados.
- El sistema deberá paginar los resultados.
- El sistema deberá devolver junto al listado los totales del conjunto
  filtrado completo, no solo de la página:
  - **ingresos:** incluye los rendimientos, con los rendimientos
    también por separado;
  - **gastos;**
  - **neto:** ingresos − gastos.

  Transferencias, ajustes y movimientos anulados nunca suman en estos
  totales.
- Si el rango de fechas está invertido, entonces el sistema deberá
  rechazar la consulta.

**RF-18. Ver un movimiento**
- Cuando consulte un movimiento, el sistema deberá devolver todos sus
  datos y su estado (vigente o anulado, con el momento y el motivo de la
  anulación).

### 4.8 Corrección y anulación

**RF-19. Corregir un movimiento**
- Cuando corrija un movimiento, el sistema deberá aplicar los cambios
  manteniendo su identidad (sigue siendo un solo movimiento) y guardar la
  versión anterior completa con el momento del cambio.
- El sistema deberá validar la versión corregida con las mismas reglas
  que un movimiento nuevo, con una excepción: la cuenta y la categoría
  que el movimiento ya tenía se aceptan aunque estén archivadas. Una
  cuenta o categoría **nueva** debe estar activa.
- Si la corrección intenta cambiar el tipo, entonces el sistema deberá
  rechazarla. Para cambiar el tipo se anula el movimiento y se crea otro.
- Si el movimiento es un ajuste o está anulado, entonces el sistema
  deberá rechazar la corrección.
- Si la corrección no cambia ningún dato (comparando el comercio según
  RF-13), entonces el sistema no deberá crear una versión nueva.
- Cuando lleguen dos correcciones del mismo movimiento casi a la vez, el
  sistema deberá aplicar la última y guardar ambas en el historial.

**RF-20. Historial de versiones**
- Cuando consulte el historial de un movimiento, el sistema deberá
  devolver todas sus versiones en orden cronológico, con el momento de
  cada cambio y los campos que cambiaron, y al final la anulación, si la
  hay.
- El sistema no deberá permitir modificar ni borrar versiones
  anteriores.

**RF-21. Anular un movimiento**
- Cuando anule un movimiento, el sistema deberá marcarlo como anulado con
  el momento de la anulación y un motivo opcional. Desde entonces deja de
  contar en saldos y totales, pero sigue siendo consultable.
- La anulación es definitiva. Si intento anular un movimiento ya
  anulado, entonces el sistema deberá rechazar la operación.
- El sistema no deberá ofrecer ninguna forma de borrar un movimiento.

### 4.9 Errores

**RF-22. Errores y operaciones completas**
- Si una operación es rechazada, entonces el sistema no deberá guardar
  ningún cambio, ni siquiera parcial.
- Si una operación es rechazada, entonces el sistema deberá devolver el
  tipo de error (**datos inválidos**, **recurso inexistente** o
  **conflicto de estado**) y el campo que falló, con un mensaje en
  español.
- Si una operación usa o pide una cuenta, categoría o movimiento de otro
  usuario, entonces el sistema deberá responder exactamente igual que si
  no existiera.

## 5. Requisitos no funcionales

- **RNF-1. Exactitud (test):** un escenario sintético fijo (ver criterio
  de finalización 3) debe producir exactamente los saldos por cuenta, el
  subtotal de Lulo, el total general y los totales del listado escritos
  de antemano en la prueba. Ningún cálculo usa números decimales con
  pérdida de precisión.
- **RNF-2. Trazabilidad (test y revisión):** ninguna corrección ni
  anulación borra información. Las versiones anteriores y las
  anulaciones quedan consultables con su momento.
- **RNF-3. Rendimiento (test):** registrar un movimiento y consultar los
  saldos debe tener un p95 (el 95 % de las peticiones) menor a 300 ms con
  10.000 movimientos almacenados, en el entorno local.
- **RNF-4. Acceso (test):** toda petición exige una contraseña única
  configurada fuera del repositorio, también en local. Si la contraseña
  no está configurada, el núcleo no arranca. Esta protección se
  sustituye por cuentas de usuario en la spec 004. La contraseña solo
  puede contener caracteres ASCII imprimibles y sin espacios (las cabeceras
  HTTP no admiten otros); si no cumple, el núcleo no arranca. Excepciones,
  porque no contienen datos:
  - la comprobación de estado del servicio es siempre pública;
  - la documentación de la API y su esquema son públicos **solo en el
    entorno local** y están desactivados en producción.
- **RNF-5. Aislamiento entre usuarios (test):** cada operación (crear,
  leer, listar, corregir, anular, ajustar, consultar saldos, ver
  historial y listar comercios) debe probarse con al menos dos usuarios
  sintéticos, creados directamente en las pruebas, y comprobar que
  ninguno ve, modifica ni usa datos del otro.
- **RNF-6. Datos sintéticos (revisión):** los datos de prueba y
  demostración son inventados. Ningún dato real entra al repositorio.
- **RNF-7. Idioma (test):** todos los mensajes para el usuario están en
  español.
- **RNF-8. Verificabilidad (test):** cada RF tiene al menos una prueba
  automatizada. La fecha de «hoy» debe poder fijarse en las pruebas. La
  cobertura de pruebas del backend es ≥ 90 %.
- **RNF-9. Interfaz documentada (revisión):** la interfaz programática
  está documentada y se puede explorar en local.

## 6. Casos límite

Montos en centavos: `2500000` = $ 25.000.

| # | Caso | Comportamiento esperado |
|---|------|------------------------|
| CL-1 | Gasto que deja la cuenta en negativo | Se guarda, con advertencia (RF-14). |
| CL-2 | Gasto registrado antes que el ingreso del mismo día | El gasto se guarda con advertencia. Al registrar el ingreso el saldo vuelve a positivo y ya no hay advertencia. |
| CL-3 | Retiro de cajero de $ 200.000 con comisión de $ 7.000 | Se registran dos movimientos: una transferencia de `20000000` a Efectivo y un gasto normal de `700000` en «Comisiones bancarias». Los gastos totales suben solo $ 7.000. |
| CL-4 | Transferencia entre dos bolsillos de Lulo | Permitida. El subtotal de Lulo y el total general no cambian. |
| CL-5 | Transferencia de una cuenta a sí misma | Rechazada. |
| CL-6 | Movimiento con fecha de mañana | Rechazado. |
| CL-7 | Movimiento con fecha 31 de febrero | Rechazado. |
| CL-8 | Movimiento con fecha igual a la fecha de inicio de la cuenta | Aceptado. Se suma al saldo inicial. |
| CL-9 | Movimiento anterior a la fecha de inicio de la cuenta | Rechazado. |
| CL-10 | Cuenta con fecha de inicio futura | Rechazada. |
| CL-11 | Monto `0`, `-500000`, `2500.5` o `"25.000"` | Rechazado (RF-1). |
| CL-12 | Rendimiento de `123456` ($ 1.234,56) | Aceptado y sumado exacto. |
| CL-13 | Saldo inicial `0` o `-500000` | Aceptado. |
| CL-14 | Ajuste cuando el saldo real coincide | No se crea movimiento. Se informa que la cuenta cuadra. |
| CL-15 | Ajuste de Lulo cuando tiene bolsillos | Compara solo el saldo propio de Lulo. Los bolsillos no cambian. |
| CL-16 | Ajuste con saldo real negativo (`-500000`) y saldo actual `0` | Ajuste de salida por `500000`, con advertencia de saldo negativo. |
| CL-17 | Ajuste con fecha distinta de hoy | Rechazado. |
| CL-18 | Corregir un ajuste | Rechazado. Anularlo sí se permite. |
| CL-19 | Corregir un gasto cambiando su cuenta | Se crea una versión nueva y ambos saldos se recalculan, con advertencia si alguno queda negativo. |
| CL-20 | Corregir una transferencia para que origen = destino | Rechazado. |
| CL-21 | Corregir un gasto para convertirlo en transferencia | Rechazado (no se cambia el tipo). |
| CL-22 | Corregir la nota de un gasto cuya categoría está archivada | Permitido. Conserva la categoría. |
| CL-23 | Corregir un gasto eligiendo una categoría archivada | Rechazado. |
| CL-24 | Corrección que solo cambia «rappi» por «RAPPI» | No se crea versión. |
| CL-25 | Corregir o anular un movimiento ya anulado | Rechazado. |
| CL-26 | Anular un ingreso y que la cuenta quede en negativo | Se anula, con advertencia. |
| CL-27 | Anular un movimiento de una cuenta archivada | Permitido, con advertencia porque la cuenta queda con saldo distinto de cero. |
| CL-28 | Archivar una cuenta con saldo distinto de cero | Rechazado. |
| CL-29 | Archivar Lulo con bolsillos activos | Rechazado, indicando qué bolsillos archivar primero. |
| CL-30 | Desarchivar un bolsillo con Lulo archivado | Rechazado. |
| CL-31 | Borrar una categoría precargada nunca usada | Permitido. |
| CL-32 | Borrar una categoría usada solo por un movimiento anulado | Rechazado. |
| CL-33 | Crear una cuenta «nequi» cuando ya existe «Nequi» | Rechazado por nombre duplicado. |
| CL-34 | Crear un bolsillo cuyo padre es otro bolsillo | Rechazado. |
| CL-35 | Filtrar por la cuenta Nequi | Incluye las transferencias donde Nequi es origen o destino. |
| CL-36 | Filtrar por la cuenta Lulo | No incluye los movimientos de sus bolsillos. |
| CL-37 | Rango del 1 al 31 de enero | Incluye los movimientos del 1 y del 31. |
| CL-38 | Totales con ingreso de 100, rendimiento de 10, gasto de 30, transferencia de 50 y ajuste de 5 | Ingresos 110 (rendimientos 10), gastos 30, neto 80. |
| CL-39 | Usar como destino, consultar o anular algo de otro usuario | Se responde «recurso inexistente», igual que si no existiera. |

## 7. Fuera de alcance

- **Otras specs:** interfaz gráfica (002), reportes y presupuestos (003),
  registro de usuarios e inicio de sesión (004), agente de WhatsApp
  (005), importación desde Excel (006), conciliación con extractos (007)
  y sugerencias de categoría o insights (008).
- **Interfaz (002):** interpretar montos escritos como texto, mostrarlos
  en formato de pesos y recordar la última cuenta usada.
- **Movimientos:** comisiones vinculadas a una transferencia (se
  registran como gasto normal), revertir una anulación, cambiar el tipo
  al corregir, movimientos programados, recurrentes o con fecha futura, y
  movimientos con hora.
- **Ajustes:** ajustes con fecha pasada o recálculo automático de
  ajustes.
- **Saldos:** saldo a una fecha pasada (spec 003).
- **Cuentas:** cambiar el tipo o la cuenta padre, y bolsillos de Nequi u
  otras billeteras.
- **Datos:** multimoneda (solo COP), subcategorías, etiquetas, archivos
  adjuntos, catálogo formal de comercios y exportación.
- **Validaciones extra:** detección de movimientos duplicados y un monto
  máximo de negocio por movimiento (solo existe el límite técnico de
  RF-1).
- **Usuarios:** cuentas o movimientos compartidos entre usuarios.

## 8. Criterios de finalización

La spec 001 está terminada cuando:

1. Cada RF (RF-1 a RF-22) tiene pruebas automatizadas que pasan, y cada
   caso límite de la sección 6 está cubierto por al menos una.
2. La cobertura de pruebas del backend es ≥ 90 %.
3. Una prueba automatizada reproduce un mes sintético fijo:
   - crear las cuentas Lulo, dos bolsillos, Nequi y Efectivo;
   - registrar gastos, ingresos, un retiro de cajero y su comisión, una
     transferencia entre bolsillos, un rendimiento y un ajuste;
   - corregir un movimiento y anular otro.

   Al final, los saldos coinciden exactamente con los valores escritos de
   antemano en la prueba (RNF-1).
4. Las pruebas de aislamiento de RNF-5 pasan en cada operación.
5. Sin la contraseña, toda petición es rechazada. Sin contraseña
   configurada, el núcleo no arranca (RNF-4).
6. RNF-3 se mide y cumple.
7. Por revisión: la interfaz está documentada y no hay datos reales en el
   repositorio.
8. La integración continua (definida en el plan) pasa en verde.

## 9. Dudas resueltas

- **D-1** La protección antes de la spec 004 es una contraseña única, que
  siempre es obligatoria (RNF-4).
- **D-2** Una corrección no puede cambiar el tipo (RF-19).
- **D-3** La detección de duplicados queda fuera del MVP.
- **D-4** Los ajustes no se corrigen, solo se anulan (RF-12).
- **D-5** No hay monto máximo de negocio en el MVP. Solo existe el
  límite técnico de RF-1.

Los detalles de implementación (tamaño de página, orden de desempate,
longitudes máximas, reglas exactas de normalización del comercio e
integración continua) se definen en el plan.
