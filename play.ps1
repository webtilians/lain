param(
    [string]$GodotPath = '',
    [switch]$ImportOnly
)
$ErrorActionPreference = 'Stop'
$clientPath = Join-Path $PSScriptRoot 'client'
if (-not (Test-Path -LiteralPath (Join-Path $clientPath 'art/apartment/plaster.png'))) {
    throw 'Falta plaster.png. Actualiza la rama completa antes de iniciar el juego.'
}
if ([string]::IsNullOrWhiteSpace($GodotPath)) {
    $engineCommand = Get-Command 'Godot*_console.exe', 'godot', 'godot4' -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $engineCommand) {
        throw 'No se encuentra Godot. Usa .\play.ps1 -GodotPath C:\ruta\Godot.exe'
    }
    $GodotPath = $engineCommand.Source
}
Write-Host 'Preparando los recursos de Godot...'
$importOutput = & $GodotPath --headless --path $clientPath --editor --import --quit 2>&1
$engineExit = $LASTEXITCODE
$importOutput | ForEach-Object { Write-Host $_ }
if ($engineExit -ne 0 -or (($importOutput -join "`n") -match '(?m)^(ERROR:|SCRIPT ERROR:)')) {
    throw 'La importación ha fallado. No se iniciará el juego con recursos incompletos.'
}
$mapping = Get-Content -LiteralPath (Join-Path $clientPath 'art/apartment/plaster.png.import') -Raw
if ($mapping -notmatch 'path="res://([^"]+)"') {
    throw 'Godot no ha generado la referencia de la textura.'
}
if (-not (Test-Path -LiteralPath (Join-Path $clientPath $Matches[1]))) {
    throw 'La textura importada no existe. Revisa los errores anteriores.'
}
Write-Host 'Recursos preparados.'
if (-not $ImportOnly) {
    # The visible game is the intended interactive output of this launcher.
    & $GodotPath --path $clientPath
}
