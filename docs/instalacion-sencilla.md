# Instalación sencilla desde GitHub

Descargá el ZIP de una versión de NexoLicitCR desde GitHub y extraelo en una carpeta propia y permanente (no una carpeta temporal ni compartida). También sirve un clon. No hace falta tener Python, Git o Docker instalados si usás el ZIP.

## Windows 10/11

Requiere PowerShell y WinGet (App Installer de Microsoft). En PowerShell, desde la carpeta extraída:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

El permiso de ejecución solo aplica a ese proceso. WinGet instala Tesseract y Poppler y puede solicitar elevación. El script prepara Python 3.12 y las dependencias fijadas en `uv.lock`. Los idiomas españoles y orientación se descargan de `tesseract-ocr/tessdata_fast`, versión 4.1.0. Después abrí **start.cmd** con doble clic.

## Ubuntu/Debian

```bash
bash install.sh
bash start.sh
```

El instalador utiliza `sudo apt-get` para las herramientas del sistema. Ejecutalo con tu usuario habitual, no con `sudo bash install.sh`. En otras distribuciones instalá manualmente Tesseract con `spa` y `osd`, Poppler y curl; después usá `bash install.sh --skip-system`. Esas distribuciones no tienen instalación automática validada.

## macOS

Requiere [Homebrew](https://brew.sh) instalado. Ejecutá `bash install.sh`; después podés abrir **start.command** o usar `bash start.sh`. El instalador no instala Homebrew automáticamente.

## Primera configuración y uso

El asistente pide URI, usuario, contraseña y base exclusiva de MongoDB Atlas. Creá previamente el acceso en Atlas y autorizá tu IP. Las credenciales se guardan en `var/installer/config.json`, ignorado por Git. No se incluyen credenciales del desarrollador ni se crea una cuenta Atlas automáticamente. En Windows la carpeta debe ser privada del usuario: se aplican sus permisos heredados.

Si existe `.env`, se valida y conserva; tiene prioridad sobre el archivo del asistente. `.env.atlas` corresponde a Docker y no se importa automáticamente. Podés corregir el JSON con un editor o, si todavía no tenés datos/configuración que conservar, renombrarlo para volver a ejecutar el asistente. No publiques estos archivos.

Al iniciar, se verifican OCR, MongoDB e índices y se abre el navegador cuando la web está lista. El worker se ejecuta junto con la web. Mantené la terminal abierta y usá **Ctrl+C** para detener ambos. Cerrar solo el navegador no detiene la aplicación. No se instala un servicio de inicio automático.

Si el puerto está ocupado, cerrá la otra instancia o ajustá `PUBLIC_ORIGIN` (por ejemplo `http://localhost:8001`) en la configuración activa. El lanzador usa ese puerto y escucha solo en `127.0.0.1`.

## Repetir o diagnosticar

Los instaladores se pueden repetir: conservan `.env` y el JSON. `--no-configure` en Bash o `-NoConfigure` en PowerShell omite preguntas; no verifica Atlas. `--skip-system` / `-SkipSystem` omite gestores del sistema, pero sigue verificando OCR. Las instalaciones requieren internet. El uso normal necesita internet para Atlas y SICOP.

```bash
.venv/bin/python scripts/easy_install.py check
bash start.sh --no-browser
```

Windows: `.venv\Scripts\python.exe scripts\easy_install.py check` y `start.cmd --no-browser`.

La configuración del asistente la carga el lanzador; para usar directamente la CLI `nexolicit`, configurá `.env` como describe el README.

## Alcance de esta primera versión

No es un MSI ni una aplicación portable. Conservá la carpeta de instalación: los lanzadores dependen de su entorno `.venv`. No movás ni copies ese entorno a otra máquina; ejecutá el instalador allí. No hay actualización automática: para una nueva versión usá otra carpeta y transferí únicamente tu configuración privada, conservando la misma base e identificador de instalación. Los datos de negocio permanecen en MongoDB.

La integración completa en equipos Windows/Linux limpios debe verificarse antes de anunciar compatibilidad de producción. Las dependencias del sistema siguen las versiones de WinGet/APT/Homebrew; Python usa el lockfile del proyecto.
