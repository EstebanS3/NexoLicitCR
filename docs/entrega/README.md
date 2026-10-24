# Materiales de entrega · NexoLicitCR v0.9.0

Esta entrega reúne documentación, demostración y un borrador editable para la exposición final. La versión acordada es **v0.9.0**. Los dos videos se incluyen en esta rama y están enlazados en la tabla. El tag original `v0.9.0` permanece local y corresponde a la entrega inicial; la demo adicional de SICOP es posterior. La [validación de entrega](VALIDACION.md) describe los comandos ejecutados, el entorno y los límites de la evidencia.

| Material | Archivo y finalidad |
|---|---|
| Documentación principal | [README](../../README.md): problema, usuarios, arquitectura, instalación, variables, datos, capturas, licencia y roadmap. |
| Cambios | [CHANGELOG](../../CHANGELOG.md): versión de entrega y antecedentes que existen en Git. |
| Ficha del portal | [portal.yml](../../portal.yml): ficha provisional; verificar el esquema oficial de la sección 7 antes de cargarla al portal. |
| Guion de video | [GUION.md](demo/GUION.md): escenas, narración y alcance de la demostración. |
| Video de 3–5 minutos | [NexoLicitCR_demo.mp4](demo/NexoLicitCR_demo.mp4): explicación de 4:44. |
| Subtítulos | [NexoLicitCR_demo.srt](demo/NexoLicitCR_demo.srt), también incluidos en el video. |
| Demo adicional con SICOP real | [Video MP4 de 4:55](demo-sicop/NexoLicitCR_cliente_SICOP.mp4) · [Recorrido de Mesa Norte Catering](demo-sicop/README.md): cuenta propia, consultas reales y decisiones de cliente. Material posterior al tag v0.9.0. |
| Presentación editable | [NexoLicitCR_presentacion_final.pptx](presentacion/NexoLicitCR_presentacion_final.pptx): borrador para adaptar a la exposición. |
| Presentación PDF | [NexoLicitCR_presentacion_final.pdf](presentacion/NexoLicitCR_presentacion_final.pdf). |
| Dataset de demostración | [prepare_demo.py](../../scripts/prepare_demo.py): entorno independiente y contenido sintético. |

## Reproducir el escenario

Desde la raíz del repositorio, después de `uv sync --frozen`, usar un ejecutable MongoDB Community compatible con macOS/Linux:

```bash
uv run python scripts/prepare_demo.py start --mongod /ruta/al/binario/mongod
uv run python scripts/prepare_demo.py serve
```

Abrir [http://localhost:8010](http://localhost:8010). Consultar de forma privada las credenciales generadas en `var/demo/access.json`. La configuración reside en `var/demo/demo.env`; ninguno de esos archivos debe publicarse ni aparecer en la grabación.

La empresa **Brújula TI** y los concursos/anexos del escenario son ficticios. MongoDB de la demo escucha en `127.0.0.1:27019`, con autenticación y base `nexolicit_demo_v090`. La API se ejecuta sin worker y el registro de preparación se identifica como simulado. Se demuestran pantallas y comportamiento sobre datos preparados; no se atribuye una consulta en vivo a SICOP.

Si el entorno macOS impide importar una instalación editable, ejecutar `uv sync --frozen --no-editable` y anteponer `uv run --no-sync` a los comandos Python/CLI siguientes. Ver [solución de problemas](../../README.md#operación-y-solución-de-problemas).

`uv run python scripts/prepare_demo.py seed` repone los datos del escenario de forma idempotente. Para terminar, cerrar la API con Ctrl+C y ejecutar `uv run python scripts/prepare_demo.py stop`. Las fechas del escenario se fijan en la primera siembra: revisar su vigencia antes de reutilizarlo en otra fecha.

## Revisión de entrega

- Verificar enlaces, rutas de medios, duración del video y legibilidad de capturas/diapositivas.
- Mantener coherentes la versión del paquete, el changelog, la ficha y el tag `v0.9.0`.
- Registrar los comandos realmente ejecutados y sus resultados; conservar los límites de los informes históricos.
- Validar `portal.yml` con la plantilla de la sección 7 cuando esté disponible.

La memoria técnica y la evidencia previa están en [validación](../validacion/README.md); el [alcance académico](../alcance-academico.md) define lo que cada evidencia permite sostener.
