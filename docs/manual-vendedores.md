# Manual del Vendedor — NexaCore Agent Manager

> **Nota de idioma:** este documento está en español a propósito. Es material de campo para el
> equipo comercial, no documentación técnica del repositorio (el código y los docs técnicos siguen
> en inglés, según `CLAUDE.md`).

**Para quién es:** Edgar, Enedina y cualquier vendedor que vaya a levantar clientes.
**Para qué sirve:** entender qué vendemos, qué información hay que sacarle al cliente, y cómo se
convierte esa información en un agente que de verdad resuelve.

---

## 1. Qué vendemos (en una frase)

> **Un empleado que contesta los mensajes del negocio 24/7, en WhatsApp, Messenger, Instagram y la
> página web, que ya sabe todo del negocio y nunca deja a un prospecto sin respuesta.**

El cliente **no compra software**. No queremos que entre a configurar nada. El cliente paga una
cuota mensual y **nosotros** montamos, entrenamos y mantenemos su agente. Ese es el trato completo.

### El problema real que resolvemos

Un consultorio dental pierde pacientes porque nadie contesta el WhatsApp a las 9 de la noche.
Un despacho jurídico pierde clientes porque el mensaje de Instagram se quedó sin ver tres días.
Una clínica pierde citas porque la recepcionista está atendiendo a alguien en ventanilla.

**El prospecto que no recibe respuesta en 5 minutos se va con el competidor.** Eso es lo que
vendemos: que nadie se quede sin respuesta.

### Lo que NO vendemos

No vendemos "inteligencia artificial". Si el cliente pregunta por el modelo o la tecnología, la
respuesta corta es: *"usamos la mejor tecnología disponible y la mantenemos actualizada por usted;
lo que a usted le importa es que sus pacientes tengan respuesta"*. En cuanto la conversación se va
a lo técnico, se pierde la venta.

---

## 2. Cómo funciona por dentro (lo mínimo que debes saber para no mentir)

Cuatro piezas. Aprende estas cuatro y puedes explicar el producto entero.

```
CLIENTE  →  AGENTE  →  CANALES  →  CONVERSACIONES
(el negocio) (el "empleado") (por dónde llegan) (lo que se puede ver y retomar)
```

**1. El Cliente** es el negocio: "Consultorio Dental Sonrisas". Tiene su plan, su cuota y su
portal propio.

**2. El Agente** es el empleado virtual. Aquí vive todo lo que sabe del negocio. Un cliente puede
tener varios agentes (por ejemplo, uno para ventas y otro para soporte), pero **casi siempre uno
bien hecho es mejor que tres a medias.**

**3. Los Canales** son por dónde entran los mensajes:

| Canal | Qué es | Qué necesita el cliente |
|---|---|---|
| **WhatsApp (QR)** | Se conecta escaneando un QR, como WhatsApp Web | Solo el teléfono. **El más rápido de activar.** |
| **WhatsApp API oficial** | La vía oficial de Meta | Una cuenta de WhatsApp Business API |
| **Facebook Messenger** | El inbox de la página de Facebook | Ser administrador de la página |
| **Instagram Direct** | Los DM de Instagram | Cuenta profesional ligada a la página |
| **Chat web** | Un widget para su sitio | Poder pegar un código en su página |

**4. Las Conversaciones** son el historial. Todo queda guardado, y aquí está la función que más
tranquiliza al cliente: **el botón de tomar control**.

### El botón de tomar control (tu mejor argumento de venta)

Cada conversación tiene dos modos: **IA** y **Humano**. Cuando alguien del negocio quiere
intervenir, aprieta un botón y **el agente se calla inmediatamente** en esa conversación. La
persona contesta a mano y, cuando quiere, se lo regresa al agente.

Úsalo siempre que salga la objeción *"¿y si el robot dice una tontería?"*:

> *"Usted nunca pierde el control. En cualquier momento entra, aprieta un botón y usted contesta.
> El agente se calla al instante. No es un robot suelto: es un asistente que usted supervisa."*

---

## 3. Cómo se "entrena" un agente

Esto es lo más importante del manual. **El agente es tan bueno como la información que le demos.**
Un agente mal levantado da respuestas genéricas y el cliente cancela al segundo mes.

La información se carga en cinco lugares, y cada uno tiene un propósito distinto:

### a) El brief del negocio (7 campos guiados)

Son los siete campos que están literalmente en el sistema. Tu trabajo en la visita es llenarlos:

| Campo | Qué preguntar |
|---|---|
| **Qué hace el negocio** | "En dos o tres frases, ¿a qué se dedican?" |
| **Productos y servicios** | "¿Qué venden exactamente? ¿Con precios o sin precios?" |
| **Público objetivo** | "¿Quién les escribe normalmente? ¿Cómo hablan?" |
| **Información y políticas clave** | Horarios, dirección, formas de pago, cancelaciones, garantías |
| **Objetivo principal del agente** | "¿Qué quiere que logre? ¿Agendar? ¿Cotizar? ¿Filtrar?" |
| **Debe hacer siempre** | "¿Qué es obligatorio en cada conversación?" |
| **No debe hacer nunca** | "¿Qué le daría pena que dijera?" |

Los dos últimos son los que más se olvidan y **los que más problemas evitan**. Insiste en ellos.

### b) Personalidad y tono

¿Le habla de usted o de tú? ¿Formal o relajado? ¿Usa emojis? Un despacho jurídico y una barbería
no hablan igual. Pregunta: *"si yo le escribiera a su negocio, ¿cómo le gustaría que le
contestaran?"*

### c) Preguntas frecuentes

Pares de pregunta y respuesta exactos. **Aquí va lo que el cliente quiere que se conteste palabra
por palabra**: precios, horarios, ubicación, "¿aceptan tarjeta?", "¿atienden niños?".

Pídele al cliente que abra su WhatsApp y te lea las últimas 20 preguntas que le llegaron. Esas son
las FAQ. No las inventes.

### d) Documentos (PDF)

Listas de precios, catálogos, menús, folletos, reglamentos. El sistema los lee, los parte y busca
el fragmento correcto cuando alguien pregunta algo relacionado. Pide siempre los PDF que ya tenga.

### e) Contexto general del cliente

Información que aplica a todos los agentes de ese negocio: sucursales, historia, datos fiscales
para facturación.

---

## 4. La visita de levantamiento

Tu meta en la primera visita es **salir con la información suficiente para que el agente quede bien
al primer intento**. Si sales con la mitad, vas a regresar tres veces y el cliente se enfría.

### Bloque 1 — El negocio (5 min)
1. ¿A qué se dedica el negocio, en sus palabras?
2. ¿Cuántas personas atienden mensajes hoy?
3. ¿Cuántos mensajes reciben al día, más o menos?
4. ¿Qué pasa con los mensajes que llegan de noche o en fin de semana?

### Bloque 2 — El dolor (5 min) — *aquí se vende*
5. ¿Se le han ido clientes por no contestar a tiempo?
6. ¿Cuánto vale para usted un cliente nuevo? *(anota la cifra; la vas a usar al cotizar)*
7. ¿Cuántas veces al día contestan lo mismo?

### Bloque 3 — Lo operativo (10 min)
8. Horarios de atención y días que cierran
9. Dirección exacta y referencias
10. Formas de pago que aceptan
11. Servicios con sus precios — **y qué precios SÍ se pueden decir por chat y cuáles no**
12. ¿Cómo se agenda una cita hoy? ¿Agenda, teléfono, sistema?
13. Política de cancelación
14. ¿Qué NO debe decir nunca el agente?

### Bloque 4 — Los canales (5 min)
15. ¿Qué número de WhatsApp usan?
16. ¿Tienen página de Facebook? ¿Quién es el administrador?
17. ¿Tienen Instagram? ¿Es cuenta profesional?
18. ¿Tienen sitio web? ¿Quién lo maneja?

### Bloque 5 — Cierre (5 min)
19. ¿Quién va a supervisar las conversaciones del lado de ellos?
20. ¿A qué correo mandamos los avisos?

**Antes de irte, pide:** los PDF que tengan (lista de precios, catálogo), y **captura de las
últimas 20 preguntas de su WhatsApp**. Eso vale más que todo lo demás.

---

## 5. Planes y cómo cotizar

| Plan | Precio | Incluye | Para quién |
|---|---|---|---|
| **Básico** | $200 MXN/mes | 500,000 tokens | Negocio chico, 1 canal, pocos mensajes al día |
| **Pro** | $500 MXN/mes | 1,500,000 tokens | Varios canales o volumen alto |
| **Llave propia (BYOK)** | Cuota fija | El cliente pone su propia llave | Empresas con área de sistemas |

### Qué es un token, para explicárselo al cliente

**No uses la palabra "token" con el cliente.** Traduce:

> *"Su plan cubre alrededor de X conversaciones al mes. Si se pasa, le avisamos antes de que
> ocurra y le ofrecemos subir de plan."*

Referencia interna, **medida en pruebas reales** (agente dental con `glm-5.3-flash`, 27/08/2026):
cada intercambio (pregunta del paciente + respuesta del agente) consume ~890 tokens.

| Tipo de conversación | Tokens | Conversaciones con 500k |
|---|---|---|
| Corta (~4 intercambios) | ~3,600 | **140 al mes** |
| Media (~6 intercambios) | ~5,300 | **93 al mes** |
| Larga (~10 intercambios) | ~8,900 | **56 al mes** |

Ojo: el consumo por intercambio **crece dentro de una misma conversación**, porque el agente
recibe todo el historial en cada respuesta. Por eso una conversación larga cuesta más del doble
que dos cortas. Un negocio con conversaciones largas (cotizaciones, muchas dudas) rinde menos que
uno de preguntas sueltas.

Verifica el consumo real del cliente en su ficha durante el primer mes y ajusta el plan si hace
falta — es mejor subirlo a tiempo que dejarlo llegar al límite.

### El ciclo corta el día que se dio de alta

Si registras al cliente el día 12, su ciclo corre del 12 al 12. No es mes calendario. Díselo al
cliente para que no se confunda.

### Margen por plan (información interna — no se comparte con el cliente)

Con `glm-5.3-flash` a través de OpenCode GO, medido con consumo real:

| Plan | Precio | Costo real de IA | Margen |
|---|---|---|---|
| Básico | $200 MXN | ~$1.08 MXN | **$198.92 (99.5%)** |
| Pro | $500 MXN | ~$3.25 MXN | **$496.75 (99.3%)** |

El costo de IA es prácticamente despreciable frente al precio. Lo que el cliente paga es el
levantamiento, el mantenimiento y el soporte — no los tokens. **Nunca le desgloses el costo de IA
al cliente**: no vendemos tokens, vendemos que su negocio no pierda prospectos.

### Cómo justificar el precio

Usa la cifra del punto 6 del levantamiento:

> *"Usted me dijo que un paciente nuevo le deja $800 pesos. El plan cuesta $200 al mes. Con que
> le recupere **un solo paciente** que se hubiera ido por no contestar, ya lo pagó cuatro veces."*

---

## 6. Qué prometer y qué NO prometer

Esta sección evita cancelaciones. Léela dos veces.

### ✅ Sí puedes prometer
- Respuesta inmediata 24/7, todos los días
- El agente sabe lo que le enseñemos: precios, horarios, servicios, políticas
- Puede recibir fotos y notas de voz, y entenderlas
- Todas las conversaciones quedan guardadas y visibles
- El cliente puede tomar el control cuando quiera
- Su portal propio para ver todo
- Ajustes cuando los pida — nosotros los hacemos

### ❌ NO prometas
- **Que agenda solo en su sistema.** El agente puede recabar los datos y decir el horario
  disponible que le enseñemos, pero no escribe en la agenda del cliente salvo que se haya montado
  una integración específica. **Confírmalo antes de prometerlo.**
- **Que cobra o procesa pagos.** No lo hace.
- **Que nunca se equivoca.** Se puede equivocar. Por eso existe el botón de tomar control.
- **Que sabe algo que no le enseñamos.** Si no está en el brief, las FAQ o los documentos, no lo
  sabe. Y así lo queremos: preferimos que diga "déjeme confirmarlo" a que invente.
- **Fechas de conexión de Messenger o Instagram sin ver los accesos.** Meta pide permisos de
  administrador; si el cliente no sabe quién administra su página, eso se puede tardar días.

**Regla de oro:** es mejor prometer menos y sorprender. Un cliente al que le prometiste que
agendaba solo y no lo hace, cancela el primer mes.

---

## 7. Caso simulado completo

### Contexto

Edgar visita el **Consultorio Dental Sonrisas** en Guadalajara. Atiende la Dra. Karla Medina.
Tienen dos dentistas y una recepcionista. Reciben unos 40 mensajes al día por WhatsApp y unos 10
por Instagram.

### La conversación de venta

> **Edgar:** Doctora, antes de platicarle qué traigo, ¿me deja hacerle tres preguntas?
> ¿Quién contesta el WhatsApp del consultorio?
>
> **Dra. Karla:** Marisol, la recepcionista. Pero cuando está en ventanilla o cobrando, se le
> juntan.
>
> **Edgar:** ¿Y en la noche o el domingo?
>
> **Dra. Karla:** Pues... nadie. Marisol a veces contesta desde su casa, pero no es su obligación.
>
> **Edgar:** ¿Se le han ido pacientes por eso?
>
> **Dra. Karla:** Seguro. La semana pasada uno preguntó por blanqueamiento el sábado, le
> contestamos el lunes y ya se había ido a otro lado.
>
> **Edgar:** ¿Cuánto le deja un paciente nuevo de blanqueamiento?
>
> **Dra. Karla:** Unos $2,500 el tratamiento.
>
> **Edgar:** Entonces ese sábado le costó $2,500 pesos. Lo que traigo cuesta $200 al mes y contesta
> ese mensaje a los cinco segundos, un sábado a las once de la noche, con su precio, su horario y
> ofreciéndole cita. Y usted, cuando quiera, entra y toma la conversación usted misma.

**Qué hizo bien Edgar:** no dijo "inteligencia artificial", no habló de tecnología, hizo que la
doctora pusiera el número, y comparó ese número contra el precio.

### El levantamiento

Edgar llena los siete campos del brief:

- **Qué hace el negocio:** Consultorio dental general y estético en Guadalajara. Dos dentistas.
  Atención por cita, con espacio para urgencias.
- **Productos y servicios:** Limpieza dental $600. Resina $850. Blanqueamiento $2,500. Extracción
  desde $900. Ortodoncia: valoración $300, tratamiento cotizado tras revisión. Endodoncia: solo
  con valoración previa, no se cotiza por chat.
- **Público objetivo:** Adultos de 25 a 60 años de la zona de Providencia y Chapalita. Escriben
  informal, muchos preguntan primero el precio.
- **Información y políticas clave:** Lun–Vie 9:00–19:00, Sáb 9:00–14:00, Dom cerrado. Av. Pablo
  Neruda 2345, local 4, frente a la farmacia Guadalajara. Efectivo, tarjeta y transferencia.
  Meses sin intereses desde $3,000 con Visa/Mastercard. Cancelación con 4 horas de anticipación.
  Urgencias: se atienden el mismo día si hay espacio.
- **Objetivo principal del agente:** Que el paciente termine agendando una cita. Si no puede
  agendar, que deje su nombre y teléfono.
- **Debe hacer siempre:** Saludar por el nombre del consultorio. Dar el precio cuando lo tenga.
  Ofrecer cita al final de cada conversación. Pedir nombre y teléfono antes de cerrar.
- **No debe hacer nunca:** Dar diagnósticos médicos. Decir qué tratamiento necesita el paciente
  sin valoración. Cotizar ortodoncia o endodoncia por chat. Prometer resultados. Hablar de otros
  pacientes.

**Personalidad:** cercano y cálido, de usted, sin emojis excesivos, máximo uno por mensaje.
Respuestas cortas, de tres o cuatro líneas.

**FAQ que le dictó la doctora:**
- *¿Cuánto cuesta la limpieza?* → $600, dura unos 40 minutos, incluye revisión general.
- *¿Atienden niños?* → Sí, desde los 5 años.
- *¿Tienen estacionamiento?* → Hay estacionamiento público a media cuadra; en la calle también se
  puede.
- *¿Aceptan seguro?* → Damos factura para que la trámite con su aseguradora, pero no facturamos
  directo a la aseguradora.
- *Me duele mucho una muela* → Lamento escuchar eso. ¿Puede venir hoy? Tenemos espacio para
  urgencias. ¿Me comparte su nombre y teléfono?

**Documentos:** la doctora entrega el PDF de la lista de precios completa y el folleto de
ortodoncia.

**Canales:** WhatsApp por QR ese mismo día. Instagram queda pendiente porque quien administra la
cuenta es su sobrino y hay que esperar a que dé acceso.

**Plan:** Básico, $200 MXN, 500,000 tokens. Edgar registra al cliente el **26 de agosto**, así que
el ciclo corta el 26 de cada mes.

### Cómo queda funcionando

Sábado, 11:40 de la noche. Llega un mensaje al WhatsApp del consultorio:

> **Prospecto:** hola, cuanto sale el blanqueamiento?
>
> **Agente (a los 4 segundos):** ¡Hola! Gracias por escribir a Consultorio Dental Sonrisas 😊
> El blanqueamiento tiene un costo de $2,500 e incluye la valoración previa. El tratamiento se
> hace en una sola sesión de aproximadamente una hora.
> ¿Le gustaría que le aparte un espacio? Tenemos disponibilidad el lunes por la mañana.
>
> **Prospecto:** si, el lunes en la mañana estaria bien
>
> **Agente:** ¡Perfecto! Para apartarle el espacio, ¿me comparte su nombre completo y un teléfono
> de contacto?
>
> **Prospecto:** Rodrigo Salas, 33 1234 5678
>
> **Agente:** Gracias, Rodrigo. Ya quedó registrada su solicitud para el lunes por la mañana en
> Av. Pablo Neruda 2345, local 4, frente a la farmacia Guadalajara. Marisol le confirmará la hora
> exacta mañana a primera hora. ¡Que tenga excelente noche!

El lunes a las 9:00, Marisol abre el portal, ve la conversación, confirma la hora y cierra la
cita. **Ese paciente no se perdió.**

### Fíjate en tres cosas del ejemplo

1. **El agente no inventó una hora exacta.** Dijo "el lunes por la mañana" y dejó que Marisol
   confirmara. Así se configuró a propósito, porque el agente no escribe en la agenda.
2. **Pidió nombre y teléfono**, porque estaba en "debe hacer siempre".
3. **Si Rodrigo hubiera preguntado por ortodoncia**, el agente habría ofrecido la valoración de
   $300 sin cotizar el tratamiento, porque estaba en "no debe hacer nunca".

---

## 8. Objeciones frecuentes

**"¿Y si contesta mal y me quema con un paciente?"**
> Usted supervisa todo desde su portal y en cualquier momento toma el control con un botón. Además
> el agente está configurado para no dar diagnósticos ni inventar: si no sabe algo, dice que lo
> confirma. Y si algo no le gusta cómo lo contesta, me avisa y yo se lo ajusto.

**"Prefiero que conteste una persona."**
> Y así seguirá siendo cuando usted quiera. Esto no reemplaza a Marisol: le quita las 30 veces al
> día que contesta "¿cuánto cuesta la limpieza?" para que se dedique a los pacientes que ya están
> ahí. Y cubre las horas en que Marisol no está.

**"Está caro."**
> ¿Cuánto le deja un paciente nuevo? ... Con uno solo al mes que recupere, ya se pagó varias veces.
> ¿Cuántos cree que se le fueron el mes pasado por no contestar a tiempo?

**"Ya tengo un chatbot / lo intenté y no funcionó."**
> Los chatbots de menú ("marque 1 para horarios") molestan porque no entienden. Este responde con
> la información real de su consultorio, con sus precios y sus políticas. ¿Me deja mostrarle una
> conversación de prueba con sus propios datos?

**"Déjeme pensarlo."**
> Claro. ¿Le parece si mientras tanto lo dejo funcionando una semana sin costo con la información
> que ya me dio, y usted ve las conversaciones reales que entren? Si no le sirve, lo apagamos.

*(Confirma con Nicolás antes de ofrecer periodos de prueba.)*

---

## 9. Checklist de alta

Antes de decirle al cliente "ya quedó":

- [ ] Cliente registrado con su plan y cuota correctos
- [ ] Los 7 campos del brief llenos — **ninguno vacío**
- [ ] Personalidad y tono definidos
- [ ] Mínimo 10 preguntas frecuentes cargadas
- [ ] PDF de precios o catálogo subido
- [ ] Zona horaria correcta (`America/Mexico_City`)
- [ ] Al menos un canal conectado y probado
- [ ] **Probado en el playground con 10 preguntas reales**, incluidas 2 que NO debe contestar
- [ ] Portal del cliente activado, con su correo y contraseña
- [ ] Portal entregado al cliente y explicado el botón de tomar control
- [ ] Correo de avisos configurado

### La prueba de las 10 preguntas

No entregues un agente sin probarlo. Escribe en el playground las 10 preguntas más comunes del
negocio **y dos que no debe contestar**. Si falla en alguna, corrige el brief o agrega la FAQ antes
de entregar. Diez minutos aquí te ahorran una cancelación.

---

## 10. Después de la venta

- **Semana 1:** revisa las conversaciones cada dos días. Es cuando salen los huecos. Corrige.
- **Mes 1:** revisa el consumo de tokens en la ficha del cliente. Si va arriba del 80%, habla de
  subir de plan **antes** de que se agote.
- **Siempre:** cuando el cliente cambie precios, horarios o promociones, **te toca actualizarlo a
  ti**. Es parte de lo que paga. Un agente con precios viejos es peor que no tener agente.

---

## Resumen en cinco puntos

1. Vendemos respuestas inmediatas, no software ni "inteligencia artificial".
2. El dolor se encuentra preguntando cuánto vale un cliente nuevo y cuántos se han ido.
3. El agente vale lo que vale su levantamiento: los 7 campos del brief y las FAQ reales.
4. Nunca prometas que agenda solo, que cobra, o que nunca se equivoca.
5. Prueba con 10 preguntas antes de entregar, y da seguimiento la primera semana.
