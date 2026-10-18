# Propuesta: la empresa cuenta qué hace, NexoLicitCR orienta su búsqueda

**Alcance vigente desde el 18/10/2026:** [entrega universitaria](alcance-academico.md). El feedback obligatorio guarda decisiones y notas; las propuestas automáticas de ajuste y la evaluación con empresas son opcionales. El recorrido y los ajustes previos de este documento conservan su contexto histórico.

Estado: alcance aprobado y primera demo implementada en `/discover`. Incluye actividad libre, sugerencias deterministas editables, confirmación con control de concurrencia, perfil persistente, oportunidades explicadas y actualización SICOP con alcance confirmado. Se conserva el catálogo y el radar existentes. Los ajustes sugeridos a partir del feedback y la evaluación humana siguen pendientes.

## Punto de entrada

La primera pantalla pregunta **«¿A qué se dedica tu empresa?»**, con un ejemplo breve y un campo de lenguaje natural. No exige palabras clave, rubros SICOP ni códigos. Ejemplo: «Instalamos y mantenemos redes informáticas para oficinas en San José y Heredia».

El sistema devuelve un **borrador editable**, nunca una clasificación confirmada automáticamente. Si la descripción es ambigua («servicios generales»), hace una pregunta concreta antes de buscar. La empresa puede continuar con un perfil incompleto; se muestra qué información falta.

## Recorrido guiado

1. **Contanos qué hacés.** Actividad y productos/servicios principales en palabras de la empresa. Ejemplos opcionales; no encerrar al usuario en una lista de sectores.
2. **Afinemos tu alcance.** Confirmar 3–8 capacidades sugeridas, lo que no ofrece y dónde puede atender. Preguntar solo por información aún desconocida. Volumen, certificaciones o presupuesto son opcionales, no inferidos de la actividad.
3. **Así vamos a buscar.** Resumen legible de servicios, términos sugeridos, exclusiones y categorías a consultar. La empresa corrige y confirma antes de guardar. Los códigos de clasificación quedan en configuración avanzada y requieren sistema/procedencia verificados.
4. **Encontramos opciones para revisar.** Buscar primero en los concursos guardados; si hace falta información actual, encolar una actualización. Explicar el estado: «Preparando tu búsqueda», «Consultando SICOP», «12 concursos revisados», «Actualización parcial». Mostrar siempre la última actualización; no presentar un porcentaje cuyo total no conocemos.
5. **Ayudanos a afinar.** Cada concurso permite «Me interesa», «No es lo que hacemos» y «Revisar después», con motivo opcional. Ese feedback propone ajustes al perfil; no modifica silenciosamente la actividad ni las exclusiones.

## Resultado que ayuda a decidir

Encabezado: **«Oportunidades para tu empresa»**. Cada tarjeta responde:

- Por qué aparece: «Menciona mantenimiento de redes, uno de tus servicios» y fragmento con fuente/página.
- Qué falta revisar: pliego incompleto, certificación mencionada, ubicación o fecha sin confirmar.
- Cierre y vigencia: cerrar/cancelar según evidencia; nunca mostrar abierto un plazo vencido.
- Siguiente acción: revisar detalle, guardar o descartar.

El puntaje numérico deja de ser el protagonista. Se muestran razones y pendientes; cualquier nivel de afinidad debe tener una definición explicable y validarse con casos humanos. No equivale a elegibilidad, probabilidad de ganar ni precio recomendado. Si faltan resultados, ofrecer ampliar cobertura o servicios, siempre con confirmación, y distinguir «sin coincidencias» de «no pudimos actualizar SICOP».

## Búsqueda y arquitectura

Separar **descubrimiento de concursos** de **evaluación para la empresa**. La actividad orienta categorías y prioridades de ingesta con límites explícitos; no asumir que SICOP admite un filtro semántico por actividad. No afirmar cobertura total cuando solo se consultó una ventana acotada. Permitir consultar todos los rubros cuando la empresa ofrezca bienes y servicios.

MongoDB sigue siendo la autoridad. Añadir un perfil comercial confirmado a `catalog` (misma empresa e incremento atómico de revisión), con actividad original, capacidades, cobertura, exclusiones y procedencia/versión de sugerencias. Mantener ítems manuales, decisiones y sesiones existentes. Un cambio confirmado de perfil invalida resultados mediante su revisión; no se borra seguimiento.

Para el primer incremento, usar sugerencias deterministas, vocabulario revisable y confirmación humana. La extracción de términos o sinónimos no demuestra capacidades de la empresa. Un modelo de lenguaje sería una decisión posterior: implica proveedor, coste, privacidad, evaluación y controles frente a texto no confiable; no es necesario para entregar el flujo guiado inicial.

Jobs conservan filtros/alcance y revisión del perfil con que se solicitaron. Si el perfil cambia durante la ingesta, los concursos se conservan como corpus compartido de la instalación y el radar se recalcula con el perfil confirmado actual. Redis mantiene aislamiento e incorpora la revisión del perfil y la versión de sugerencias/reglas.

## Cambios propuestos al planning

| Issue | Ajuste propuesto |
|---|---|
| NLC-03 · autenticación/catálogo | Añadir onboarding del perfil, borrador/confirmación, edición y migración sin perder catálogo. Mantener autenticación. |
| NLC-04 · ingesta | Plan de consulta derivado del perfil confirmado; alcance visible, reutilización de corpus y actualización bajo demanda. |
| NLC-07 · matching/radar | Razones en lenguaje claro, información por confirmar, feedback con motivos y propuesta de ajustes. |
| NLC-08 · caché | Invalidar también por revisión del perfil y versión de sugerencias; probar aislamiento entre instalaciones. |
| NLC-10 · validación | Recorrido actividad → perfil confirmado → búsqueda → evidencia → decisión; medir facilidad de uso y calidad con empresas/casos etiquetados. |

NLC-05 conserva su arquitectura de jobs. El arranque local automático del worker resuelve un problema operativo independiente. NLC-01/06/09 mantienen sus pendientes de evidencia SICOP, documentos y adjudicaciones; el rediseño no los elimina.

Propuesta de entrega en dos incrementos: primero onboarding y perfil confirmado con radar existente; después búsqueda orientada, feedback y evaluación de calidad. El usuario autorizó ajustar los issues 3, 4, 7, 8 y 10 a este alcance. La demo no completa por sí sola las validaciones de infraestructura, OCR ni calidad humana.

## Criterios de aceptación sugeridos

- Una empresa puede obtener su primera lista sin conocer palabras clave o clasificaciones SICOP.
- Toda capacidad, exclusión y cobertura sugerida es editable y requiere confirmación.
- «No sé» o información incompleta no se convierte en un rechazo automático.
- Recargar, reintentar o cambiar el perfil no duplica jobs ni pierde decisiones.
- Los fallos de SICOP y documentos incompletos son visibles y distintos de cero coincidencias.
- La ausencia de worker no provoca espera silenciosa; arranque local integrado y estado operativo verificable.
- Evaluación humana antes de fijar umbrales o afirmar calidad del matching.

## Cómo probar la demo

Abrir `/discover` con la sesión local. Escribir «Instalamos y mantenemos redes informáticas para oficinas». Revisar los servicios propuestos, cobertura opcional y tipo de oportunidades. Confirmar para consultar primero los concursos existentes; pulsar «Consultar novedades en SICOP» para encolar una consulta acotada. El perfil confirmado queda en MongoDB; no se crean concursos ficticios. Para el recorrido con datos sintéticos, usar `pytest tests/test_discovery.py` sin tocar la base local.

### Correcciones de búsqueda (15 de octubre de 2026)

La descripción se compara con un vocabulario controlado, sin llamadas a IA. Las
sugerencias son un borrador que debe revisar la empresa. Se distinguen redes
informáticas y redes sociales, se reconocen actividades de software y se omiten
negaciones simples por cláusula. Una actividad desconocida requiere términos
manuales; no se usan ubicaciones ni adjetivos como servicios.

El radar compara los servicios confirmados y el catálogo manual con títulos,
líneas y documentos disponibles. Normaliza tildes y mayúsculas, y reconoce una
lista explícita de variantes de singular/plural. No interpreta semánticamente
cualquier descripción ni determina elegibilidad. Las negaciones complejas y los
sinónimos fuera del vocabulario requieren revisión humana.

Con perfil confirmado, la vista «Por revisar» oculta afinidad cero por defecto.
Afinidad mínima 0 permite explorar todo; los seguimientos siguen accesibles aunque
el perfil cambie. El filtro de título/institución admite búsquedas sin tildes.
La consulta a SICOP sigue siendo una ventana acotada por categoría, no una búsqueda
exhaustiva por descripción. La cobertura geográfica no filtra automáticamente.

Validación: 12 casos sintéticos de regresión (8 fallaban antes del arreglo), más
la suite existente. Los datos sintéticos deben permanecer en una base de pruebas
separada: un identificador ficticio mezclado con el corpus real provoca errores
al reconsultarlo en SICOP. Los trabajos parciales conservan los concursos ya
procesados; un error no significa que no existan resultados.

### Inicio sin datos de demostración

Al entrar sin perfil, la bienvenida explica tres pasos: nombre comercial,
actividad y confirmación de servicios/cobertura/exclusiones. `/company` permite
crear o editar la identidad; los borradores no escriben en MongoDB ni encolan
consultas. El nombre acompaña al perfil en el dashboard y el radar. Al confirmar
se guarda la empresa; consultar SICOP sigue siendo una acción explícita.
Los errores de formularios solicitados como HTML muestran una página con opciones
de recuperación; los clientes JSON conservan respuestas estructuradas.

Las instalaciones nuevas no generan empresas, catálogos ni concursos de ejemplo.
Para reiniciar un espacio local existente se detiene la API y el worker, se exporta
cada colección a BSON en `var/backups` (ignorado por Git, permisos privados), se
conserva `users` y se vacían los datos restantes mediante transacción. Se mantienen
índices, se inicializa catálogo vacío y se aumenta la generación del corpus para
invalidar caché. Las sesiones se cierran; el usuario inicia sesión nuevamente.

### Experiencia guiada simplificada — 15 de octubre de 2026

El recorrido muestra una decisión por pantalla: empresa → sector → especialidad
→ revisión. Los desplegables son nativos; la interfaz mejora progresivamente con
JavaScript y conserva formularios de servidor. Para especialidades conocidas la
descripción es opcional: el servidor genera una frase explícita a partir de la
selección. «Otra actividad» requiere contexto y servicios manuales.

La revisión presenta servicios seleccionables y despliega edición manual,
cobertura, exclusiones y categoría solo cuando se necesitan. Confirmar es una
acción explícita que guarda el perfil; no encola una consulta. Volver utiliza
`POST /discover/revise` y conserva servicios y ajustes en el borrador, sin escribir
en MongoDB ni depender del historial del navegador. Los fallos al confirmar se
muestran junto al formulario y conservan lo escrito.

Hay tutoriales breves plegables en la configuración y el radar; el primer radar
distingue entre no haber consultado, no disponer aún de datos y filtros sin
coincidencias. Controles táctiles, foco al cambiar de paso, cierre de sesión móvil,
contraste explícito y respeto a movimiento reducido completan el recorrido.
Las pruebas de navegador usan borradores: no reemplazan la empresa guardada.

### Personalización y navegación — 16 de octubre de 2026

La actividad se elige entre 20 sectores y 65 especialidades; el vocabulario y sus
límites se documentan en [taxonomy.md](taxonomy.md). El radar permite elegir
consultas de 10, 25, 50 o 100 concursos recientes por rubro confirmado, además de
revisar hasta ese número de activos guardados. El alcance forma parte de la
idempotencia. Un filtro independiente permite explorar bienes, servicios u obras
del corpus local; se conserva al paginar y no modifica el perfil de la empresa.

La navegación prioriza Inicio, Mi radar y Mi empresa, con exploración y actividad
como opciones secundarias. El menú se adapta a pantalla estrecha; los controles,
las tarjetas, los servicios seleccionables y las ayudas tienen feedback visual.
Las transiciones entre páginas aprovechan View Transitions cuando está disponible,
sin interceptar enlaces o formularios ni retrasar las acciones. Se respeta la
preferencia de movimiento reducido y el regreso mediante historial del navegador.
