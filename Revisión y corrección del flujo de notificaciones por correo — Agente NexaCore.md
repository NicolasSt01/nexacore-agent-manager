# Revisión y corrección del flujo de notificaciones por correo — Agente NexaCore

## Objetivo

Revisar, diagnosticar y corregir el flujo mediante el cual el Agente NexaCore debe enviar automáticamente un correo electrónico al equipo interno cuando una conversación con un prospecto haya generado suficiente información para ser considerada una **solicitud de valoración, cotización o seguimiento comercial**.

Durante una prueba reciente, el agente indicó al prospecto que la información había quedado registrada y enviada al equipo, pero **no se recibió el correo esperado**.

Se requiere revisar todo el flujo técnico de extremo a extremo y garantizar que:

1. El agente identifique correctamente cuándo debe generar una notificación.
2. Se ejecute realmente la función/acción responsable de enviar el correo.
3. El sistema pueda detectar y registrar errores de envío.
4. El correo sea enviado a todos los destinatarios configurados.
5. El contenido del correo incluya un resumen completo y útil del proyecto.
6. El agente nunca afirme que una notificación fue enviada si técnicamente la acción no se ejecutó o falló.
7. El sistema conserve suficiente información de diagnóstico para detectar fácilmente futuros errores.

---

# 1. Revisar primero el flujo actual

Revisar el código completo relacionado con:

- Generación de solicitudes comerciales.
- Agendamiento o solicitudes de citas.
- Funciones/tools/actions disponibles para el agente.
- Envío de correos.
- Configuración SMTP/API de correo.
- Destinatarios configurados.
- Plantillas de correo.
- Manejo de errores.
- Logs.
- Webhooks, colas o jobs, si existen.
- Procesos asíncronos relacionados con el envío.
- Integraciones externas utilizadas para correo.

Determinar exactamente:

**¿Qué sucede técnicamente cuando el agente decide que debe enviar una solicitud al equipo?**

Documentar el flujo actual paso por paso.

Ejemplo:

`WhatsApp → Agente IA → Tool/Function → Backend → Generación de correo → SMTP/API → Proveedor de correo → Destinatarios`

Identificar en qué punto podría estar fallando.

---

# 2. Verificar que la acción de envío realmente exista y sea ejecutada

Confirmar que el agente tenga disponible una función, tool, endpoint o mecanismo real para enviar la información al equipo.

No debe existir únicamente una instrucción dentro del prompt como:

> "Envía un correo al equipo."

Debe existir una acción técnica real que pueda ejecutarse.

Por ejemplo, conceptualmente:

`send_internal_lead_notification`

El nombre real puede ser diferente; lo importante es que exista una acción funcional.

Verificar:

- Que el agente tenga acceso a dicha acción.
- Que la acción esté correctamente registrada.
- Que el esquema de parámetros sea válido.
- Que el agente pueda invocarla.
- Que los parámetros requeridos estén llegando correctamente.
- Que la acción realmente se ejecute en backend.
- Que el backend devuelva un resultado de éxito o error.
- Que el agente reciba ese resultado.

---

# 3. Revisar los logs de la conversación de prueba

Utilizar específicamente la conversación de prueba realizada por Nicolás Salas.

Buscar el momento en que el agente respondió aproximadamente:

> "Listo, Nicolás, con esos datos quedo en registrar todo..."

y posteriormente indicó que la solicitud había sido enviada al equipo.

Determinar:

### A. ¿El agente intentó ejecutar la acción?

Si NO:

- Revisar las instrucciones del agente.
- Revisar las condiciones que determinan cuándo debe enviarse el correo.
- Revisar si el agente no entendió que debía ejecutar la función.

Si SÍ:

Continuar con:

### B. ¿La función fue ejecutada correctamente?

Verificar:

- Timestamp.
- Payload enviado.
- Parámetros.
- Identificador de conversación.
- Identificador del prospecto.
- Resultado de la función.
- Código de respuesta.
- Error, si existió.

### C. ¿El backend intentó enviar el correo?

Si NO, identificar por qué.

### D. ¿El proveedor de correo aceptó el mensaje?

Si NO, obtener el error exacto.

### E. ¿El correo fue aceptado pero posteriormente no entregado?

Revisar logs/eventos del proveedor de correo.

---

# 4. No considerar "acción realizada" únicamente porque el agente lo dijo

Este punto es MUY importante.

El agente no debe poder afirmar:

> "El correo ya fue enviado."

simplemente porque su prompt le indicó que debía hacerlo.

La confirmación debe depender del resultado real de la función.

El flujo debería funcionar conceptualmente así:

### Éxito

`Agente → send_email() → Backend → Email Provider → SUCCESS`

Entonces el agente puede comunicar:

> "Perfecto, ya envié la información al equipo."

### Error

`Agente → send_email() → Backend → ERROR`

Entonces el agente debe comunicar algo como:

> "Tu solicitud quedó registrada, pero tuvimos un inconveniente al enviar la notificación al equipo. Voy a dejar la información registrada para que puedan darle seguimiento."

Nunca debe afirmar que el correo fue enviado si la función devolvió error.

---

# 5. Revisar configuración de correo

Verificar completamente la configuración utilizada para enviar los correos.

Revisar:

- SMTP host, si aplica.
- SMTP port.
- Encryption/TLS.
- Usuario.
- Credenciales.
- API key, si aplica.
- From address.
- Reply-To.
- Destinatarios.
- CC.
- BCC.
- Dominio remitente.
- Verificación del dominio.
- SPF.
- DKIM.
- DMARC.
- Límites de envío.
- Restricciones del proveedor.
- Sandbox/test mode, si existe.
- Configuración de producción vs desarrollo.

No modificar credenciales directamente en código fuente.

Verificar que las variables de entorno utilizadas en producción sean las correctas.

---

# 6. Verificar los destinatarios

El sistema debe permitir configurar claramente quién recibe estas notificaciones.

La lista debe ser configurable y no estar enterrada dentro de lógica difícil de modificar.

Conceptualmente:

`lead_notification_recipients`

Debe soportar múltiples destinatarios.

Ejemplo:

- Responsable comercial.
- Responsable de desarrollo.
- Dirección.
- Otro integrante involucrado.

Verificar además que:

- Todos los destinatarios estén recibiendo el mensaje.
- No se esté enviando accidentalmente únicamente al primer correo.
- Los correos estén correctamente separados.
- No existan errores de formato.
- No se esté enviando el correo al prospecto por error.

---

# 7. Crear una plantilla específica para solicitudes de valoración/cotización

No utilizar un correo genérico como:

> "Nuevo cliente interesado."

El objetivo del correo es que el equipo pueda leerlo y **entender el proyecto sin tener que volver a iniciar la conversación desde cero**.

El correo debe funcionar como un **Brief Comercial / Brief de Cotización generado automáticamente por IA**.

---

# 8. Plantilla esperada

El correo debe tener una estructura similar a la siguiente:

---

## Asunto

**Nueva solicitud de cotización — [Tipo de proyecto] — [Nombre del prospecto]**

Ejemplo:

**Nueva solicitud de cotización — Tienda en línea — Nicolás Salas**

---

## Encabezado

**Nueva solicitud comercial**

Se ha recibido una nueva solicitud de valoración/cotización a través del Agente NexaCore.

---

## Información del prospecto

**Nombre:** Nicolás Salas  
**WhatsApp:** [número obtenido automáticamente de la conversación]  
**Correo:** sistemas@crosspoint.com.mx  
**Empresa:** [si fue proporcionada]  
**Fecha de contacto:** [fecha y hora]  
**Canal:** WhatsApp

IMPORTANTE:

Si el número de WhatsApp está disponible automáticamente por la plataforma, utilizar ese número.

**No pedir nuevamente al prospecto un número que el sistema ya conoce.**

---

# 9. Resumen ejecutivo del proyecto

Debe existir una sección visible llamada:

### Resumen del proyecto

Aquí la IA debe generar un resumen en lenguaje natural de aproximadamente 1–3 párrafos.

Ejemplo:

> El cliente requiere una tienda en línea para una boutique, cuyo objetivo es mostrar sus productos y permitir que sus clientas realicen compras directamente desde el sitio web. Inicialmente contempla aproximadamente 30 productos y ya cuenta con fotografías y logotipo.
>
> El sistema deberá permitir pagos en línea y generar una notificación vía WhatsApp cuando un pedido haya sido pagado. También desea permitir pedidos directamente por WhatsApp para coordinar pagos de manera manual. La operación contempla tanto envíos a domicilio como recolección en tienda.

El resumen debe ser generado con base exclusivamente en la información obtenida durante la conversación.

No inventar información.

---

# 10. Objetivo del proyecto

Incluir:

### Objetivo

¿Qué busca conseguir el cliente?

Ejemplo:

> Tener presencia digital para su boutique, mostrar sus productos y permitir la venta directa en línea.

Si el objetivo no fue identificado claramente, indicarlo:

> Pendiente de confirmar.

---

# 11. Tipo de proyecto

Identificar automáticamente la categoría correspondiente.

Ejemplos:

- Página web corporativa.
- Landing page.
- Tienda en línea.
- Sistema administrativo.
- Sistema POS.
- Aplicación móvil.
- Automatización.
- Integración.
- CRM.
- ERP.
- Sistema personalizado.
- Red/infraestructura.
- Otro.

Ejemplo:

**Tipo:** Tienda en línea / E-commerce

---

# 12. Alcance identificado

Crear una sección:

### Alcance y funcionalidades identificadas

Ejemplo:

- Sitio web para boutique.
- Catálogo de productos.
- Aproximadamente 30 productos iniciales.
- Carrito de compras.
- Compra en línea.
- Pagos con tarjeta / pasarela de pago.
- Notificación de pedidos pagados vía WhatsApp.
- Pedidos mediante WhatsApp.
- Envíos a domicilio.
- Recolección en tienda.
- Administración de productos.
- Administración de pedidos.

IMPORTANTE:

Separar lo que el cliente **confirmó** de lo que solamente fue **detectado como posible requerimiento**.

---

# 13. Información de productos o contenido

Incluir:

### Contenido e insumos

Ejemplo:

- Logotipo: Disponible.
- Fotografías: Disponibles.
- Textos: [Disponible / No confirmado].
- Catálogo: [Disponible / No confirmado].
- Precios: [Disponible / No confirmado].
- Información de productos: [Disponible / No confirmado].

No asumir que algo está disponible si el cliente no lo confirmó.

---

# 14. Pagos

Si aplica, incluir:

### Pagos

- ¿Desea pagos en línea?: Sí.
- Método de pago: [confirmado / pendiente].
- Pasarela específica: [si fue mencionada].
- ¿Pedidos por WhatsApp?: Sí.
- ¿Pago manual mediante WhatsApp?: Sí.

Si no se especificó una pasarela concreta:

**Pasarela de pago: Pendiente de definir.**

---

# 15. Envíos y logística

Si aplica:

### Entregas y envíos

- Envío a domicilio: Sí.
- Recolección en tienda: Sí.
- Paquetería: Pendiente.
- Cálculo de costo de envío: Pendiente.
- Cobertura geográfica: Pendiente.
- Reglas de envío: Pendiente.

---

# 16. Usuarios y administración

Cuando corresponda, identificar:

- Administrador.
- Empleados.
- Clientes.
- Vendedores.
- Otros perfiles.

Y determinar qué funciones tendrá cada uno si fueron mencionadas.

---

# 17. Integraciones

Crear:

### Integraciones

Mostrar las integraciones confirmadas.

Ejemplo:

- WhatsApp.
- Pasarela de pagos.
- Google Calendar.
- Correo electrónico.
- ERP existente.
- CRM.
- API externa.

Si no hay integraciones:

**No se identificaron integraciones adicionales durante el levantamiento.**

---

# 18. Diseño e identidad

Incluir:

### Diseño

- Logotipo: Sí.
- Fotografías: Sí.
- Identidad corporativa: [confirmada / pendiente].
- Referencias visuales: [si existen].
- Estilo deseado: [si fue mencionado].

---

# 19. Infraestructura existente

Si aplica:

### Infraestructura actual

- Dominio: [Sí / No / Pendiente].
- Hosting: [Sí / No / Pendiente].
- Sitio actual: [URL si fue proporcionada].
- Sistema existente: [información].
- Base de datos existente: [información].

No solicitar nuevamente información que ya esté disponible.

---

# 20. Fecha y tiempos

Crear:

### Tiempo

**Fecha objetivo:** [fecha]

**Motivo de la fecha:** [evento/lanzamiento/urgencia, si fue mencionado]

**Prioridad:** [Normal / Alta / Urgente]

Si no existe fecha:

**Fecha objetivo: No definida.**

---

# 21. Presupuesto

Crear:

### Presupuesto

**Rango indicado por el cliente:** [cantidad]

Si el cliente no quiso proporcionarlo:

**Presupuesto: Pendiente de revisar durante valoración.**

Nunca inventar un presupuesto.

---

# 22. Prioridades

Separar los requerimientos:

### Prioridades

**Indispensable**
- ...

**Importante**
- ...

**Deseable**
- ...

**Futuro**
- ...

Si no existe suficiente información para clasificarlos, dejarlo como pendiente.

---

# 23. Requerimientos implícitos / puntos a confirmar

Esta sección es MUY importante.

La IA debe analizar el proyecto y detectar aspectos que podrían afectar el alcance, pero que todavía no fueron confirmados.

Ejemplo para la boutique:

### Puntos a confirmar

- Variantes de productos: tallas, colores, etc.
- Control de inventario.
- Descuento automático de inventario al realizar una compra.
- Número de sucursales.
- Pasarela de pago.
- Métodos de pago disponibles.
- Empresa de paquetería.
- Cálculo de tarifas de envío.
- Cobertura de envíos.
- Políticas de cambios y devoluciones.
- Cupones y promociones.
- Registro de clientes.
- Facturación.
- Dominio y hosting.
- Administración de productos.
- Reportes de ventas.

La IA debe generar esta sección de manera dinámica según el proyecto.

---

# 24. Complejidad preliminar

Agregar una valoración interna:

### Complejidad preliminar

- Baja.
- Media.
- Alta.
- Muy alta.

Y una breve explicación.

Ejemplo:

**Media**

> El proyecto requiere e-commerce, pagos en línea, gestión de pedidos, integración con WhatsApp y configuración de diferentes métodos de entrega.

Esta valoración es únicamente orientativa y no sustituye la revisión técnica.

---

# 25. Pendientes

Agregar una sección:

### Información pendiente

Aquí deben aparecer únicamente los datos que realmente faltan para poder realizar una cotización con mayor precisión.

Ejemplo:

- Definir pasarela de pago.
- Confirmar manejo de inventario.
- Definir paquetería.
- Confirmar variantes de productos.
- Confirmar dominio y hosting.

---

# 26. Cita / valoración

Si el prospecto solicitó una sesión:

### Sesión solicitada

**Fecha:** [fecha]  
**Hora:** [hora]  
**Estado:** Pendiente de confirmación / Confirmada / Rechazada

IMPORTANTE:

No indicar "Confirmada" si el sistema únicamente registró una solicitud.

---

# 27. Conversación original

El correo debe incluir una referencia a la conversación original.

Idealmente:

**Ver conversación completa → [link interno]**

Si existe un identificador de conversación, incluirlo internamente para facilitar la búsqueda.

Ejemplo:

`Conversation ID: XXXXX`

Esto permitirá que el equipo pueda revisar rápidamente el contexto si necesita hacerlo.

---

# 28. Información técnica interna

Al final del correo, incluir una sección que no necesariamente tenga que mostrarse al cliente:

### Información interna

- Lead ID.
- Conversation ID.
- Fecha/hora de creación.
- Canal.
- Agente utilizado.
- Estado del lead.
- ID de la solicitud.
- Estado del correo.
- ID del mensaje del proveedor de correo, si existe.

Esto facilitará muchísimo el diagnóstico de errores.

---

# 29. Diseño del correo

El correo debe ser visualmente limpio y profesional.

Debe poder leerse fácilmente desde:

- Computadora.
- Gmail.
- Outlook.
- Teléfono móvil.

Recomendación:

- Encabezado con identidad NexaCore.
- Títulos claramente diferenciados.
- Información importante destacada.
- Listas en lugar de bloques enormes de texto.
- Buena separación entre secciones.
- No utilizar excesivamente emojis.
- No convertir el correo en una transcripción de WhatsApp.

El objetivo es que un miembro del equipo pueda abrirlo y comprender el proyecto en aproximadamente 1–2 minutos.

---

# 30. Manejo de errores

Implementar manejo explícito de errores.

Si el envío falla:

1. Registrar el error completo.
2. Registrar timestamp.
3. Registrar destinatarios.
4. Registrar payload.
5. Registrar respuesta del proveedor.
6. Registrar código de error.
7. Marcar la notificación como `failed`.
8. Permitir reintento.
9. Evitar que el agente diga que el correo fue enviado.

Si el sistema utiliza colas/jobs:

- Registrar el estado del job.
- Registrar intentos.
- Registrar último error.
- Implementar retry cuando sea apropiado.
- Evitar duplicados.

---

# 31. Estados recomendados

La notificación debería tener estados claros, por ejemplo:

`pending`

`processing`

`sent`

`failed`

`retrying`

De esta manera podremos saber exactamente qué ocurrió.

Ejemplo:

**Lead:** 12345  
**Email notification:** `sent`

o:

**Lead:** 12345  
**Email notification:** `failed`  
**Error:** SMTP authentication failed.

---

# 32. Evitar correos duplicados

Implementar algún mecanismo de idempotencia.

Si el agente intenta enviar nuevamente la misma solicitud debido a un retry, timeout o repetición de la conversación, evitar enviar múltiples correos idénticos accidentalmente.

Por ejemplo, utilizar:

- Lead ID.
- Conversation ID.
- Event ID.

como identificador único de la notificación.

---

# 33. Confirmación de funcionamiento

Una vez corregido el sistema, realizar pruebas completas.

### Prueba 1 — Solicitud normal

Simular un prospecto que proporciona suficiente información.

Resultado esperado:

- Se ejecuta la función.
- Se crea la solicitud.
- Se genera el brief.
- Se envía el correo.
- Se registra `sent`.

### Prueba 2 — Error de correo

Simular una falla del proveedor.

Resultado esperado:

- El sistema registra `failed`.
- El error queda almacenado.
- El agente NO afirma que el correo fue enviado.

### Prueba 3 — Múltiples destinatarios

Verificar que todos los destinatarios configurados reciban el correo.

### Prueba 4 — Datos faltantes

Verificar que el correo indique claramente:

`Pendiente de confirmar`

en lugar de inventar información.

### Prueba 5 — Reintento

Forzar un fallo temporal y comprobar que el sistema pueda reintentar sin crear correos duplicados.

### Prueba 6 — Información disponible

Verificar que si el número de WhatsApp ya está disponible, el agente no vuelva a preguntarlo innecesariamente.

---

# 34. Resultado esperado

Al finalizar esta tarea, debemos poder hacer una conversación de prueba completa con el agente y obtener automáticamente:

**Prospecto → Conversación → Levantamiento → Brief → Notificación → Correo recibido**

El correo debe permitir que el equipo de NexaCore comprenda el proyecto y tenga una primera base suficientemente sólida para preparar una cotización o realizar una sesión de valoración.

Además, debe quedar completamente claro mediante logs si una notificación:

- Fue creada.
- Fue procesada.
- Fue enviada.
- Falló.
- Fue reintentada.
- Fue entregada al proveedor.

---

# Criterio de aceptación principal

La funcionalidad NO se considera terminada simplemente porque el agente diga:

> "Ya envié la información al equipo."

Se considera terminada cuando:

**1. El agente ejecuta realmente la acción.**

**2. El backend procesa correctamente la solicitud.**

**3. El proveedor de correo acepta el mensaje.**

**4. Los destinatarios configurados reciben el correo.**

**5. El sistema registra el resultado.**

**6. El correo contiene un Brief Comercial completo, estructurado y útil para cotización.**

**7. Ante cualquier error, el sistema lo registra y el agente comunica correctamente que la acción no pudo completarse.**