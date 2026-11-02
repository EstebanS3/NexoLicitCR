# Conclusiones

> *"Automatizamos la búsqueda. Tu PYME construye el futuro."*

Llegar a este punto del proyecto nos deja una satisfacción difícil de resumir. NexoLicitCR empezó como una pregunta sencilla —¿por qué una PYME costarricense tiene que dedicar horas a revisar SICOP para descubrir si un concurso le conviene?— y terminó convirtiéndose en un sistema completo, documentado, probado y pensado para resistir los problemas del mundo real. Este documento reúne lo que logramos, lo que nos costó y, sobre todo, lo que aprendimos en el camino.

---

## 1. Lo que construimos

Entregamos una aplicación funcional que acompaña a una pequeña o mediana empresa desde la descripción de sus capacidades hasta la decisión de participar o no en un concurso público:

| Capacidad | Resultado alcanzado |
|---|---|
| **Perfil y catálogo empresarial** | Sectores, varias especialidades y servicios revisables, con control de revisión que evita sobrescrituras concurrentes. |
| **Consulta acotada a SICOP** | Búsquedas explícitas por rubro y volumen, con pausas entre solicitudes y respeto por una fuente externa que no controlamos. |
| **Cola de trabajos durable** | Progreso, reintentos, checkpoints, cancelación y reanudación de consultas interrumpidas, todo persistido en MongoDB. |
| **Radar de afinidad explicable** | Cada sugerencia indica *por qué* aparece: términos, códigos, fragmentos y páginas del documento original. |
| **Evidencia documental** | Anexos íntegros en GridFS, verificados con SHA-256, y extracción de texto con pypdf y OCR en español como respaldo. |
| **Historial y seguimiento** | Versiones inmutables de cada concurso y decisiones humanas que sobreviven a cualquier recálculo. |
| **Seguridad por defecto** | Contraseñas con Argon2, sesiones persistentes, protección CSRF, TLS obligatorio y una base exclusiva por instalación. |

Detrás de esa lista hay **20 decisiones de arquitectura documentadas**, una batería de pruebas que cubre desde la ingesta hasta la recuperación de un worker que se cae a mitad de un trabajo, y una guía de instalación que funciona tanto en una laptop con Windows como en Docker con Atlas.

---

## 2. Lo que más nos enorgullece

**Haber dicho "no" a tiempo.** Habría sido tentador prometer que el sistema determina la elegibilidad legal de una empresa, o que cubre todo SICOP, o que usa inteligencia artificial para "entender" los carteles. Elegimos la honestidad: NexoLicitCR *sugiere* y *explica*; la verificación final ocurre en el expediente original. Esa decisión le da al producto algo más valioso que una funcionalidad llamativa: **confianza**.

**La trazabilidad.** Cualquier resultado del radar puede reconstruirse: sabemos qué versión del concurso, qué revisión del catálogo y qué versión de las reglas lo produjeron. Pocas veces en un curso se tiene la oportunidad de diseñar pensando en auditar el propio sistema.

**La resiliencia.** Probamos deliberadamente escenarios incómodos: procesos que mueren a mitad de una descarga, archivos huérfanos en GridFS, reinicios del servidor y caídas de Redis. Ver que el sistema se recupera solo, sin perder trabajo ni duplicarlo, fue uno de los momentos más gratificantes del proyecto.

---

## 3. Lo que aprendimos

Más allá de las tecnologías utilizadas, este proyecto nos enseñó conceptos que rara vez aparecen en los cursos introductorios y que, sin embargo, separan un prototipo de un sistema en el que alguien puede confiar.

### 3.1 Las transacciones de MongoDB no funcionan en un servidor standalone

Uno de los primeros golpes de realidad. MongoDB admite transacciones multi-documento, pero **solo sobre un replica set o un clúster**. Un `mongod` instalado "tal cual" las rechaza. Por eso el entorno local levanta un replica set de un solo nodo: no aporta alta disponibilidad, pero habilita el *oplog* que las transacciones necesitan. Aprendimos que una característica documentada puede tener requisitos de infraestructura que no son evidentes.

### 3.2 Una cola de trabajos no necesita Redis ni RabbitMQ

Antes del proyecto, asociábamos "trabajos en segundo plano" con un broker de mensajes dedicado. Descubrimos el patrón de **leases**: un worker reclama un trabajo con una operación atómica (`find_one_and_update`) y obtiene un "arriendo" con fecha de vencimiento. Si el proceso muere, el lease expira y otro worker retoma el trabajo desde su último *checkpoint*. Una sola base de datos resolvió persistencia, concurrencia y recuperación.

### 3.3 Idempotencia: ejecutar dos veces debe dar lo mismo que ejecutar una

En un sistema que reintenta, cualquier operación puede ocurrir más de una vez. Aprendimos a diseñar escrituras idempotentes: claves naturales como `cartelNo:cartelSeq`, *upserts* en lugar de inserciones ciegas y deduplicación de archivos por su hash. La pregunta "¿qué pasa si esto se ejecuta dos veces?" se volvió un hábito en cada revisión de código.

### 3.4 El hash de contenido como historial gratuito

En lugar de comparar campo por campo para saber si un concurso cambió, calculamos un **hash SHA-256 del contenido normalizado**. Si el hash coincide, no hay nada que guardar; si difiere, se crea una nueva versión inmutable. La misma idea sirve para deduplicar anexos en GridFS: dos archivos idénticos ocupan espacio una sola vez. Es el mismo principio que usa Git internamente, y entenderlo cambió nuestra forma de ver el almacenamiento.

### 3.5 Los índices TTL hacen limpieza sin código

Sesiones vencidas, tokens de inicio de sesión y contadores de intentos fallidos desaparecen solos gracias a los **índices TTL** de MongoDB, que eliminan documentos después de una fecha indicada. Sin tareas programadas, sin scripts de mantenimiento. Aprendimos que muchas veces la base de datos ya resuelve un problema que pensábamos programar a mano.

### 3.6 El dinero nunca se guarda como `float`

`0.1 + 0.2` no es `0.3` en punto flotante. Para importes de ofertas y adjudicaciones usamos `Decimal` serializado, junto con su moneda. Un error de redondeo en un monto de licitación no es un detalle técnico: es un problema de credibilidad.

### 3.7 Una fecha sin zona horaria es una fecha ambigua

SICOP publica fechas sin offset. Interpretarlas con la zona del servidor —que en la nube suele ser UTC— desplaza un cierre de recepción seis horas. Por eso la zona `America/Costa_Rica` es una configuración explícita y las fechas se almacenan normalizadas. Aprendimos que "la hora" siempre necesita un "¿de dónde?".

### 3.8 Hashear contraseñas no es lo mismo que cifrarlas, y no cualquier hash sirve

SHA-256 es excelente para verificar integridad, pero **pésimo para contraseñas**, precisamente porque es rápido. Argon2 es lento a propósito y consume memoria, lo que vuelve costosísimo un ataque por fuerza bruta con tarjetas gráficas. Elegir el algoritmo correcto para cada propósito fue una lección de criptografía aplicada.

### 3.9 CSRF: el navegador envía las cookies aunque el usuario no lo quiera

Una página maliciosa puede provocar que el navegador haga una solicitud a nuestra aplicación con la sesión del usuario incluida. La protección CSRF, junto con la validación estricta del origen (`PUBLIC_ORIGIN`), impide que una acción se ejecute sin intención real del usuario. Es una vulnerabilidad invisible hasta que se entiende cómo funcionan las cookies.

### 3.10 La caché debe ser desechable

Redis acelera el radar, pero el sistema funciona perfectamente sin él. Si Redis falla, la aplicación vuelve a MongoDB sin errores visibles. Además, las claves incluyen la versión del catálogo y del corpus, de modo que un cambio invalida automáticamente lo obsoleto. Aprendimos la frase que resume uno de los problemas más difíciles de la computación: *"solo hay dos cosas difíciles: invalidar la caché y nombrar cosas"*.

### 3.11 Reglas deterministas antes que IA generativa

Un motor de reglas versionado es explicable, reproducible y verificable con *benchmarks*. Un modelo generativo habría sido más vistoso, pero no podría garantizar que la misma entrada produzca la misma salida ni explicar con exactitud por qué recomendó algo. Aprendimos que la herramienta más sofisticada no siempre es la más adecuada para el problema.

### 3.12 La extracción de texto también tiene niveles de confianza

Un PDF puede contener texto real o solo imágenes escaneadas. Primero intentamos pypdf, que es rápido y exacto; si no hay texto, recurrimos a OCR con Tesseract en español, con límites de páginas, tamaño y tiempo. Y cuando la extracción es parcial, **lo decimos**: la ausencia de evidencia no es evidencia de ausencia.

### 3.13 Un monolito bien modularizado no es un pecado

Los microservicios están de moda, pero para una empresa por instalación habrían multiplicado la complejidad sin beneficio real. Un monolito con módulos de responsabilidad única, ejecutado en dos procesos (web y worker), nos dio aislamiento del trabajo pesado sin redes internas, contratos versionados ni despliegues coordinados. Aprendimos que la arquitectura se elige según el problema, no según la tendencia.

### 3.14 Documentar decisiones vale tanto como documentar código

Los *Architecture Decision Records* nos obligaron a escribir no solo *qué* elegimos, sino *por qué* y *qué descartamos*. Varias veces, releer un ADR evitó repetir una discusión ya resuelta. El código explica cómo funciona el sistema; los ADR explican por qué es así.

### 3.15 Un lockfile es una promesa de reproducibilidad

Con `uv` y `uv.lock`, cualquier integrante —o cualquier evaluador— instala exactamente las mismas versiones de cada dependencia. "En mi máquina funciona" dejó de ser una excusa. Sumado a `pip-audit`, también aprendimos que las dependencias son código ajeno que debe vigilarse.

---

## 4. Los desafíos que superamos

- **Una fuente externa impredecible.** SICOP es lento, cambia y a veces no responde. Diseñar todo para interrumpirse y reanudarse fue exigente, pero convirtió la fragilidad de la fuente en una fortaleza del sistema.
- **Concurrencia en algo tan simple como "guardar el perfil".** Dos pestañas abiertas pueden pisarse los cambios. El control por revisión monotónica nos enseñó que hasta un formulario necesita reglas de concurrencia.
- **Coordinación del equipo.** Ramas, *pull requests*, revisiones y documentación compartida exigieron disciplina. El historial del repositorio refleja ese trabajo colectivo.
- **Equilibrar ambición y plazo.** Distinguir lo obligatorio de las ampliaciones, y dejarlo por escrito en el alcance académico, nos permitió entregar algo sólido en lugar de algo inconcluso.

---

## 5. Mirando hacia adelante

NexoLicitCR tiene espacio para crecer: incorporar adjudicaciones finales desde una fuente validada, ampliar la cobertura de rubros, ofrecer alertas proactivas y, eventualmente, extraer el OCR como un servicio independiente si la carga lo exige. Gracias a los límites de módulo y a las decisiones documentadas, ese crecimiento no requerirá reescribir lo construido.

---

## 6. Reflexión final

Este proyecto nos enseñó que el software de calidad no se mide por la cantidad de funcionalidades, sino por cómo se comporta cuando las cosas salen mal: cuando un proceso se cae, cuando la fuente no responde, cuando dos personas editan al mismo tiempo o cuando un documento no se puede leer. Aprendimos a pensar en el usuario —una PYME que necesita oportunidades, no complejidad técnica— y a ser honestos sobre los límites de lo que construimos.

Nos llevamos mucho más que un repositorio. Nos llevamos criterio para tomar decisiones técnicas, la costumbre de preguntarnos "¿y si falla?" y la convicción de que la tecnología puede abrir puertas reales a las pequeñas empresas de Costa Rica.

**NexoLicitCR es, ante todo, la prueba de lo que aprendimos a construir juntos.**
