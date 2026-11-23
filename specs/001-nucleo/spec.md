# Spec 001 — Núcleo

- **Estado:** Borrador para revisión
- **Fecha:** 2026-11-23
- **Roadmap:** primera versión funcional (001 de 008)

## 1. Contexto y objetivo

### Contexto
Hoy llevo mis finanzas en una plantilla de Excel. Funciona, pero editar
las hojas es tan engorroso que termino sin registrar gastos, y entonces
los saldos y reportes dejan de reflejar la realidad. La app completa
(web, WhatsApp, reportes, importación, conciliación, ML) va a depender de
un mismo núcleo: cuentas, movimientos, categorías y saldos.

### Objetivo
Construir ese núcleo **sin interfaz gráfica ni WhatsApp**. Se accede por
una interfaz programática y debe ser correcto, exacto y auditable. Al
terminar esta spec debo poder:

1. Dar de alta mis cuentas reales (Lulo Bank y sus bolsillos, Nequi y
   efectivo) con su saldo inicial.
2. Registrar cualquier movimiento de mi vida financiera real.
3. Saber en todo momento cuánto dinero tengo en cada cuenta y en total.
4. Consultar y filtrar mi historial.
5. Corregir errores sin perder el rastro de lo que cambió.

### Por qué primero
Todas las specs siguientes (002–008) leen y escriben sobre este núcleo.
Un error aquí, como un saldo mal calculado o una transferencia contada
como gasto, se propagaría a la web, los reportes y el ML. Por eso esta
spec prioriza la exactitud y la trazabilidad por encima de la comodidad.

## 2. Usuarios

| Usuario | Descripción |
|---------|-------------|
| **Yo (propietario)** | Único usuario en esta versión. Estudiante en Colombia que maneja pesos colombianos (COP) en Lulo Bank, Nequi y efectivo. |
| **Conocidos (futuros)** | Otras personas con las que compartiré la app cuando exista el registro de usuarios (spec 004). Cada uno tendrá sus propias cuentas, categorías y movimientos. |
| **Clientes del núcleo (futuros)** | La app web (002), el agente de WhatsApp (005) y el importador (006). No son personas, pero consumen las mismas capacidades y necesitan errores claros y predecibles. |

La app es **multiusuario por diseño**: toda entidad (cuenta, categoría,
movimiento, versión, comercio) pertenece a un usuario, y ningún usuario
puede ver ni modificar datos de otro. En esta spec existe un solo
usuario. El registro y la autenticación de usuarios llegan en la
spec 004.

## 3. Historias de usuario

- **HU-1:** Como propietario, quiero crear mis cuentas con su saldo
  inicial para que el sistema parta de mi dinero real.
- **HU-2:** Como propietario, quiero que los bolsillos de Lulo se agrupen
  bajo Lulo para ver tanto el saldo de cada bolsillo como el de Lulo en
  conjunto.
- **HU-3:** Como propietario, quiero definir mis propias categorías de
  gasto e ingreso para clasificar mis movimientos a mi manera.
- **HU-4:** Como propietario, quiero registrar un gasto o un ingreso con
  monto, fecha, cuenta, categoría, comercio y nota para que mi historial
  sea completo.
- **HU-5:** Como propietario, quiero registrar transferencias entre mis
  cuentas (incluidos los retiros de cajero y los movimientos entre
  bolsillos) sin que cuenten como gasto ni como ingreso, para que mis
  reportes no se inflen.
- **HU-6:** Como propietario, quiero registrar la comisión de un retiro
  o transferencia en el mismo paso para no olvidarla.
- **HU-7:** Como propietario, quiero registrar los rendimientos de mis
  cuentas como ingreso para saber cuánto me genera el ahorro.
- **HU-8:** Como propietario, quiero ajustar el saldo de una cuenta al
  valor real que veo en el banco, dejando constancia del ajuste, para
  corregir descuadres sin buscar el error movimiento por movimiento.
- **HU-9:** Como propietario, quiero consultar el saldo actual de cada
  cuenta y el total para saber cuánto dinero tengo.
- **HU-10:** Como propietario, quiero listar mis movimientos filtrando
  por fechas, cuenta, categoría y tipo, y ver los totales, para revisar
  en qué se va mi dinero.
- **HU-11:** Como propietario, quiero corregir o anular un movimiento y
  ver su historial de cambios para arreglar errores sin perder el rastro.
- **HU-12:** Como propietario, quiero que el sistema me advierta cuando
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

**RF-1. Montos exactos en COP**
- El sistema deberá representar todo monto en pesos colombianos con
  precisión exacta de centavos, sin redondeos ni errores de
  representación.
- El sistema deberá aceptar montos solo como valores estrictamente
  positivos. El tipo de movimiento determina si el monto suma o resta.
- Si se recibe un monto igual a cero, negativo, con más de dos decimales
  o no numérico, entonces el sistema deberá rechazar la operación con un
  mensaje que indique el campo y el motivo.

**RF-2. Fechas de movimiento**
- El sistema deberá registrar cada movimiento con una fecha de calendario
  (día, sin hora obligatoria), interpretada en la zona horaria de Bogotá.
- Cuando no se indique fecha, el sistema deberá usar la fecha de hoy en
  Bogotá.
- Si la fecha es posterior a hoy en Bogotá, entonces el sistema deberá
  rechazar el movimiento indicando que no se admiten fechas futuras.
- Si la fecha es anterior a la fecha de inicio de alguna cuenta
  involucrada, entonces el sistema deberá rechazar el movimiento
  indicando la fecha de inicio de esa cuenta.
- El sistema deberá guardar además el momento exacto de registro de cada
  movimiento, para ordenar los movimientos de un mismo día.

### 4.2 Cuentas

**RF-3. Crear cuenta**
- Cuando cree una cuenta, el sistema deberá exigir: nombre, tipo (banco,
  bolsillo, billetera digital o efectivo), saldo inicial (puede ser cero
  o negativo) y fecha de inicio (por defecto, hoy).
- Donde la cuenta sea de tipo bolsillo, el sistema deberá exigir una
  cuenta padre de tipo banco.
- Si el nombre ya existe en otra cuenta del mismo usuario (sin
  distinguir mayúsculas ni espacios sobrantes), entonces el sistema
  deberá rechazar la creación. Usuarios distintos pueden tener cuentas
  con el mismo nombre.
- Si la cuenta padre no existe, está archivada o es a su vez un
  bolsillo, entonces el sistema deberá rechazar la creación.
- El sistema deberá arrancar sin cuentas precargadas.

**RF-4. Editar y archivar cuenta**
- Cuando renombre una cuenta, el sistema deberá aplicar la misma regla de
  nombre único de RF-3 y conservar todos sus movimientos.
- El sistema no deberá permitir editar el saldo inicial ni la fecha de
  inicio de una cuenta que ya tenga movimientos. Los cambios de saldo se
  hacen con un ajuste (RF-11).
- Cuando archive una cuenta, el sistema deberá impedir nuevos movimientos
  en ella y conservar intacto su historial.
- Mientras una cuenta esté archivada, el sistema deberá permitir
  corregir y anular sus movimientos existentes.
- Si intento archivar una cuenta banco que tiene bolsillos activos,
  entonces el sistema deberá rechazar la operación indicando qué
  bolsillos debo archivar primero.
- Cuando desarchive una cuenta, el sistema deberá volver a aceptar
  movimientos en ella.
- El sistema no deberá permitir borrar una cuenta que tenga movimientos.
  Donde la cuenta no tenga ningún movimiento, el sistema deberá permitir
  borrarla.

### 4.3 Categorías

**RF-5. Gestionar categorías**
- El sistema deberá arrancar sin categorías precargadas.
- Cuando cree una categoría, el sistema deberá exigir nombre y clase
  (gasto o ingreso).
- Si el mismo usuario ya tiene una categoría con el mismo nombre en la
  misma clase (sin distinguir mayúsculas ni espacios sobrantes),
  entonces el sistema deberá rechazar la creación.
- Cuando renombre una categoría, el sistema deberá reflejar el nuevo
  nombre en todos sus movimientos, incluidos los históricos.
- El sistema no deberá permitir cambiar la clase de una categoría que ya
  tenga movimientos.
- Cuando archive una categoría, el sistema deberá dejar de aceptarla en
  movimientos nuevos y conservarla en los existentes.
- El sistema no deberá permitir borrar una categoría con movimientos.
  Donde no tenga ninguno, el sistema deberá permitir borrarla.
- Las categorías son planas: no hay subcategorías.

### 4.4 Movimientos

**RF-6. Datos comunes de un movimiento**
- El sistema deberá registrar en cada movimiento: tipo, monto, fecha,
  cuenta(s), y opcionalmente comercio y nota.
- El sistema deberá admitir cinco tipos: **gasto**, **ingreso**,
  **transferencia**, **rendimiento** y **ajuste**.
- Si alguna cuenta involucrada está archivada, entonces el sistema
  deberá rechazar el movimiento.

**RF-7. Gasto**
- Cuando registre un gasto, el sistema deberá exigir una cuenta de origen
  y una categoría activa de clase gasto, y restar el monto del saldo de
  esa cuenta.
- Si la categoría no existe, está archivada o es de clase ingreso,
  entonces el sistema deberá rechazar el gasto.
- Si no existe ninguna categoría activa de clase gasto, entonces el
  sistema deberá rechazar el gasto indicando que primero debo crear una.

**RF-8. Ingreso**
- Cuando registre un ingreso, el sistema deberá exigir una cuenta de
  destino y una categoría activa de clase ingreso, y sumar el monto al
  saldo de esa cuenta.
- Si la categoría no existe, está archivada o es de clase gasto,
  entonces el sistema deberá rechazar el ingreso.

**RF-9. Transferencia entre cuentas propias**
- Cuando registre una transferencia, el sistema deberá exigir una cuenta
  de origen y una de destino distintas, restar el monto del origen y
  sumarlo al destino en una sola operación indivisible.
- El sistema deberá permitir transferencias entre cualquier par de
  cuentas activas: principal ↔ bolsillo, bolsillo ↔ bolsillo, banco ↔
  billetera digital, y cualquier cuenta ↔ efectivo.
- El sistema deberá registrar un retiro de cajero como una transferencia
  hacia la cuenta de efectivo.
- El sistema no deberá contar una transferencia como gasto ni como
  ingreso en ningún total.
- Una transferencia no lleva categoría. Si se envía una, entonces el
  sistema deberá rechazar la operación.
- Si el origen y el destino son la misma cuenta, entonces el sistema
  deberá rechazar la transferencia.

**RF-10. Comisión asociada a una transferencia**
- Donde una transferencia tenga comisión, el sistema deberá permitir
  indicar en la misma operación el monto de la comisión y una categoría
  de gasto. En ese caso creará un gasto aparte, vinculado a la
  transferencia, que se resta de la cuenta de origen.
- Cuando registre una transferencia con comisión, el sistema deberá
  guardar ambos movimientos o ninguno.
- Cuando anule una transferencia con comisión vinculada, el sistema
  deberá anular también la comisión. Cuando revierta esa anulación,
  deberá revertir también la de la comisión.
- La comisión sí cuenta como gasto en los totales.

**RF-11. Ajuste de saldo**
- Cuando indique el saldo real de una cuenta a una fecha (por defecto,
  hoy), el sistema deberá calcular la diferencia contra el saldo que
  registra a esa fecha y crear un movimiento de tipo ajuste. Su monto
  será el valor absoluto de la diferencia (siempre positivo, como exige
  RF-1) y su dirección será de entrada si el saldo real es mayor y de
  salida si es menor.
- Si la diferencia es cero, entonces el sistema no deberá crear ningún
  movimiento e informará que la cuenta ya cuadra.
- El sistema deberá mostrar los ajustes en el historial y en el listado
  de movimientos.
- El sistema no deberá contar un ajuste como gasto ni como ingreso en
  ningún total.
- Un ajuste no lleva categoría.

**RF-12. Rendimiento**
- Cuando registre un rendimiento, el sistema deberá exigir una cuenta de
  destino y sumar el monto a su saldo.
- El sistema deberá permitir rendimientos en cualquier cuenta, no solo
  en el bolsillo de ahorro.
- El sistema deberá contar los rendimientos como ingreso en los totales,
  e identificarlos por separado para que puedan distinguirse del resto
  de ingresos.
- Un rendimiento no exige categoría: su tipo ya lo clasifica.

**RF-13. Comercio y nota**
- Cuando se registre un comercio, el sistema deberá normalizarlo
  (eliminar espacios sobrantes y unificar mayúsculas y minúsculas) para
  que «rappi », «RAPPI» y «Rappi» se traten como el mismo comercio.
- El sistema deberá ofrecer la lista de comercios ya usados por el
  usuario (nunca los de otros usuarios), ordenada
  por frecuencia de uso, para poder reutilizarlos.
- Si el comercio o la nota superan una longitud razonable, entonces el
  sistema deberá rechazar la operación indicando el límite. El límite se
  fija en el plan.

**RF-14. Advertencia de saldo negativo**
- Cuando un movimiento nuevo, una corrección o una reversión de
  anulación deje en negativo el saldo actual de alguna cuenta
  involucrada, el sistema deberá guardar la operación y devolver una
  advertencia que indique la cuenta y su saldo resultante.
- El sistema no deberá bloquear ninguna operación por saldo negativo.

### 4.5 Saldos

**RF-15. Saldo por cuenta**
- El sistema deberá calcular el saldo de cada cuenta como: saldo inicial
  + entradas (ingresos, rendimientos, transferencias recibidas y ajustes
  de entrada) − salidas (gastos, comisiones, transferencias enviadas y
  ajustes de salida), contando solo los movimientos no anulados.
- El sistema no deberá guardar un saldo editable. El saldo se deriva
  siempre de los movimientos.
- El sistema deberá permitir consultar el saldo de una cuenta a una
  fecha dada (por defecto, hoy).

**RF-16. Saldo agrupado y total**
- Cuando consulte los saldos, el sistema deberá devolver, por cada
  cuenta, su saldo propio, y por cada cuenta banco con bolsillos, un
  subtotal «cuenta + bolsillos».
- El sistema deberá devolver un total general que sume cada cuenta una
  sola vez (sin duplicar los bolsillos dentro del subtotal del banco).
- El sistema deberá incluir en el total las cuentas archivadas cuyo
  saldo sea distinto de cero, marcadas como archivadas.

### 4.6 Consulta de movimientos

**RF-17. Listar y filtrar**
- El sistema deberá listar los movimientos ordenados por fecha
  descendente y, dentro del mismo día, por momento de registro
  descendente.
- El sistema deberá permitir filtrar por rango de fechas, una o varias
  cuentas, una o varias categorías y uno o varios tipos. Los filtros se
  combinan con «y» entre sí y con «o» dentro de cada uno.
- Donde se filtre por cuenta, el sistema deberá incluir las
  transferencias en las que esa cuenta sea origen o destino.
- El sistema deberá excluir por defecto los movimientos anulados.
  Donde se pida explícitamente, deberá incluirlos marcados como anulados.
- El sistema deberá paginar los resultados.
- El sistema deberá devolver junto al listado los totales del conjunto
  filtrado completo (no solo de la página): total de gastos, total de
  ingresos (con los rendimientos desglosados) y neto. Transferencias y
  ajustes quedan excluidos de estos totales.
- Si el rango de fechas está invertido, entonces el sistema deberá
  rechazar la consulta.

**RF-18. Ver un movimiento**
- Cuando consulte un movimiento, el sistema deberá devolver todos sus
  datos, su estado (vigente o anulado) y, si aplica, la comisión o
  transferencia vinculada.

### 4.7 Corrección y anulación

**RF-19. Corregir un movimiento**
- Cuando corrija un movimiento, el sistema deberá aplicar los cambios
  manteniendo su identidad (sigue siendo un solo movimiento en los
  listados) y guardar la versión anterior completa con el momento del
  cambio.
- El sistema deberá validar la versión corregida con las mismas reglas
  que un movimiento nuevo (RF-1 a RF-13).
- Si la corrección no cambia ningún dato, entonces el sistema no deberá
  crear una nueva versión.
- Si el movimiento está anulado, entonces el sistema deberá rechazar la
  corrección hasta que se revierta la anulación.

**RF-20. Historial de versiones**
- Cuando consulte el historial de un movimiento, el sistema deberá
  devolver todas sus versiones en orden cronológico, con el momento de
  cada cambio y los campos que cambiaron.
- El sistema no deberá permitir modificar ni borrar versiones
  anteriores.

**RF-21. Anular y revertir anulación**
- Cuando anule un movimiento, el sistema deberá marcarlo como anulado con
  el momento de la anulación y un motivo opcional. A partir de entonces
  dejará de contar en saldos y totales, pero seguirá siendo consultable.
- Cuando revierta la anulación, el sistema deberá volver a contarlo en
  saldos y totales y registrar el momento de la reversión en su
  historial.
- Si intento anular un movimiento ya anulado, o revertir uno vigente,
  entonces el sistema deberá rechazar la operación.
- El sistema no deberá ofrecer ninguna forma de borrar definitivamente
  un movimiento.

### 4.8 Errores

**RF-22. Errores claros**
- Si una operación es rechazada, entonces el sistema deberá devolver un
  mensaje en español que indique qué campo falló y por qué, sin guardar
  ningún cambio parcial.
- El sistema deberá distinguir entre: datos inválidos, recurso
  inexistente, conflicto de estado (por ejemplo, cuenta archivada o
  nombre duplicado) y error interno.

## 5. Requisitos no funcionales

- **RNF-1. Exactitud:** ninguna operación puede introducir errores de
  redondeo. La suma de los saldos de todas las cuentas debe ser igual a
  la suma de los saldos iniciales + ingresos + rendimientos − gastos ±
  ajustes, en todo momento.
- **RNF-2. Atomicidad:** toda operación que afecte varios movimientos o
  cuentas (transferencia con comisión, anulación en cascada) se aplica
  completa o no se aplica.
- **RNF-3. Trazabilidad:** ningún dato financiero se pierde. Toda
  corrección, anulación y reversión queda registrada con su momento.
- **RNF-4. Rendimiento:** registrar un movimiento y consultar los saldos
  debe responder en menos de 300 ms con 50 000 movimientos almacenados,
  en el entorno local. El registro rápido de las specs 002 y 005 depende
  de esto.
- **RNF-5. Protección de acceso antes de la spec 004:** hasta que exista
  el registro de usuarios, la app se ejecuta solo en local. Si se
  despliega antes, la protección mínima es una contraseña única definida
  en una variable de entorno, que se exige en toda petición. No hay
  registro de usuarios en esta spec. La contraseña nunca se guarda en el
  repositorio. Si no está definida, una instancia desplegada no deberá
  arrancar.
- **RNF-6. Privacidad de los datos:** los datos de prueba y demostración
  son sintéticos. Ningún dato real entra al repositorio.
- **RNF-7. Aislamiento entre usuarios:** toda entidad tiene un usuario
  dueño desde esta spec, y toda lectura, escritura, saldo, total y
  listado se limita a los datos del usuario que hace la petición. Las
  pruebas deben comprobar, con al menos dos usuarios sintéticos creados
  directamente en las pruebas, que ninguno puede ver, modificar, anular
  ni referenciar (p. ej. usar como cuenta destino o categoría) datos del
  otro. Una referencia a un recurso de otro usuario se trata como
  recurso inexistente.
- **RNF-8. Idioma:** todos los mensajes para el usuario están en
  español. Los montos se presentan en formato colombiano (p. ej.
  `$ 25.000` o `$ 1.234,56`).
- **RNF-9. Verificabilidad:** cada RF tiene al menos una prueba
  automatizada. La cobertura de pruebas del núcleo es ≥ 90 %.
- **RNF-10. Contrato estable:** la interfaz programática está
  documentada y es consumible por la web (002), WhatsApp (005) y el
  importador (006) sin cambios incompatibles. Añadir la autenticación de
  la spec 004 no deberá cambiar la forma de las operaciones del núcleo.

## 6. Casos límite

| # | Caso | Comportamiento esperado |
|---|------|------------------------|
| CL-1 | Gasto que deja la cuenta en negativo | Se guarda y se devuelve la advertencia de RF-14. |
| CL-2 | Gasto registrado antes que el ingreso del mismo día | Se permite. El saldo puede pasar temporalmente a negativo, con advertencia. |
| CL-3 | Retiro de cajero de $ 200.000 con comisión de $ 7.000 | Transferencia de $ 200.000 a Efectivo + gasto vinculado de $ 7.000. El origen baja $ 207.000, Efectivo sube $ 200.000 y los gastos totales suben solo $ 7.000. |
| CL-4 | Transferencia entre dos bolsillos de Lulo | Permitida. El subtotal de Lulo no cambia y el total general tampoco. |
| CL-5 | Transferencia de una cuenta a sí misma | Rechazada. |
| CL-6 | Movimiento con fecha de mañana | Rechazado (sin fechas futuras). |
| CL-7 | Movimiento a las 23:30 hora de Bogotá | Se registra con la fecha de Bogotá, aunque en UTC ya sea el día siguiente. |
| CL-8 | Movimiento anterior a la fecha de inicio de la cuenta | Rechazado, indicando la fecha de inicio. |
| CL-9 | Gasto cuando no existe ninguna categoría de gasto | Rechazado, con un mensaje que pide crear una categoría primero. |
| CL-10 | Monto `0`, `-5000` o `25000,555` | Rechazado (RF-1). |
| CL-11 | Monto con centavos, p. ej. un rendimiento de $ 1.234,56 | Aceptado y sumado sin redondeo. |
| CL-12 | Ajuste cuando el saldo real coincide | No se crea movimiento. Se informa que la cuenta cuadra. |
| CL-13 | Ajuste con fecha pasada y movimientos posteriores | La diferencia se calcula contra el saldo a esa fecha. Los movimientos posteriores siguen sumando normalmente. |
| CL-14 | Corregir un gasto y cambiar su cuenta | Se crea una versión nueva y ambos saldos se recalculan. Si la nueva cuenta queda en negativo, hay advertencia. |
| CL-15 | Corregir una transferencia para que origen = destino | Rechazado (mismas reglas que un movimiento nuevo). |
| CL-16 | Anular una transferencia que tiene comisión | Se anulan ambas. Al revertir, se revierten ambas. |
| CL-17 | Corregir un movimiento anulado | Rechazado hasta revertir la anulación. |
| CL-18 | Archivar una categoría con movimientos | Permitido. Los movimientos la conservan y deja de aceptarse en movimientos nuevos. |
| CL-19 | Archivar Lulo con bolsillos activos | Rechazado, indicando qué bolsillos hay que archivar primero. |
| CL-20 | Archivar una cuenta con saldo distinto de cero | Permitido. Sigue apareciendo en saldos y total, marcada como archivada. |
| CL-21 | Comercio «  rappi » y luego «RAPPI» | Se tratan como el mismo comercio. |
| CL-22 | Filtrar por la cuenta Nequi | Incluye las transferencias donde Nequi es origen o destino. |
| CL-23 | Crear una cuenta «nequi» cuando ya existe «Nequi» | Rechazado por nombre duplicado. |
| CL-24 | Crear un bolsillo cuyo padre es otro bolsillo | Rechazado. |

## 7. Fuera de alcance

- Interfaz gráfica (spec 002) y agente de WhatsApp (spec 005).
- Reportes por categoría o por mes, y presupuestos (spec 003). Esta spec
  solo entrega los totales del listado.
- Registro de usuarios, inicio de sesión y gestión de usuarios
  (spec 004).
- Importación desde Excel (spec 006), conciliación con extractos
  (spec 007) y sugerencias de categoría o insights (spec 008).
- Movimientos programados, recurrentes o con fecha futura.
- Multimoneda: solo COP.
- Subcategorías, etiquetas y archivos adjuntos (recibos, fotos).
- Catálogo formal de comercios (crear, fusionar, categoría por defecto).
- Cuentas o movimientos compartidos entre usuarios.
- Exportación de datos.
- Detección de movimientos duplicados (ver D-3).

## 8. Criterios de finalización

La spec 001 está terminada cuando:

1. Todos los RF (RF-1 a RF-22) tienen pruebas automatizadas que pasan, y
   cada caso límite de la sección 6 está cubierto por al menos una.
2. La cobertura de pruebas del núcleo es ≥ 90 %.
3. Con datos sintéticos, puedo reproducir un mes típico de punta a
   punta: crear las 5 cuentas (Lulo, bolsillo de ahorro, otro bolsillo,
   Nequi, Efectivo), crear categorías, registrar gastos, ingresos, un
   retiro de cajero con comisión, una transferencia entre bolsillos, un
   rendimiento y un ajuste, corregir uno y anular otro. Al final, los
   saldos por cuenta, el subtotal de Lulo y el total coinciden con un
   cálculo hecho a mano.
4. Se cumple el invariante de RNF-1 después de cada operación en las
   pruebas.
5. La interfaz programática está documentada y se puede explorar
   localmente.
6. No hay datos reales en el repositorio.
7. Las pruebas de aislamiento de RNF-7 pasan con al menos dos usuarios
   sintéticos.
8. Con la contraseña de RNF-5 definida, toda petición sin ella es
   rechazada.
9. Las dudas abiertas de la sección 9 están resueltas o pospuestas
   explícitamente a otra spec.

## 9. Dudas abiertas

- **D-1 Protección de acceso antes de la spec 004 (resuelta).** Hasta
  la spec 004 la app corre solo en local. Si se despliega antes, se
  protege con una contraseña única definida en una variable de entorno,
  sin registro de usuarios. Queda recogido en RNF-5.
- **D-2 [NECESITA ACLARACIÓN] Cambio de tipo al corregir.** ¿Una
  corrección puede cambiar el tipo de movimiento (p. ej. un gasto que
  en realidad era una transferencia)? *Recomendación:* permitirlo entre
  gasto, ingreso, transferencia y rendimiento, revalidando todo. No
  permitir convertir en ajuste ni desde ajuste, porque el ajuste se
  calcula y no se teclea.
- **D-3 [NECESITA ACLARACIÓN] Posibles duplicados.** ¿El sistema debe
  advertir (sin bloquear) cuando registro un movimiento igual a otro
  reciente (mismo tipo, monto, cuenta, fecha y comercio)? Útil para el
  registro rápido y WhatsApp. *Recomendación:* posponerlo a 002 o 005.
- **D-4 [NECESITA ACLARACIÓN] Corregir un ajuste.** Un ajuste se calcula
  a partir del saldo real. ¿Se puede corregir su monto a mano, o solo
  anularlo y crear otro? *Recomendación:* solo anular y volver a
  ajustar, para que el ajuste siempre refleje un saldo real observado.
- **D-5 [NECESITA ACLARACIÓN] Límite de monto.** ¿Hay un monto máximo
  por movimiento para atrapar errores de dedo (p. ej. un cero de más)?
  *Recomendación:* no bloquear, pero advertir por encima de un umbral
  configurable. Se puede posponer.
