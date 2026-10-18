# Visión y propuesta de valor

> **Automatizamos la búsqueda. Tu PYME construye el futuro.**

NexoLicitCR convierte una pregunta cotidiana, «¿hay una oportunidad para lo que hacemos?», en un recorrido concreto: describir la empresa, confirmar sus capacidades, consultar concursos, entender las coincidencias y decidir qué seguir. La propuesta une información pública de SICOP con el contexto comercial de una PYME costarricense.

El producto no termina en una lista de resultados. Construye una memoria de trabajo: qué se consultó, qué cambió, de dónde proviene una coincidencia, qué documentos se pudieron leer y qué decisión tomó la empresa. Esa continuidad es la idea que vale la pena presentar: **menos búsqueda repetitiva y más atención a las oportunidades que merecen una revisión.**

Esta edición describe el código de la rama `dev` en el commit `4c91af4`, versión de paquete `0.1.0`. Fecha editorial: 18 de octubre de 2026, Costa Rica. Las afirmaciones de implementación provienen del repositorio; las propuestas comerciales y de evolución se identifican como tales. No se realizó una nueva investigación de mercado para este documento.

## 1. Una oportunidad empieza antes de presentar una oferta

Una empresa pequeña puede tener experiencia, personal y capacidad para atender una necesidad pública. Aun así, alguien debe identificar el concurso, leer sus líneas, abrir los anexos, verificar el cierre y decidir si justifica dedicar más tiempo. Cuando esa revisión se repite de forma manual, la información puede quedar repartida entre pestañas, descargas y notas.

Este es el problema de diseño que aborda NexoLicitCR. No se presenta como una medición estadística del comportamiento de todas las PYMES. Es una hipótesis de necesidad que puede validarse con empresas: **el costo de descubrir y ordenar información compite con el tiempo disponible para preparar una participación seria.**

El primer beneficio buscado es reducir esa fricción inicial. La preparación de ofertas, las decisiones comerciales y la verificación de requisitos continúan bajo responsabilidad de la empresa y de sus profesionales.

### Tres preguntas, un mismo espacio de trabajo

| Pregunta de la empresa | Respuesta del producto | Valor esperado |
|---|---|---|
| ¿Qué hay relacionado con lo que ofrecemos? | Perfil confirmado, catálogo y radar sobre el corpus consultado. | Concentrar la primera revisión. |
| ¿Por qué debería abrir este concurso? | Razones asociadas a términos, líneas, códigos o páginas disponibles. | Revisar evidencia concreta. |
| ¿Qué dejamos pendiente la última vez? | Decisiones persistentes, detalle y actividad de sincronización. | Continuar el trabajo con contexto. |

## 2. La propuesta en una frase

**NexoLicitCR conecta lo que tu empresa sabe hacer con oportunidades de compra pública que puede revisar con evidencia.**

El nombre expresa esa conexión. «Nexo» comunica vínculo; «Licit» sitúa la actividad; «CR» identifica el contexto costarricense. El símbolo existente combina una N modular con una dirección de avance. El azul profundo transmite solidez; el verde acompaña la conexión y el crecimiento.

La promesa comercial debe mantenerse vinculada a una acción observable: identificar, explicar, organizar y seguir. Expresiones como «ganá todas tus licitaciones», «nunca perdás una oportunidad» o «elegibilidad automática» excederían el alcance real del sistema.

### Presentación de treinta segundos

> Tu empresa conoce su oficio. NexoLicitCR ayuda a encontrar dónde ese oficio puede ser relevante en compras públicas. Confirmás lo que ofrecés, consultás SICOP y recibís un radar con razones para revisar cada oportunidad. Podés abrir la evidencia, guardar tu decisión y continuar después. La búsqueda se vuelve un proceso organizado, con información que conserva su contexto.

### Presentación de dos minutos

El punto de partida no es un código de clasificación: es la empresa. Una PYME puede trabajar en varias especialidades; por eso el perfil permite combinar hasta ocho selecciones de distintos sectores, revisar los servicios sugeridos y agregar sus propios términos. La configuración conserva la decisión humana sobre lo que la empresa realmente ofrece.

Con ese perfil, el radar compara títulos, líneas y texto documental disponible. Cuando una coincidencia aparece, la aplicación puede explicar qué término o código la produjo y, cuando existe, mostrar una referencia al documento y la página. El equipo obtiene un punto de partida para revisar el expediente.

Detrás de esa experiencia hay una infraestructura que conserva versiones, trabajos y decisiones. Una actualización puede detenerse o quedar parcial; el sistema registra el avance y permite reanudar en los casos implementados. Los documentos incompletos mantienen visible esa condición. La propuesta es una herramienta que ayuda a trabajar con información imperfecta sin ocultar sus límites.

## 3. Cuatro pilares del producto

### Conocer a la empresa

La actividad, las especialidades, los servicios, la cobertura y las exclusiones forman un perfil comercial explícito. Las sugerencias provienen de reglas y vocabulario editable. El catálogo manual complementa el perfil para representar productos o servicios específicos. La empresa revisa antes de confirmar.

### Encontrar motivos para revisar

El radar ordena y filtra información guardada. La afinidad tiene razones trazables; el valor de la tarjeta está en ayudar a decidir el próximo paso. La cobertura geográfica declarada no actúa actualmente como filtro automático y una puntuación elevada no valida todos los requisitos.

### Conservar el contexto

La información importada mantiene procedencia, snapshots y versiones. Los anexos admitidos se almacenan con hash y su texto se separa por página. Las decisiones de seguimiento tienen identidad propia y sobreviven a nuevos cálculos de afinidad.

### Trabajar con interrupciones

La ingesta se ejecuta mediante trabajos durables con estados, checkpoints y reintentos. HTTP 429 provoca pausas registradas. La aplicación puede mostrar progreso real y resultados parciales; no necesita simular que conoce el tamaño completo de un universo de concursos.

## 4. Alcance que ya se puede mostrar

| Capacidad | Implementación disponible | Cómo presentarla |
|---|---|---|
| Inicio de una instalación | Registro inicial de un administrador, sesión y configuración de empresa. | «Tu espacio de trabajo empieza con tu empresa». |
| Perfil flexible | 20 sectores, 66 opciones de especialidad y hasta 8 especialidades combinadas. | «Tu actividad puede abarcar más de un oficio». |
| Radar explicable | Reglas deterministas, filtros, razones y decisiones. | «Cada coincidencia tiene un motivo que podés revisar». |
| Consulta a SICOP | Trabajos acotados por rubro, reconsulta de activos y recuperación. | «Actualizá un alcance visible y seguí su avance». |
| Documentos | PDF, PNG y JPEG; extracción digital y OCR con límites configurables. | «La información útil también puede estar en los anexos». |
| Memoria comercial | Decisiones separadas del recálculo y versiones de concursos. | «Retomá lo que estabas evaluando». |
| Operación | MongoDB, CLI, Docker y Redis opcional. | «Una base técnica que se puede explicar y mantener». |

Los 20 sectores incluyen «Otra actividad». El vocabulario predefinido cubre 19 sectores comerciales y 65 especialidades predefinidas, más una opción personalizada; no representa una clasificación oficial de SICOP ni un catálogo de demanda vigente. Los conteos corresponden a la versión documentada.

## 5. Para quién empieza a tener sentido

El perfil inicial más razonable es una PYME que ya conoce sus productos o servicios y quiere organizar la búsqueda de concursos. Puede tratarse de una empresa de mantenimiento, tecnología, suministros, construcción u otra actividad contemplada por su perfil. Son segmentos propuestos para un piloto, no una cartera de clientes existente.

| Persona de diseño | Necesidad | Momento de valor |
|---|---|---|
| Persona propietaria que también vende | Decidir dónde dedicar una revisión inicial. | Entender por qué aparece un concurso. |
| Persona encargada comercial | Mantener continuidad en oportunidades pendientes. | Recuperar el seguimiento después de una actualización. |
| Persona que revisa documentación | Ubicar el origen de una coincidencia. | Abrir el detalle y la página asociada cuando estén disponibles. |
| Responsable técnico de la instalación | Poder diagnosticar y recuperar operaciones. | Consultar trabajos, errores y estado del procesamiento. |

Estas personas describen usos posibles. La implementación actual tiene una cuenta administradora por instalación y una empresa por base exclusiva. Los roles comerciales de la tabla no equivalen a permisos multiusuario implementados.

## 6. Una historia para presentar la demo

Imaginemos una PYME ficticia que instala redes informáticas y brinda soporte de equipos. La persona que la administra abre NexoLicitCR, registra el espacio y confirma esas dos especialidades. Revisa las sugerencias: deja cableado estructurado y mantenimiento informático; retira cualquier capacidad que no ofrece.

En el radar consulta una ventana acotada de SICOP con anexos habilitados. Mientras el trabajo avanza puede ver su actividad. Cuando aparecen resultados, abre uno y revisa las razones. Si una frase proviene de una página procesada, sigue esa evidencia; si el documento quedó parcial, sabe que debe continuar la lectura en la fuente original.

Finalmente marca el concurso «En seguimiento». Una nueva consulta puede cambiar el contenido o la afinidad; su decisión permanece. El cierre de la demostración no es un puntaje espectacular: es la capacidad de volver mañana y continuar una evaluación con contexto.

La empresa y el recorrido anterior son ilustrativos. La demo debe usar una base sintética separada o los datos que la persona haya autorizado para una instalación real. No se prometen coincidencias específicas ni concursos abiertos antes de comprobarlos.

## 7. Ventaja defendible desde el diseño

El posicionamiento propuesto combina cinco atributos: entrada desde la actividad de la empresa, evidencia para explicar resultados, soporte documental, persistencia de decisiones y continuidad operativa. Esta combinación describe el producto; no es una comparación comercial validada contra competidores.

| Alternativa de trabajo | NexoLicitCR aporta | Condición necesaria |
|---|---|---|
| Buscar y recordar manualmente | Perfil reutilizable y seguimiento persistente. | Confirmar capacidades y registrar decisiones. |
| Conservar solo una lista de enlaces | Detalle normalizado, versiones y referencias de evidencia. | Que la fuente y los anexos puedan consultarse. |
| Leer todos los documentos desde cero | Texto disponible por página y coincidencias asociadas. | Revisar integridad, límites y calidad del OCR. |
| Depender de una actualización en una sola sesión | Jobs persistentes y recuperación según estado. | Worker activo y MongoDB disponible. |

El trabajo profundo de evaluar requisitos sigue existiendo. La oportunidad comercial del proyecto está en mejorar el camino que lleva a esa evaluación y en conservar su contexto.

## 8. Una base de datos que participa en la propuesta de valor

Para un proyecto de Bases de Datos Avanzadas, MongoDB no aparece como un simple lugar donde guardar formularios. El dominio exige documentos heterogéneos, snapshots históricos, escrituras coordinadas, índices de unicidad, expiración de sesiones y almacenamiento de archivos. Redis agrega una capa opcional de aceleración cuyo fallo no elimina la información principal.

La arquitectura permite defender decisiones concretas: por qué un catálogo puede tener ítems embebidos, por qué una decisión necesita una colección independiente, por qué un snapshot y su versión deben publicarse juntos y por qué un archivo binario requiere un ciclo de vida distinto del texto extraído. El [capítulo técnico](02-arquitectura-y-datos.md) desarrolla esas relaciones.

## 9. Lenguaje recomendado para comunicar la idea

| Mensaje | Sustento actual |
|---|---|
| «Encontrá razones para revisar una oportunidad». | Matching con evidencia por término/código y contenido disponible. |
| «Tu empresa puede ofrecer más de una especialidad». | Selecciones múltiples con confirmación explícita. |
| «Conservá el contexto de cada decisión». | Decisiones persistentes independientes del radar. |
| «Sabé qué se pudo consultar y qué sigue pendiente». | Jobs, errores y procesamiento parcial visibles. |
| «De información dispersa a una revisión organizada». | Integración de perfil, concursos, anexos y seguimiento. |

La comunicación debe evitar cifras de ahorro, ingresos, exactitud o probabilidad de ganar hasta contar con mediciones adecuadas. En el [capítulo de evolución](04-evolucion-y-evaluacion.md) se propone cómo producir esa evidencia.

## 10. Fuentes de este capítulo

Base de la propuesta: [README](../../README.md), [contratos](../../src/nexolicitcr/models.py), [sectores](../../src/nexolicitcr/sectors.py), [matching](../../src/nexolicitcr/matching.py), [descubrimiento guiado](../guided-discovery.md) y [revisión de OCR](../ocr-review.md). Los reportes históricos conservan su fecha y alcance; esta edición no sustituye una revalidación de SICOP.
