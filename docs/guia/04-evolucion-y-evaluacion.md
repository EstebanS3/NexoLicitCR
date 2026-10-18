# Evolución, evaluación y defensa del proyecto

> **La siguiente oportunidad también se construye: con evidencia, aprendizaje y prioridades claras.**

Este capítulo propone cómo convertir la base implementada en un producto evaluado con empresas. Las fases, métricas, hipótesis comerciales y criterios que siguen son propuestas. No representan compromisos de entrega, ingresos, resultados de usuarios ni funciones ya disponibles.

**Entrega universitaria actual:** rige [alcance-academico.md](../alcance-academico.md), con muestra exploratoria obligatoria de 10–20 pares revisados manualmente. Las fases comerciales de este capítulo, la evaluación con empresas, 30–50 pares, Redis real y Docker son ampliaciones opcionales.

## 1. Del software que funciona al producto que ayuda

La versión documentada reúne un recorrido funcional, persistencia, ingesta, extracción documental y seguimiento. El próximo salto de calidad consiste en demostrar que una persona puede usar ese conjunto para revisar oportunidades con mayor claridad y continuidad.

Son preguntas diferentes: una prueba puede demostrar que un filtro conserva un estado; una sesión de uso puede revelar si alguien entiende ese filtro; una evaluación de relevancia puede mostrar si los resultados justifican abrir un expediente. La estrategia de validación debe atender las tres.

### Mapa de evidencia

| Capa | Evidencia que corresponde | Qué permite sostener |
|---|---|---|
| Contratos y reglas | Pruebas unitarias y regresiones con datos sintéticos. | Comportamientos específicos bajo entradas controladas. |
| Persistencia real | Pruebas de integración en una base aislada. | Transacciones, reinicios y almacenamiento en ese entorno. |
| Fuente pública | Muestras fechadas y procedencia de consultas. | Formatos y comportamientos observados en la muestra. |
| OCR | Transcripciones humanas y casos diversos. | Calidad de texto para el conjunto evaluado. |
| Relevancia | Pares empresa-concurso etiquetados por personas. | Precisión y cobertura dentro del universo evaluado. |
| Experiencia | Sesiones de tareas con empresas participantes. | Comprensión, errores y fricciones del recorrido. |
| Negocio | Pilotos y decisiones reales de adopción. | Utilidad percibida y disposición a pagar observadas. |

## 2. Estado de la evidencia disponible

El repositorio contiene pruebas automatizadas y reportes históricos. [planning-status.md](../planning-status.md) reúne entregas de varias fechas; sus cifras son acumulados históricos y sus pendientes deben leerse junto con los documentos posteriores. [ocr-review.md](../ocr-review.md) registra la revisión del 17 de octubre con pruebas controladas y una muestra documental real.

Ese reporte describe 152 casos sintéticos de extracción y recuperación de 520 frases esperadas, además de 16 anexos reales revisados, 14 PDF compatibles y 217 páginas recuperadas. Son resultados documentados en el repositorio. No son una medición repetida durante la redacción de esta guía ni acreditan exactitud total del OCR o del radar.

La fuente [source-validation.md](../source-validation.md) registra muestras para fechas, identificadores, secuencias y anexos. Sus observaciones orientan la configuración actual; no demuestran que todos los futuros expedientes mantengan el mismo formato. La aplicación conserva fechas originales, estados desconocidos y errores para representar esas incertidumbres.

La validación realizada específicamente para esta entrega documental se registra en el [índice de la documentación](../DOCUMENTACION.md). De este modo una persona puede distinguir comprobaciones nuevas de evidencia histórica.

## 3. Ruta de evolución propuesta

### Fase A: una experiencia confiable de principio a fin

Objetivo: que una empresa pueda confirmar su perfil, comprender su primer radar y retomar una decisión sin acompañamiento constante.

Trabajo propuesto: probar mensajes de estados vacíos, revisar instrucciones cuando SICOP no responde, observar la selección de varias especialidades y verificar que los usuarios entiendan el carácter preliminar de ciertos resultados. Conviene incluir una empresa con actividad clara y otra con oferta combinada para evitar diseñar solo para el caso más sencillo.

Criterio de salida propuesto: recorridos documentados, obstáculos reproducibles resueltos y una explicación comprensible de qué se consultó. El umbral de éxito debe acordarse antes de medir y conservarse junto con el tamaño de muestra.

### Fase B: calidad de relevancia medible

Objetivo: evaluar si las razones del radar ayudan a seleccionar concursos que merecen revisión.

Trabajo propuesto: formar un conjunto de 30 a 50 pares empresa-concurso como primera evaluación exploratoria, con perfiles confirmados y evidencia disponible. Dos personas deberían revisar los casos ambiguos y registrar el motivo de su decisión. Ese tamaño inicial sirve para descubrir errores, no para representar todo el mercado.

Criterio de salida propuesto: etiquetas, protocolo, resultados por actividad y análisis de falsos positivos y falsos negativos. No basta con aumentar el número de coincidencias: debe mejorar su utilidad para la tarea.

### Fase C: evidencia documental más completa

Objetivo: entender dónde falla la extracción y cómo afecta la evaluación posterior.

Trabajo propuesto: ampliar muestras con tablas, páginas giradas, imágenes degradadas, documentos mixtos y formatos todavía no compatibles. Crear referencias humanas para una selección de páginas y medir errores de palabras o caracteres. Analizar el costo de aumentar límites antes de modificarlos.

Criterio de salida propuesto: resultados segmentados por tipo de documento y una política explícita de revisión manual. Si se agregan nuevos formatos, deben tener contratos, límites de recursos y regresiones propias.

### Fase D: operación y crecimiento controlado

Objetivo: medir el sistema completo bajo cargas representativas y escenarios de falla.

Trabajo propuesto: ensayar Redis real, tiempos extremo a extremo, restauración de backups y recuperación ante interrupciones. Evaluar el costo de mantener corpus y anexos a lo largo del tiempo. El radar actual calcula el conjunto y después pagina; una mayor escala requiere medir consultas e índices antes de prometer tiempos.

Criterio de salida propuesto: presupuesto de latencia, consumo y recuperación con entorno, volumen y método documentados. La alta disponibilidad exige infraestructura adicional; un replica set de un nodo valida transacciones, pero no tolerancia a pérdida del nodo.

### Fase E: expansión funcional con fuente validada

Objetivo: incorporar capacidades nuevas cuya utilidad se pueda justificar.

Posibilidades: recomendaciones de ajuste al perfil basadas en feedback, avisos de eventos relevantes, colaboración entre personas y comparables de adjudicación por línea. Cada una necesita diseño e implementación propios. Para adjudicaciones, la condición previa es una fuente final validada; el historial actual contiene ofertas presentadas.

## 4. Medir lo que importa

| Indicador propuesto | Definición operativa | Cuidado de interpretación |
|---|---|---|
| Tiempo hasta la primera revisión fundamentada | Desde iniciar la configuración hasta abrir evidencia y registrar una decisión. | Medir familiaridad, pausas y ayuda recibida. |
| Finalización de perfil | Personas que confirman un perfil / personas que inician la tarea observada. | Registrar abandonos y motivos; no inferirlos. |
| Precisión de oportunidades mostradas | Casos mostrados etiquetados relevantes / casos mostrados evaluados. | Definir relevancia y umbral antes de medir. |
| Cobertura en un conjunto conocido | Relevantes recuperados / relevantes existentes en ese conjunto etiquetado. | No equivale a cobertura de todo SICOP. |
| Utilidad de la explicación | Personas que identifican correctamente el motivo de la tarjeta. | Una razón presente puede ser poco comprensible. |
| Integridad documental visible | Casos parciales reconocidos correctamente por la persona. | Recuperar texto no demuestra comprensión. |
| Recuperación operativa | Trabajos recuperados de un escenario de fallo según el protocolo. | Separar errores de fuente, proceso e infraestructura. |
| Continuidad del seguimiento | Decisiones conservadas y recuperables después de cambios del corpus. | Evaluar tanto persistencia como acceso en la UI. |

No se fijan porcentajes de éxito sin datos. El objetivo del piloto es producir una línea base y decidir qué mejorar con ella.

## 5. Hipótesis comercial y sostenibilidad

La hipótesis principal es que una empresa podría valorar un espacio que mantenga su perfil y organice la revisión de concursos. Para validarla, conviene observar uso recurrente y disposición a sostener el servicio, además de preguntar si la idea parece interesante.

| Opción a explorar | Valor propuesto | Dependencias por resolver |
|---|---|---|
| Instalación acompañada por empresa | Configuración inicial y autonomía de operación. | Soporte, actualizaciones y responsabilidad de infraestructura. |
| Servicio administrado por instalación | Mantenimiento, respaldo y asistencia recurrente. | Costos reales y operación segura de instancias separadas. |
| Piloto con una organización de apoyo | Aprendizaje con varias empresas bajo un protocolo común. | Consentimiento, aislamiento y tiempo de acompañamiento. |

Estas opciones son modelos de servicio posibles. La aplicación no incluye cobros, facturación, planes de suscripción ni provisión automática de empresas. Una propuesta SaaS multiempresa requeriría una evolución explícita del modelo de usuarios y aislamiento; `INSTALLATION_ID` por sí solo no la implementa.

Los costos que deben medirse incluyen base de datos, almacenamiento documental, cómputo OCR, transferencia, respaldo y soporte. La descarga acotada y la extracción por límites ayudan a controlar consumo, pero no sustituyen una estimación de costos con uso real.

## 6. Matriz de riesgos del producto

| Riesgo concreto | Tratamiento actual | Próxima comprobación propuesta |
|---|---|---|
| Confundir afinidad con elegibilidad | Razones y requisitos incompletos explícitos. | Observar interpretación en pruebas de uso. |
| Confundir ausencia de resultados con ausencia de demanda | Consulta acotada, estados y actividad. | Verificar comprensión del alcance y antigüedad. |
| Leer solo parte de un expediente | Estados parciales, límites y referencia a la fuente. | Evaluar documentos extensos y formatos nuevos. |
| Cambios o pausas en SICOP | Errores, reintentos, checkpoints y pausas por HTTP 429. | Revalidar contratos y muestras con fecha. |
| Pérdida de contexto por recálculo | Decisiones separadas de las coincidencias. | Ensayar cambios de perfil y de versión. |
| Crecimiento del corpus | Caché opcional y generación de invalidación. | Medir consultas y procesamiento extremo a extremo. |
| Expectativas comerciales superiores al alcance | Mensajes basados en capacidades observables. | Revisar materiales después de cada nueva versión. |

La matriz se concentra en límites presentes en el diseño. No pretende ser un análisis exhaustivo de cumplimiento normativo ni de seguridad de producción.

## 7. Defensa académica: de la experiencia a la persistencia

Una exposición sólida puede iniciar con una pregunta humana y terminar mostrando la decisión de base de datos que la sostiene.

| Pregunta para la defensa | Decisión técnica que permite responder |
|---|---|
| ¿Cómo conservamos cambios del contenido importado de un concurso? | Snapshots, hashes y versiones inmutables de concursos. |
| ¿Qué pasa si una escritura falla a la mitad? | Transacciones en la publicación de datos relacionados. |
| ¿Cómo evitamos duplicar por reintento? | Identidades deterministas, índices únicos y claves de idempotencia. |
| ¿Cómo evitamos que un worker viejo publique resultados? | Leases, heartbeats y tokens de fencing. |
| ¿Por qué una decisión no desaparece al cambiar el perfil? | Colección de decisiones independiente del resultado calculado. |
| ¿Qué pasa si Redis está caído? | MongoDB sigue como autoridad y existe fallback. |
| ¿Cómo se almacena y explica un anexo? | GridFS para binarios; metadatos y páginas en colecciones propias. |
| ¿Por qué usar revisión de catálogo? | Control de concurrencia e invalidación de resultados derivados. |

La demostración de estos conceptos debe apoyarse en ejemplos pequeños y datos sintéticos. Mostrar una transacción revertida o una decisión conservada comunica mejor su valor que enumerar tecnologías sin conectar su propósito.

## 8. Guion sugerido para una exposición de doce minutos

1. **Minutos 0-2: el problema.** Presentar la PYME ficticia, su oferta combinada y el esfuerzo de revisión. Explicar la promesa con una sola frase.
2. **Minutos 2-5: el recorrido.** Confirmar capacidades, mostrar el radar y abrir una razón con evidencia. Si la fuente está indisponible, mostrar un escenario preparado y etiquetado.
3. **Minutos 5-7: continuidad.** Registrar seguimiento y mostrar la actividad de una consulta o un ejemplo de resultado parcial.
4. **Minutos 7-10: la arquitectura.** Relacionar la experiencia con MongoDB, versiones, transacciones, jobs y GridFS. Explicar el papel opcional de Redis.
5. **Minutos 10-11: evidencia.** Mostrar pruebas y límites con su fecha, tipo de datos y entorno. Separar validaciones históricas de esta entrega.
6. **Minutos 11-12: la próxima etapa.** Proponer un piloto orientado a relevancia y comprensión. Cerrar con la continuidad que el producto ofrece a la empresa.

Los tiempos son una propuesta de presentación. No representan tiempos de uso medidos ni duración garantizada de consultas.

## 9. Preguntas difíciles que conviene responder bien

### ¿El proyecto usa inteligencia artificial generativa?

El descubrimiento y la afinidad actuales usan reglas y vocabulario determinista. La extracción incluye OCR. No hay un modelo de lenguaje externo encargado de clasificar empresas o decidir elegibilidad. Una futura incorporación requeriría justificar costo, privacidad, evaluación y manejo de texto no confiable.

### ¿Cubre todos los concursos?

La ingesta consulta ventanas acotadas por rubro y revisita activos según sus reglas. El corpus es el conjunto guardado en una instalación. La documentación no atribuye cobertura exhaustiva ni vigencia a todos los resultados.

### ¿Puede calcular el precio para ganar?

El importador histórico conserva ofertas presentadas con su procedencia. La fuente final de adjudicaciones por línea sigue pendiente. No existe una base validada para prometer un precio ganador o comparables adjudicados.

### ¿Está listo para cientos de empresas en una sola instancia?

El diseño actual es una empresa y una cuenta administradora por instalación, con base MongoDB exclusiva. Un despliegue para muchas empresas necesita una estrategia explícita de operación o una ampliación del modelo.

### ¿Por qué conservar estados parciales?

Porque un dato incompleto puede seguir siendo útil si su límite es visible. Un PDF largo puede aportar sus primeras páginas; una consulta puede conservar concursos ya importados. Ocultar esa condición llevaría a conclusiones que la evidencia no sostiene.

## 10. Cierre de la propuesta

NexoLicitCR propone que la primera revisión de compras públicas sea una tarea más organizada, explicable y continua. La base técnica ya permite recorrer esa idea: perfil, consulta, evidencia y decisión. La siguiente inversión debe demostrar su utilidad con empresas y convertir sus límites conocidos en prioridades medibles.

**La promesa es concreta: que una PYME llegue a su próxima revisión con mejores razones y con su trabajo anterior a mano.**

## Fuentes y continuidad

- [Estado histórico del proyecto](../planning-status.md).
- [Validación de la fuente](../source-validation.md).
- [Revisión de OCR y especialidades múltiples](../ocr-review.md).
- [Arquitectura existente](../architecture.md).
- [Pruebas automatizadas](../../tests/).
- [Índice y registro de esta entrega](../DOCUMENTACION.md).
