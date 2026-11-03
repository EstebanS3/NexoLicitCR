param([switch]$SkipSystem, [switch]$NoConfigure)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot
if (!(Test-Path 'uv.lock') -or !(Test-Path 'scripts/easy_install.py')) {
    throw 'Extrae el ZIP completo del proyecto antes de instalar.'
}
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Fallo $Program (codigo $LASTEXITCODE)." }
}
if (!$SkipSystem) {
    if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Instala App Installer (WinGet) desde Microsoft Store y vuelve a intentar.'
    }
    foreach ($Id in @('UB-Mannheim.TesseractOCR', 'oschwartz10612.Poppler')) {
        & winget install --exact --id $Id --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
        # WinGet devuelve este codigo si la version instalada ya esta actualizada.
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
            throw "No se pudo instalar $Id (codigo $LASTEXITCODE)."
        }
    }
}
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
$Installer = Join-Path $PSScriptRoot 'var/installer'
New-Item -ItemType Directory -Force $Installer | Out-Null
$Uv = Join-Path $Installer 'bin/uv.exe'
if (!(Test-Path $Uv)) {
    Invoke-WebRequest 'https://astral.sh/uv/0.12.24/install.ps1' -OutFile (Join-Path $Installer 'uv-install.ps1') -UseBasicParsing
    $PreviousInstall = $env:UV_UNMANAGED_INSTALL
    try {
        $env:UV_UNMANAGED_INSTALL = Join-Path $Installer 'bin'
        Invoke-Checked 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Installer 'uv-install.ps1'))
    } finally { $env:UV_UNMANAGED_INSTALL = $PreviousInstall }
}
Invoke-Checked $Uv @('sync', '--frozen', '--no-dev', '--python', '3.12')
$Python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
Invoke-Checked $Python @('scripts/easy_install.py', 'windows-ocr')
Invoke-Checked $Python @('scripts/easy_install.py', 'check')
if (!$NoConfigure) { Invoke-Checked $Python @('scripts/easy_install.py', 'configure') }
Write-Host 'Instalacion preparada. Abre start.cmd para iniciar NexoLicitCR.'
