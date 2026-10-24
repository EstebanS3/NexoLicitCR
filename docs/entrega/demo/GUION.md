# Guion de la demo · NexoLicitCR v0.9.0

Duración: **4:44**. Recorrido grabado de la aplicación real con una base independiente, un usuario propio de demostración y la empresa ficticia **Brújula TI**. Narración sintética en español (voz local Paulina) y subtítulos incluidos en el MP4 y como archivo SRT.

## Escenario y alcance

- Cinco concursos sintéticos: tres afines vigentes, uno vencido y uno fuera de rubro.
- Tres anexos PDF originales en GridFS; uno de los expedientes tiene evidencia parcial.
- Login, lectura, filtros, escritura de nota y seguimiento sobre MongoDB real.
- El navegador utiliza un perfil temporal vacío y permite únicamente peticiones a `http://localhost:8010`.
- La actividad `DEMO-CARGA-LOCAL` es un registro preparado; no representa una consulta SICOP ni una ejecución del worker.
- La afinidad del escenario no mide precisión comercial ni elegibilidad. Esta grabación muestra texto digital; las pruebas de OCR están documentadas por separado.

## Escenas y narración

### 00:00 · Un escenario ficticio, una aplicación real

Esta es Nexo Licit Costa Rica, una aplicación para ayudar a pequeñas empresas a revisar oportunidades de contratación pública. En esta demostración usaremos Brújula TI, una empresa ficticia de soporte y redes. Creamos una base independiente y una cuenta propia. Todos los concursos, instituciones y documentos que veremos son sintéticos; las interacciones se realizan en la aplicación real.

### 00:27 · El perfil de Brújula TI

Al ingresar encontramos el espacio de la empresa. El perfil conserva el nombre comercial, las actividades y las especialidades que orientan la búsqueda. Cada instalación administra una empresa. La configuración se revisa antes de confirmarse y queda almacenada en Mongo DB. Así podemos volver al mismo contexto sin empezar de nuevo en cada sesión.

### 00:51 · Un catálogo que la empresa puede ajustar

El catálogo describe lo que Brújula TI ofrece: soporte técnico, mantenimiento y redes. Los términos y códigos permiten relacionar la oferta con la información de los concursos. El catálogo es editable y conserva su propia revisión. Aquí mostramos datos preparados para repetir el recorrido; no estamos afirmando que una empresa real haya validado estas coincidencias.

### 01:17 · Coincidencias explicadas

El radar reúne oportunidades y muestra una afinidad orientativa. Cada tarjeta conserva el título, la institución, el cierre y una explicación de por qué aparece. También informa cuándo se verificó el contenido. La puntuación ayuda a priorizar la revisión; no garantiza que la empresa cumpla todos los requisitos ni que vaya a ganar una contratación.

### 01:42 · Reducir la lista para revisar mejor

Podemos buscar por título o institución y combinar filtros de estado, tipo de concurso y afinidad mínima. Aplicaremos una búsqueda de soporte para concentrarnos en ese servicio. Los resultados se calculan sobre el corpus guardado. En una instalación conectada, consultar novedades requiere una acción explícita; el radar no representa todo el contenido de SICOP.

### 02:07 · Del resultado al expediente

Abrimos un concurso de ejemplo para revisar sus líneas, cantidades y condiciones. A la derecha aparecen las coincidencias que respaldan la afinidad. Esta vista conecta la recomendación con su evidencia y permite distinguir información disponible de información pendiente. En los datos reales, siempre corresponde revisar el expediente original y las condiciones antes de participar.

### 02:33 · Documentos con procedencia

Los documentos se almacenan en Grid FS y su texto se organiza por página. Podemos leer la evidencia o descargar el original. El archivo de esta demo es sintético. El sistema admite extracción de PDF y OCR cuando está configurado; si una página no puede leerse, muestra el estado parcial en lugar de dar el expediente por completo.

### 02:57 · Guardar una decisión de seguimiento

Ahora registramos una decisión real en nuestra base de demostración. Elegimos en seguimiento y añadimos una nota: revisar experiencia y preparar la propuesta técnica. Guardamos el formulario. Las decisiones permanecen separadas de los resultados calculados, para conservar el criterio de la empresa aunque cambie el perfil o se actualice el contenido del concurso.

### 03:22 · Comprobar que la decisión quedó guardada

Volvemos al radar y seleccionamos la vista en seguimiento. La oportunidad aparece con el estado que acabamos de guardar. Este recorrido muestra lectura, filtrado y escritura con persistencia real en Mongo DB. Los datos se preparan mediante un script reproducible y se mantienen aislados de la base que utiliza el propietario del proyecto.

### 03:45 · Actividad y responsabilidades de los motores

La pantalla de actividad permite revisar estados y resultados de trabajos. Aquí se presenta un registro sintético de la carga local, no una consulta ejecutada contra SICOP. En el sistema, Mongo DB conserva los trabajos durables, perfiles y concursos; Grid FS almacena archivos. Redis es una caché opcional: la aplicación conserva un camino de cálculo cuando la caché no está disponible.

### 04:13 · Alcance de la versión 0.9.0

La versión cero punto nueve reúne perfil, catálogo, radar explicado, documentos y seguimiento. El repositorio incluye instalación, datos de prueba y evidencia técnica con sus límites. El roadmap propone evaluar relevancia con empresas y ampliar las mediciones. Esta demo muestra un escenario ficticio reproducible; la disponibilidad de SICOP, la precisión comercial y los comparables adjudicados requieren validaciones adicionales.

## Repetir la grabación

Primero preparar y abrir la demo siguiendo el [README de entrega](../README.md). Leer las credenciales exclusivamente desde `var/demo/access.json`; no se incluyen en estos materiales.

La grabación requiere Node.js, Playwright con su navegador descargado, FFmpeg y, para esta narración, macOS con la voz Paulina. Estas herramientas son opcionales y no forman parte de la instalación de la aplicación.

```bash
uv run python scripts/prepare_demo_audio.py
npm install --prefix var/media-tools playwright@1.62.1
export PLAYWRIGHT_MODULE="$PWD/var/media-tools/node_modules/playwright"
PLAYWRIGHT_BROWSERS_PATH=var/demo-video/browser-cache \
  var/media-tools/node_modules/.bin/playwright install chromium
node scripts/record_demo.mjs --screenshots
# Reponer el escenario antes de la toma definitiva:
uv run python scripts/prepare_demo.py seed
node scripts/record_demo.mjs
uv run python scripts/assemble_demo.py --ffmpeg /ruta/al/binario/ffmpeg
```

Los scripts nunca abren el perfil personal de un navegador. Los intermedios quedan en `var/demo-video/`, fuera de Git. Las capturas publicables se guardan en `docs/assets/demo/`. La fuente de narración editable está en [narracion.json](narracion.json).

## Archivos entregados

- [Video MP4 de 4:44](NexoLicitCR_demo.mp4).
- [Subtítulos SRT](NexoLicitCR_demo.srt).
- [Ficha técnica del video](video.json).
