param(
    # internet: Cloudflare quick tunnel (HTTPS, no router changes). lan: same Wi-Fi only.
    [ValidateSet('internet', 'lan')]
    [string]$Mode = 'internet',
    [int]$Port = 8000,
    # Skip the host's local Ollama model even if it is available.
    [switch]$NoAI,
    # Create a new player access and friend kit, then exit (world must be closed).
    [string]$AddPlayer = '',
    [string]$Cloudflared = ''
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$dataDir = Join-Path $env:LOCALAPPDATA 'LAIN\OnlineHost'
$accessDir = Join-Path $dataDir 'access'
$logs = Join-Path $dataDir 'logs'
$kitsDir = Join-Path $env:USERPROFILE 'LAIN-Online-Amigos'
$utf8 = New-Object Text.UTF8Encoding $false

function Test-PortBusy([int]$number) {
    return [bool](Get-NetTCPConnection -LocalPort $number -State Listen -ErrorAction SilentlyContinue)
}

function Update-Kit([IO.DirectoryInfo]$access) {
    # One folder per player: personal access file, address updater and instructions.
    $kit = Join-Path $kitsDir $access.Name
    New-Item -ItemType Directory -Force -Path $kit | Out-Null
    Copy-Item -LiteralPath (Join-Path $access.FullName 'lain-online.json') -Destination $kit -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packaging\Cambiar servidor.bat') -Destination $kit -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packaging\LEEME-AMIGO.txt') -Destination $kit -Force
    # Single attachment to send each friend.
    Compress-Archive -Path (Join-Path $kit '*') -DestinationPath "$kit.zip" -Force
    return $kit
}

function Set-ServerUrl([string]$url) {
    # Only the address changes; every player keeps the token that identifies them.
    foreach ($access in (Get-ChildItem -LiteralPath $accessDir -Directory -ErrorAction SilentlyContinue)) {
        $file = Join-Path $access.FullName 'lain-online.json'
        if (-not (Test-Path -LiteralPath $file)) { continue }
        $config = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
        $config.server_url = $url
        [IO.File]::WriteAllText($file, ($config | ConvertTo-Json), $utf8)
        Update-Kit $access | Out-Null
    }
}

if ($AddPlayer) {
    if (Test-PortBusy $Port) {
        throw "Cierra antes el mundo online (Ctrl+C en su ventana): no se pueden crear jugadores con el servidor abierto."
    }
    & $python -m tools.online_server add-player --name $AddPlayer --url "http://127.0.0.1:$Port"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el jugador.' }
    $slug = $AddPlayer -replace '[^a-zA-Z0-9_-]', '_'
    if ($slug.Length -gt 24) { $slug = $slug.Substring(0, 24) }
    $access = Get-ChildItem -LiteralPath $accessDir -Directory -Filter "$slug-*" | Sort-Object CreationTime -Descending | Select-Object -First 1
    $kit = Update-Kit $access
    Write-Host ''
    Write-Host "Kit de $AddPlayer listo: $kit"
    Write-Host 'La dirección del servidor se rellena al abrir el mundo con .\online-host.ps1'
    exit 0
}

if (Test-PortBusy $Port) {
    throw "El puerto $Port está ocupado. Cierra el otro servidor de LAIN (por ejemplo serve-city.ps1) y vuelve a intentarlo."
}
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (-not $NoAI) {
    $hasModel = $false
    try {
        $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3
        $hasModel = @($tags.models | Where-Object { $_.name -like 'lain-qwen7b*' }).Count -gt 0
    } catch { $hasModel = $false }
    if ($hasModel) {
        $env:LAIN_LLM_ENABLED = '1'
        $env:LAIN_LLM_MODEL = 'lain-qwen7b'
        $env:LAIN_LLM_ENDPOINT = 'http://127.0.0.1:11434/v1/chat/completions'
        $env:LAIN_LLM_TIMEOUT = '45'
        Write-Host 'IA de los personajes: Ollama (lain-qwen7b) en este equipo.'
    } else {
        Write-Host 'IA de los personajes: desactivada (no hay Ollama con lain-qwen7b). Diálogos predefinidos.'
    }
}

function Start-Tunnel {
    # Each quick tunnel gets a new trycloudflare hostname. Returns $null on failure.
    $tunnelLog = Join-Path $logs 'tunnel.log'
    Remove-Item -LiteralPath $tunnelLog -ErrorAction SilentlyContinue
    $process = Start-Process -FilePath $Cloudflared -PassThru -NoNewWindow `
        -ArgumentList @('tunnel', '--no-autoupdate', '--url', "http://127.0.0.1:$Port") `
        -RedirectStandardError $tunnelLog -RedirectStandardOutput (Join-Path $logs 'tunnel-out.log')
    $address = ''
    for ($i = 0; $i -lt 120 -and -not $address; $i++) {
        Start-Sleep -Milliseconds 500
        if ($process.HasExited) { return $null }
        if (Test-Path -LiteralPath $tunnelLog) {
            $found = Select-String -LiteralPath $tunnelLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
            if ($found) { $address = $found.Matches[0].Value }
        }
    }
    if (-not $address) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        return $null
    }
    # The new hostname can take a few seconds to resolve worldwide.
    $public = $false
    for ($i = 0; $i -lt 40 -and -not $public; $i++) {
        try { Invoke-WebRequest -UseBasicParsing -Uri "$address/api/v1/player/state" -TimeoutSec 5 | Out-Null; $public = $true }
        catch {
            if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { $public = $true }
            else { Start-Sleep -Seconds 1 }
        }
    }
    if (-not $public) { Write-Warning 'La dirección aún no responde desde internet; espera un minuto antes de que entren tus amigos.' }
    return @{ Process = $process; Url = $address }
}

function Show-Address([string]$url, [bool]$changed) {
    Write-Host ''
    Write-Host '=============================================================='
    if ($changed) { Write-Host " DIRECCIÓN NUEVA  $url" } else { Write-Host " MUNDO LAIN ABIERTO  $url" }
    Write-Host '=============================================================='
    Write-Host " Kits de jugadores (actualizados con esta dirección): $kitsDir"
    Write-Host ' Pasa la dirección a tus amigos: la pegan con "Cambiar servidor.bat"'
    Write-Host ' y abren LAIN.exe. Si ya estaban jugando, que cierren y vuelvan a entrar.'
    Write-Host ' Deja esta ventana abierta mientras jugáis. Ctrl+C cierra el mundo.'
    Write-Host ''
}

# Keep this PC awake while the world is open (released automatically on exit;
# the Windows power plan is not changed).
Add-Type -Namespace LainHost -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);'
[LainHost.Power]::SetThreadExecutionState([uint32]2147483649) | Out-Null  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

$bind = '127.0.0.1'
if ($Mode -eq 'lan') { $bind = '0.0.0.0' }
$server = Start-Process -FilePath $python -WorkingDirectory $PSScriptRoot -PassThru -NoNewWindow `
    -ArgumentList @('-m', 'tools.online_server', 'serve', '--host', $bind, '--port', "$Port") `
    -RedirectStandardOutput (Join-Path $logs 'server.log') -RedirectStandardError (Join-Path $logs 'server-errors.log')
$tunnel = $null
try {
    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
        Start-Sleep -Milliseconds 500
        if ($server.HasExited) { throw "El mundo no arrancó. Revisa $logs\server-errors.log" }
        try { Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/v1/player/state" -TimeoutSec 2 | Out-Null; $ready = $true }
        catch { if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { $ready = $true } }
    }
    if (-not $ready) { throw 'El mundo no responde en el puerto local.' }

    if ($Mode -eq 'internet') {
        if (-not $Cloudflared) {
            $Cloudflared = Join-Path $env:USERPROFILE 'tools\cloudflared.exe'
            if (-not (Test-Path -LiteralPath $Cloudflared)) { $Cloudflared = (Get-Command cloudflared -ErrorAction Stop).Source }
        }
        $opened = Start-Tunnel
        if (-not $opened) { throw "Cloudflare no dio una dirección. Revisa $logs\tunnel.log" }
        $tunnel = $opened.Process
        $url = $opened.Url
    } else {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' } |
            Select-Object -First 1 -ExpandProperty IPAddress
        if (-not $ip) { throw 'No encuentro una dirección de red local.' }
        $url = "http://$($ip):$Port"
        Write-Host 'Si Windows pregunta por el cortafuegos, permite solo redes privadas.'
    }

    Set-ServerUrl $url
    Show-Address $url $false
    while (-not $server.HasExited) {
        Start-Sleep -Seconds 2
        if ($tunnel -and $tunnel.HasExited) {
            # Wi-Fi drops end quick tunnels; open a new one instead of closing the world.
            Write-Warning 'Se cortó la conexión del túnel. Abriendo uno nuevo...'
            $opened = $null
            for ($attempt = 1; $attempt -le 30 -and -not $opened; $attempt++) {
                $opened = Start-Tunnel
                if (-not $opened) { Start-Sleep -Seconds 10 }
            }
            if (-not $opened) { throw 'No se pudo recuperar el túnel. Comprueba internet y vuelve a abrir el mundo.' }
            $tunnel = $opened.Process
            $url = $opened.Url
            Set-ServerUrl $url
            Show-Address $url $true
        }
    }
    throw "El mundo se cerró. Revisa $logs\server-errors.log"
} finally {
    foreach ($process in @($tunnel, $server)) {
        if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    }
    [LainHost.Power]::SetThreadExecutionState([uint32]2147483648) | Out-Null  # ES_CONTINUOUS: allow sleep again
    Write-Host 'Mundo cerrado. El progreso de todos queda guardado.'
}
