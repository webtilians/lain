param(
    [string]$WorldPath = (Join-Path $PSScriptRoot 'chapter01.db'),
    [string]$PythonPath = ''
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $candidates = @(
        (Join-Path $PSScriptRoot '.venv/Scripts/python.exe'),
        (Join-Path (Split-Path $PSScriptRoot -Parent) 'lain/.venv/Scripts/python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { $PythonPath = $candidate; break }
    }
    if ([string]::IsNullOrWhiteSpace($PythonPath)) {
        $PythonPath = (Get-Command python -ErrorAction Stop).Source
    }
}
# Keep current model/provider choices; supply the user's established defaults only if absent.
$defaults = @{
    LAIN_LLM_ENABLED = '1'
    LAIN_LLM_MODEL = 'lain-qwen7b'
    LAIN_LLM_ENDPOINT = 'http://127.0.0.1:11434/v1/chat/completions'
    LAIN_LLM_TIMEOUT = '45'
    LAIN_REALITY_GENERATION = '1'
    LAIN_WORLD_CLOCK = '1'
    LAIN_WORLD_TICK_SECONDS = '8'
    LAIN_PROLOGUE_ENABLED = '1'
    LAIN_CITY_RESIDENTS_ENABLED = '1'
    LAIN_CHAPTER_ONE = '1'
}
foreach ($key in $defaults.Keys) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))) {
        [Environment]::SetEnvironmentVariable($key, $defaults[$key], 'Process')
    }
}
$env:LAIN_WORLD_DB = [IO.Path]::GetFullPath($WorldPath)
Write-Host "Partida de prueba: $env:LAIN_WORLD_DB"
Write-Host 'Si ya tienes otro servidor en el puerto 8000, ciérralo antes de iniciar este.'
& $PythonPath -m uvicorn server.api:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
