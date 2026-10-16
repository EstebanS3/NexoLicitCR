# Sectores y especialidades comerciales

La selección guiada ofrece **20 sectores y 65 especialidades**: 64 opciones con
términos sugeridos y una opción para definir una actividad propia. Es un vocabulario comercial editable
de NexoLicitCR: no representa códigos oficiales de SICOP, CIIU ni una acreditación.
Los sectores orientan los servicios sugeridos; no sustituyen el rubro de la
consulta (bienes, servicios u obras).

| Sector | Opciones disponibles |
|---|---|
| Tecnología e informática | Redes de datos, software, soporte informático, equipo de cómputo, ciberseguridad, nube |
| Deporte y recreación | Redes para porterías, equipamiento, actividades recreativas |
| Comunicación y mercadeo | Redes sociales, publicidad y diseño, producción audiovisual |
| Limpieza y mantenimiento | Limpieza de instalaciones, jardinería, plagas, aire acondicionado, productos de limpieza |
| Construcción y obras | Edificios, electricidad e iluminación, obra vial, acueductos y alcantarillado, materiales, estructuras metálicas |
| Alimentación | Catering, alimentos, equipo de cocina |
| Mobiliario | Oficina, escolar, estanterías y archivos |
| Salud y equipo médico | Insumos, equipo médico, odontología, laboratorio clínico |
| Seguridad física y prevención | Vigilancia, videovigilancia y acceso, protección contra incendios |
| Transporte y logística | Personas, carga y mudanzas, mensajería, almacenamiento y distribución |
| Vehículos y taller automotriz | Mantenimiento, repuestos, llantas y alineado |
| Educación y capacitación | Formación profesional, idiomas y traducción, material educativo |
| Consultoría y servicios profesionales | Jurídico, contabilidad y auditoría, ingeniería |
| Ambiente y gestión de residuos | Residuos, análisis de agua, estudios ambientales |
| Agro, veterinaria y recursos forestales | Insumos agrícolas, veterinaria, reforestación |
| Textiles, uniformes y protección personal | Uniformes, ropa y equipo de protección |
| Papelería e impresión | Útiles de oficina, impresión y consumibles |
| Maquinaria y equipo industrial | Maquinaria, herramientas, bombas y válvulas |
| Eventos y producción cultural | Producción y decoración, sonido e iluminación |
| Otra actividad | Especialidad definida por la empresa |

## Qué hace la selección

Una especialidad propone frases concretas que la empresa puede seleccionar,
editar o sustituir antes de confirmar. «Redes informáticas», «redes sociales»,
«redes para arcos» y «redes eléctricas» pertenecen a opciones distintas. Se
distinguen también vigilancia física y seguridad informática, transporte de
personas y carga, y servicio de limpieza y productos de limpieza.

La comparación utiliza los términos confirmados contra títulos, líneas y texto
de documentos disponibles. No basta seleccionar el sector para determinar la
elegibilidad de una empresa. Las coincidencias pueden requerir revisión: un curso
de ciberseguridad y un servicio de ciberseguridad comparten vocabulario, por ejemplo.
La especialidad inicial no limita lo que una empresa puede añadir a su catálogo.

Los identificadores existentes se conservan para que los perfiles guardados
sigan siendo válidos. Ampliar este archivo no cambia servicios ya confirmados ni
inicia consultas SICOP. Cambiar de especialidad requiere revisar y confirmar el
nuevo borrador.

## Procedencia y límites

La fuente de concursos es el [portal oficial SICOP](https://www.sicop.go.cr/), a
través del [cliente de consultas públicas del proyecto](../src/nexolicitcr/sicop.py).
La taxonomía se mantiene en [sectors.py](../src/nexolicitcr/sectors.py).

Para orientar esta ampliación se revisó una muestra local anterior de nueve
concursos (tres por rubro, observada el 9 de octubre de 2026), con 132 líneas.
Contiene, entre otros, transporte de personas, almacenamiento y distribución,
curso de certificación, madera y plywood, obra civil y figuras inflables para
eventos. Es una muestra de conveniencia, no aleatoria ni representativa del
mercado. La ampliación incorpora también lectura del corpus local disponible:
protección personal, producción audiovisual, luminarias, aceras y alcantarillado
pluvial. Durante la revisión inicial, una consulta nueva a SICOP devolvió un error
de disponibilidad; esta evidencia procede de concursos ya guardados y no acredita
su vigencia actual. No se descargan concursos como efecto de cambiar la taxonomía.

El resto de opciones es una selección editorial de actividades comerciales:
no se afirma que exista actualmente un concurso abierto para cada una. No se
copian códigos de clasificación ni información personal en este vocabulario.
La disponibilidad y la vigencia se comprueban en los concursos consultados, con
los límites de búsqueda visibles en la aplicación.

Las regresiones de [test_sectors.py](../tests/test_sectors.py) prueban coincidencias
en títulos y líneas, separación de términos ambiguos, validación de selecciones,
compatibilidad de perfiles previos y confirmación sin crear trabajos. Los casos
son sintéticos y no sustituyen una evaluación de precisión y exhaustividad con
pares etiquetados por personas.
