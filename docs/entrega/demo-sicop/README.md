# Mesa Norte Catering · demo con SICOP real

Segunda demostración de NexoLicitCR, grabada el **21 de octubre de 2026**. La empresa, su cuenta y sus comentarios son ficticios; las consultas, expedientes y anexos provienen de SICOP. Se usa una base exclusiva y un Chromium de Playwright con perfil temporal vacío, separado de los navegadores personales.

- [Video MP4 de 4:55](NexoLicitCR_cliente_SICOP.mp4).
- [Subtítulos](NexoLicitCR_cliente_SICOP.srt), también incluidos como pista en el video.
- [Narración editable](narracion.json) y [ficha técnica](video.json).

[Validación del recorrido y del archivo final](validacion.json): persistencia comprobada en MongoDB, 19 escenas revisadas, decodificación completa sin errores y audio sin saturación.

## Recorrido del cliente

Crear la cuenta → configurar empresa y especialidad → agregar un servicio al catálogo → consultar diez concursos → ampliar a cincuenta al no encontrar alimentación en la ventana inicial → procesar anexos → detener el trabajo restante conservando lo recuperado → revisar el expediente → guardar un comentario → leer el PDF → definir tareas de seguimiento → descartar una reparación de excavadora → filtrar la cartera → cerrar sesión y comprobar la persistencia al volver.

El caso principal es el procedimiento **2026LD-000009-0033400001**, alimentación por demanda para un taller en Huetar Norte. [Expediente oficial de SICOP](https://www.sicop.go.cr/app/module/bid/public/cartel-specification-published?cartelNo=20261002698&cartelSeq=00).

El concurso principal conserva un PDF de nueve páginas procesado correctamente. Otros concursos de la búsqueda ampliada contienen archivos no compatibles o evidencia parcial. La nota comercial pide cotejar la documentación vigente en SICOP antes de participar. Los comentarios se guardan en la aplicación; no se envían a SICOP ni a la institución. No se presentan ofertas.

## Edición y procedencia

La narración interpreta a la encargada comercial de la empresa ficticia, mediante la voz local Paulina. La música de ascensor es una composición original sintetizada con notas, sin grabaciones de terceros. Las esperas se muestran en cámara rápida con su factor y duración real; las acciones permanecen a velocidad normal.

El montaje une tramos de la misma cuenta y base, separados por pausas de producción. El listado de SICOP cambió durante la producción: el expediente pasó a estar fuera de los diez concursos recientes. Se conservó el registro y la primera consulta, y se grabó la ampliación real desde ese estado. Un corte de conexión local obligó a retomar la captura del mismo trabajo; la cola siguió avanzando. Los rótulos de espera indican el tiempo grabado, no toda la duración del trabajo. El montaje no presenta datos sembrados ni respuestas simuladas como resultados de la fuente.

La grabación anterior de Brújula TI y el tag `v0.9.0` se conservan. Esta demo y la corrección visual posterior no están incluidas en ese tag.

## Entorno exclusivo

```bash
uv run python scripts/prepare_sicop_demo.py start --mongod /ruta/a/mongod
uv run python scripts/prepare_sicop_demo.py serve
```

API: `http://localhost:8011`. MongoDB autenticado: `127.0.0.1:27020`, base `nexolicit_demo_sicop`. Los archivos privados y credenciales quedan en `var/demo-sicop/`; no se distribuyen. `start` crea índices, pero no crea la cuenta ni siembra concursos. El registro inicial se realiza por la interfaz. Si ya hay una cuenta, no se elimina ni reemplaza.

El servidor posee un worker que usa la misma configuración explícita. Detener la API con Ctrl+C y luego ejecutar `uv run python scripts/prepare_sicop_demo.py stop`. La carpeta de datos se conserva. El perfil de empresa y los permisos declarados en la narración son ficticios; no acreditan elegibilidad.

## Producción del video

Herramientas opcionales: Node.js, Playwright con Chromium descargado, FFmpeg y voz Paulina de macOS. No son dependencias de uso de NexoLicitCR.

- `scripts/assemble_sicop_demo.py --prepare-audio`: voz local y tiempos de cada escena.
- `scripts/record_sicop_demo.mjs`: registro y consulta inicial; requiere un entorno de demo nuevo. Sus identificadores corresponden al caso grabado, no a una prueba automática estable de SICOP.
- `scripts/record_sicop_continuation.mjs`: amplía la búsqueda en la misma cuenta, espera la evidencia del caso y realiza las decisiones.
- `scripts/record_sicop_continuation.mjs --resume-job ID`: retoma la captura de un trabajo existente si hubo un corte, sin volver a encolarlo.
- `scripts/compose_sicop_recording.py`: selecciona las escenas completadas y revisadas de los tramos privados.
- `scripts/assemble_sicop_demo.py --ffmpeg /ruta/a/ffmpeg`: montaje, música original, subtítulos y MP4 a partir de los tramos revisados en el manifiesto privado.

Las consultas reales pueden cambiar, fallar o pedir una pausa. Antes de otra toma, revisar la vigencia del caso, el texto de la narración y el estado de los anexos. No sobrescribir bases de otras instalaciones ni ignorar las pausas de la fuente. El material bruto, capturas y registros permanecen fuera de Git en `var/demo-sicop-video/`.
