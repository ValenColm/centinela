
# Centinela

**Motor de detección de fraude transaccional en tiempo real**

## El encargo

Una fintech los contrató. Procesa transacciones de tarjetas y transferencias, y está perdiendo dinero por fraude que nadie detecta a tiempo.

Ustedes van a construir Centinela: el sistema que vigila ese flujo de transacciones y detecta, en tiempo real, cuáles son sospechosas.

Cada vez que un cliente hace una compra, transferencia o retiro, la transacción entra a Centinela. El sistema la analiza contra un conjunto de reglas de riesgo, calcula un puntaje (*score*) y decide en milisegundos:

- **Score bajo** → la transacción sigue su curso normal. El cliente ni se entera.
- **Score alto** → la transacción se marca, se abre un caso de fraude, y un analista humano lo revisa con toda la evidencia en la mano.

Al terminar deben entregar la plataforma completa: la API que recibe transacciones, el motor que las puntúa, el sistema de gestión de casos para los analistas, y la infraestructura en la nube que lo sostiene todo.

## Las tres restricciones que definen su arquitectura

Detectar fraude con reglas no es lo difícil. Lo difícil es hacerlo bajo estas condiciones, que son las de cualquier sistema financiero real.

### El cliente no puede esperar

Cuando alguien pasa su tarjeta, la respuesta debe ser inmediata. Es inaceptable que la transacción se quede colgada mientras el sistema consulta el historial de la cuenta, aplica cuatro reglas y abre un caso.

Esto significa que su sistema debe responderle al cliente **antes** de terminar de analizar la transacción. No es un detalle de rendimiento: es lo que los obliga a diseñar un sistema desacoplado y orientado a eventos, en vez de una cadena de llamadas.

### El volumen no es constante

Un viernes a las 6pm entran muchísimas más transacciones que un martes a las 3am. El sistema tiene que absorber los picos sin perder ni una sola transacción.

Esto significa que las decisiones sobre cómo almacenan y particionan los datos las tienen que tomar al principio, no cuando el sistema ya se esté ahogando.

### El sistema no se puede caer

Si Centinela deja de responder, la fintech deja de operar. Cuando algo falla, alguien tiene que poder abrir una consola y ver exactamente dónde y por qué.

Esto significa despliegue automatizado y observabilidad de punta a punta.

## El motor de detección

La detección se basa en **reglas heurísticas**. No hay Machine Learning: cada regla es lógica que ustedes escriben, entienden y pueden defender.

Cada regla que se dispara suma puntos al score de la transacción.

**Velocidad de transacción**
Demasiadas transacciones desde la misma cuenta en una ventana corta de tiempo. Una cuenta que hace 8 compras en 3 minutos es sospechosa.

**Monto atípico**
El monto está muy por encima del comportamiento histórico de esa cuenta. Si una cuenta suele mover $50.000 y de repente intenta $4.000.000, algo pasa.

**Ubicación geográficamente imposible**
Dos transacciones de la misma cuenta desde ubicaciones que no se pueden recorrer en el tiempo transcurrido. Una compra en Medellín y otra en Madrid con 10 minutos de diferencia significa que una de las dos no la hizo el titular.

**Comercio o categoría de riesgo**
La transacción va hacia un comercio o categoría marcada previamente como sospechosa.

### El umbral

La suma de los puntos es el score. Si supera un **umbral configurable**, se abre un caso.

El umbral no puede ser un número quemado en el código, y van a tener que defender el valor que elijan: uno muy bajo genera falsos positivos y satura a los analistas; uno muy alto deja pasar fraude real.

### Guarden el porqué, no solo el cuánto

Cada regla que se dispara debe registrar **por qué** se disparó, con los datos concretos que la activaron. No basta con guardar `score: 85`.

De esa información depende el explicador, que construyen en la semana 3. Si no la guardan, no van a tener nada que explicar.

## El explicador de casos

Cuando el motor marca una transacción, el analista recibe un caso. Un número y una lista de códigos de regla no le sirven para decidir rápido.

Su sistema debe generar una explicación legible a partir del detalle de las reglas que se dispararon. Con una plantilla determinista, no con un modelo de lenguaje.

Esto es lo que debe producir:

> *Transacción marcada con score 82 (umbral: 60).*
>
> *Se detectaron 3 transacciones de esta cuenta en los últimos 4 minutos, cuando el promedio es de 1 cada 6 horas (+35 puntos).*
>
> *El monto de $4.200.000 supera en 84× el promedio histórico de la cuenta ($50.000) (+30 puntos).*
>
> *La transacción anterior de esta cuenta se originó en Medellín hace 11 minutos; esta se origina en Madrid, a 8.000 km (+17 puntos).*

Si no logran producir un texto así, revisen qué está guardando su motor cuando toma una decisión.

## Verificación de identidad

Cuando un analista necesita confirmar quién es el titular de una cuenta, sube un documento (cédula, extracto bancario). Un servicio de reconocimiento documental extrae automáticamente los datos —nombre, número de identificación, fechas— y los adjunta al caso.

Es el único servicio de inteligencia artificial que van a usar. **Verifiquen su disponibilidad y su cuota en la región que elijan durante el primer día**, antes de construir nada encima. Si no está disponible en su suscripción, pregunten antes de improvisar: hay un plan alternativo definido.

## Los actores del sistema

| Rol                          | Qué hace                                                                                                                                                      |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cliente**            | No interactúa con Centinela. Solo origina transacciones que entran al sistema.                                                                                |
| **Analista de fraude** | Revisa los casos marcados, ve la evidencia y la explicación, y resuelve: confirma el fraude o lo descarta. Escala casos subiendo documentos de verificación. |
| **Administrador**      | Configura las reglas, ajusta el umbral, gestiona comercios de riesgo y administra usuarios.                                                                    |
| **Servicio**           | La identidad que usan los componentes internos del sistema para hablar entre sí. Corre desatendida, sin nadie detrás.                                        |
| **Auditor**            | Ve todo el sistema. No modifica nada.                                                                                                                          |

## Recorrido de una transacción

Este es el camino que hace una transacción desde que entra hasta que un analista la ve. Entender este flujo es entender el proyecto.

1. **Ingesta.** La API recibe la transacción y responde de inmediato con un acuse. No espera al análisis.
2. **Publicación del evento.** La transacción se publica como un evento. Aquí termina la responsabilidad de la API.
3. **Scoring.** Un componente serverless reacciona al evento, consulta el historial reciente de esa cuenta, aplica las reglas y calcula el score.
4. **Decisión.** Si el score supera el umbral, se encola un caso. Si no, la transacción queda registrada.
5. **Apertura del caso.** El caso se crea en la base de datos de gestión, listo para asignarse.
6. **Explicación.** Se genera la explicación legible del porqué de la marca.
7. **Resolución.** El analista revisa, decide y cierra el caso. Todo queda auditado.

Entre el paso 1 y el paso 7 pueden pasar segundos. **El cliente ya recibió su respuesta en el paso 1.** Si su arquitectura hace que el cliente espere por el paso 6, está mal diseñada.

## Dónde vive cada dato

El sistema maneja tres tipos de información con necesidades completamente distintas. Elegir el almacén correcto para cada una es parte del trabajo, y tendrán que justificar sus decisiones.

**Transacciones y scores**
Millones de registros, escritura constante, y una consulta que domina todo lo demás: *"dame las transacciones recientes de esta cuenta"*. El motor hace esa consulta en cada transacción que procesa. Cómo particionen estos datos determina si el sistema escala o se ahoga.

**Casos de fraude**
Volumen bajo comparado con las transacciones, pero con relaciones reales (caso ↔ analista ↔ resolución ↔ auditoría), reportería, y necesidad de trazabilidad. En un sistema financiero tienen que poder responder quién tocó qué y cuándo.

**Documentos de verificación**
Archivos binarios que los analistas suben al escalar un caso. Se escriben una vez y se leen pocas veces.

## El presupuesto es un requisito técnico

Trabajan sobre **una suscripción gratuita de Azure por célula**: 200 dólares de crédito, 30 días de reloj. El proyecto dura 21 días. No hay más dinero y no hay prórroga.

Esto no es una limitación del ejercicio. Es la condición normal de trabajo: ningún cliente les va a dar presupuesto ilimitado, y *"se nos acabó el crédito a mitad de sprint"* no es una excusa aceptable.

**Tres cosas que necesitan saber desde el primer día:**

**El reloj empieza cuando crean la cuenta.** Créenla el primer día del proyecto, no antes. Si alguno de ustedes ya tiene una cuenta gratuita creada hace meses, esa cuenta no sirve — su crédito ya está corriendo o expirado.

**El crédito se agota, no se cobra.** La suscripción tiene un límite de gasto. Cuando el crédito se acaba, los servicios se deshabilitan. Nadie va a recibir un cargo, pero si gastan mal, el sistema deja de existir a mitad de la semana 3.

**Tener crédito no es tener permiso.** Algunos servicios tienen cuota cero en suscripciones gratuitas, sin importar cuánto saldo les quede. Van a chocar con esto. Verifiquen las cuotas de su suscripción antes de comprometerse con cualquier diseño.

**Su objetivo: terminar el proyecto habiendo gastado menos de 60 de los 200 dólares.** Los 140 restantes son su margen de error.

Un diseño que funciona pero agota el crédito antes de la semana 3 es un diseño fallido.

## Fuera del alcance

No trabajen en esto, aunque les sobre tiempo:

- Orquestación de contenedores con clusters gestionados.
- Modelos de lenguaje generativo. El explicador es determinista, con plantilla.
- Entornos de staging con intercambio de despliegue.
- Puntos de acceso privados a los almacenes.
- Capas de gestión de API con niveles dedicados.

Si terminan el alcance base y quieren ir más lejos, vayan hacia **profundidad, no hacia servicios nuevos**: más reglas de detección, mejor manejo de errores, pruebas de carga más agresivas, un explicador más rico. No agreguen nada que consuma crédito.

## Reglas del juego

**El lenguaje es libre.** Construyan el backend y los componentes serverless en lo que su célula domine: C#/.NET, Node.js, Python, Java. Nadie va a ser evaluado por elegir un stack en vez de otro.

**Lo que no es libre es el contrato.** La forma de los eventos y los payloads que cruzan el pipeline la definen y documentan desde el inicio, porque de eso depende que las piezas encajen.

**La infraestructura se crea por script.** Todo debe poder recrearse desde cero ejecutando un script versionado en su repositorio. Si la única forma de reconstruir el sistema es que alguien recuerde qué botones apretó en el portal, no cuenta.

**Ningún secreto vive en el código.** Cadenas de conexión, claves, credenciales: todas van a un gestor de secretos. Un secreto en un commit queda en el historial de git aunque lo borren después.

**Todo se justifica.** No se evalúa que hayan usado un servicio, sino que sepan por qué lo usaron y qué les costó. Por qué esa clave de partición, por qué ese nivel de consistencia, por qué mensajería y no una llamada directa, por qué ese nivel de servicio y no el de arriba.

**Apaguen lo que no estén usando.** Un recurso olvidado encendido un fin de semana puede costarles la semana 3.

## Las tres semanas

**Semana 1 — Fundamentos.**
Levantan la infraestructura, la identidad, la red y la puerta de entrada. Al final, la API recibe transacciones y las persiste. Todavía no detecta nada.

**Semana 2 — El motor.**
Construyen el pipeline serverless de scoring y los almacenes de datos. Al final, una transacción que entra se puntúa automáticamente y abre un caso si corresponde.

**Semana 3 — Producción.**
Automatizan el despliegue, integran la verificación documental, construyen el explicador y hacen el sistema observable. Al final tienen un producto.

Cada semana tiene su propio documento con lo que se solicita y lo que deben entregar.

## Cuándo está terminado

Al cierre del proyecto, su célula tiene que poder pararse frente a alguien que nunca vio el sistema, enviarle una transacción fraudulenta en vivo, y mostrarle:

- que fue detectada por las reglas correctas;
- que el cliente recibió su respuesta antes de que terminara el análisis;
- que el analista tiene un caso abierto con una explicación clara y legible;
- que todo el recorrido de esa transacción es visible en la herramienta de monitoreo;
- que si borran toda la infraestructura, la reconstruyen ejecutando un script;
- y que les sobra crédito.
