# Revisión de privacidad de los videos

Revisión realizada el 21 de octubre de 2026 sobre los dos MP4 finales.

**Resultado: no se detectaron datos personales del propietario ni información que identifique su computadora.** No se encontraron motivos de privacidad para recortar, censurar o volver a grabar estos archivos. Los videos permanecen sin modificaciones y se conservan únicamente en local; no se incluyen en la rama publicable.

| Archivo | Muestreo a 2 fotogramas/s | Fotogramas adicionales por cambios de imagen | Resultado |
| --- | ---: | ---: | --- |
| `demo/NexoLicitCR_demo.mp4` | 569 | 63 | Sin hallazgos de privacidad |
| `demo-sicop/NexoLicitCR_cliente_SICOP.mp4` | 590 | 80 | Sin hallazgos de privacidad |

Las copias de la carpeta de entrega `Videos`, incluida la denominada `NexoLicitCR_demo_Explicacion.mp4`, coinciden byte por byte con los respectivos archivos locales revisados. Esas copias MP4 están excluidas de Git.

## Comprobaciones realizadas

- Se decodificaron ambas pistas de video completas. Se extrajeron **1.302 imágenes** combinando muestreo regular y detección de cambios sobre toda la grabación. Se aplicó OCR en español e inglés a resolución original a todas esas imágenes.
- Se contrastó el texto con identificadores locales y secretos conocidos, sin incluir sus valores en el informe. También se buscaron rutas personales, direcciones locales, correos, credenciales, tokens y señales de ventanas ajenas a la aplicación. Una segunda comprobación normalizó espacios, acentos y caracteres que el OCR puede confundir. No hubo coincidencias sensibles.
- Se inspeccionaron visualmente las hojas de contacto de ambos recorridos, todos los cambios seleccionados y ampliaciones de los accesos. No se observó escritorio, barra del sistema, terminal, notificaciones, pestañas, marcadores ni datos del navegador personal.
- Se revisaron los guiones completos y se extrajeron los subtítulos internos de ambos MP4. Su texto coincide con los SRT externos y no contiene información personal del equipo.
- Se inspeccionaron la estructura del contenedor MP4 y sus metadatos. Cada archivo contiene una pista de video, una de audio y una de subtítulos. Los metadatos descriptivos son el título de la demo y el codificador; las marcas de creación/modificación del contenedor están en cero. No se detectó autor personal, nombre del equipo, ruta de origen, GPS ni archivos adjuntos.
- Se comparó el audio final decodificado con las fuentes locales de narración y música. La similitud de señal fue **0,999990** en la explicación y **0,999989** en SICOP; además, se comprobaron ventanas de cinco segundos. Los 19 segmentos de SICOP coinciden con las voces sintéticas o la música original y sus pausas previstas. El relleno final del codificador es silencio. No se detectó audio ajeno a esas fuentes.
- Los scripts de captura usan contextos temporales nuevos de Playwright y graban el contenido de la página. El montaje selecciona expresamente las pistas de narración y música.

## Información que sí aparece

- Las empresas ficticias Brújula TI y Mesa Norte Catering, sus perfiles y comentarios de demostración.
- Los usuarios ficticios `demo.brujula` y `demo.mesanorte`. Las contraseñas aparecen enmascaradas con puntos, también en los accesos breves entre escenas.
- En la demo de SICOP, información pública de concursos: instituciones, números de procedimiento, requisitos, fechas y lugares del servicio. Las referencias a Costa Rica y Huetar Norte pertenecen al escenario y los expedientes; no son una geolocalización de la computadora.
- La fecha rotulada de la demo y metadatos técnicos genéricos del formato/codificador.

## Identificación exacta de los archivos revisados

SHA-256 de la explicación:

```text
e25cdea088d09de7fa1dadffbc603a6db45b6229bbc1a327a703f63fa8907bce
```

SHA-256 de la demo SICOP:

```text
895c7942ea520be9fe6bd2be8c23eaa569ea2b4127f4a522129d55b9799c4483
```

La revisión visual y de OCR se basa en el muestreo y los cambios descritos; no constituye una inspección manual individual de cada fotograma ni una garantía absoluta de ausencia de información. El resultado corresponde exclusivamente a estos archivos, identificados por sus hashes. Las capturas, transcripciones y registros de trabajo de la auditoría permanecen en el directorio privado de trabajo, excluido de Git.
