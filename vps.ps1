param(
    # The server's IPv4 from the Hetzner console. Needed only the first time.
    [string]$Ip = '',
    # Create this PC's SSH key for the server and show its public half.
    [switch]$Key,
    # Install, or reinstall, the engine on the server.
    [switch]$Install,
    # Type the AI key on the server (run it yourself; it is never shown).
    [switch]$Gemini,
    [switch]$Groq,
    # Move the world and players from this PC's online-host.ps1 to the server.
    [switch]$Migrate,
    # Create a player on the server and build their ZIP.
    [string]$AddPlayer = '',
    # Build one ready-to-play ZIP per player (game + their access file).
    [switch]$Packages,
    # The game ZIP from GitHub Actions (only needed once; it is kept).
    [string]$GameZip = '',
    [switch]$Status,
    [switch]$Update,
    [switch]$Shell,
    # With -Migrate: replace a server world that already has players.
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
$sshKey = Join-Path $env:USERPROFILE '.ssh\lain_vps'
$vpsDir = Join-Path $env:LOCALAPPDATA 'LAIN\VPS'
$accessDir = Join-Path $vpsDir 'access'
$configFile = Join-Path $vpsDir 'server.json'
$savedGame = Join-Path $vpsDir 'LAIN-Online-Windows.zip'
$friendsDir = Join-Path $env:USERPROFILE 'LAIN-Amigos'
$utf8 = New-Object Text.UTF8Encoding $false
New-Item -ItemType Directory -Force -Path $vpsDir, $accessDir | Out-Null

function Get-Server {
    if ($Ip) {
        $address = $null
        if (-not [Net.IPAddress]::TryParse($Ip, [ref]$address) -or $address.AddressFamily -ne 'InterNetwork') {
            throw 'Usa la IPv4 del servidor: cuatro números separados por puntos.'
        }
        # sslip.io gives a free name for HTTPS: 1.2.3.4 -> 1-2-3-4.sslip.io
        $config = [ordered]@{ ip = $Ip; host = ($Ip -replace '\.', '-') + '.sslip.io' }
        [IO.File]::WriteAllText($configFile, ($config | ConvertTo-Json), $utf8)
    }
    if (-not (Test-Path -LiteralPath $configFile)) {
        throw 'Indica la IP del servidor la primera vez: .\vps.ps1 -Ip 1.2.3.4 -Install'
    }
    return Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
}

function Get-SshOptions {
    if (-not (Test-Path -LiteralPath $sshKey)) { throw 'Falta la llave SSH. Créala con: .\vps.ps1 -Key' }
    return @('-i', $sshKey, '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ServerAliveInterval=30')
}

function Invoke-Server([string]$command, [switch]$Interactive) {
    $options = Get-SshOptions
    if ($Interactive) { $options += '-t' }
    & ssh.exe @options "root@$($server.ip)" $command
    if ($LASTEXITCODE -ne 0) { throw "El servidor devolvió un error ($LASTEXITCODE)." }
}

function Copy-ToServer([string]$source, [string]$target) {
    $options = Get-SshOptions
    & scp.exe @options -q -r $source "root@$($server.ip):$target"
    if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar $source al servidor." }
}

function Set-ServerUrl([string]$file) {
    $config = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
    $config.server_url = "https://$($server.host)"
    [IO.File]::WriteAllText($file, ($config | ConvertTo-Json), $utf8)
}

function Import-GameZip([string]$path) {
    # Accepts the game ZIP itself or the GitHub artifact ZIP that wraps it.
    $archive = [IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $path).Path)
    try {
        if ($archive.GetEntry('LAIN.exe')) {
            $archive.Dispose()
            Copy-Item -LiteralPath $path -Destination $savedGame -Force
        } else {
            $inner = @($archive.Entries | Where-Object { $_.FullName -like '*.zip' })
            if ($inner.Count -ne 1) { throw "$path no parece el ZIP del juego (falta LAIN.exe)." }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($inner[0], $savedGame, $true)
        }
    } finally { $archive.Dispose() }
    $check = [IO.Compression.ZipFile]::OpenRead($savedGame)
    try { if (-not $check.GetEntry('LAIN.exe')) { throw 'El ZIP del juego no contiene LAIN.exe.' } } finally { $check.Dispose() }
}

function Build-Package([IO.DirectoryInfo]$access) {
    if (-not (Test-Path -LiteralPath $savedGame)) {
        Write-Host "  (Sin ZIP del juego todavía: usa -Packages -GameZip <ruta> para crear los paquetes.)"
        return
    }
    New-Item -ItemType Directory -Force -Path $friendsDir | Out-Null
    $target = Join-Path $friendsDir ('LAIN-' + $access.Name + '.zip')
    Copy-Item -LiteralPath $savedGame -Destination $target -Force
    # Swap only the access file inside the copy; the game is not recompressed.
    $zip = [IO.Compression.ZipFile]::Open($target, 'Update')
    try {
        foreach ($name in 'lain-online.json', 'LEEME-PRIMERO.txt') {
            $old = $zip.GetEntry($name)
            if ($old) { $old.Delete() }
        }
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $access.FullName 'lain-online.json'), 'lain-online.json') | Out-Null
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, (Join-Path $PSScriptRoot 'packaging\LEEME-SERVIDOR.txt'), 'LEEME-PRIMERO.txt') | Out-Null
    } finally { $zip.Dispose() }
    Write-Host "  Paquete listo: $target"
}

if ($Key) {
    if (-not (Test-Path -LiteralPath $sshKey)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $sshKey) | Out-Null
        & ssh-keygen.exe -q -t ed25519 -N '""' -C 'lain-vps' -f $sshKey
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear la llave SSH.' }
    }
    Write-Host 'Llave pública (pégala en Hetzner > Security > SSH keys al crear el servidor):'
    Write-Host ''
    Write-Host (Get-Content -LiteralPath "$sshKey.pub" -Raw).Trim()
    Write-Host ''
}

if ($Ip -or $Install -or $Gemini -or $Groq -or $Migrate -or $AddPlayer -or $Status -or $Update -or $Shell) { $server = Get-Server }

if ($Install) {
    Copy-ToServer (Join-Path $PSScriptRoot 'deploy\vps\setup.sh') '/root/lain-setup.sh'
    Invoke-Server "bash /root/lain-setup.sh --host $($server.host)"
}

function Send-AiKey([string]$provider, [string]$label) {
    # Asked here, masked; it travels only inside the SSH connection's input.
    $secure = Read-Host "Pega tu clave de $label (clic derecho o Ctrl+V) y pulsa Enter" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $options = Get-SshOptions
    $plain | & ssh.exe @options "root@$($server.ip)" "lain-set-ai-key $provider"
    $plain = $null
    if ($LASTEXITCODE -ne 0) { throw 'No se activó la IA (mira el mensaje de arriba).' }
}

if ($Gemini) { Send-AiKey 'gemini' 'Google (Gemini)' }
if ($Groq) { Send-AiKey 'groq' 'Groq' }

if ($Migrate) {
    $hostDir = Join-Path $env:LOCALAPPDATA 'LAIN\OnlineHost'
    $database = Join-Path $hostDir 'online-world.db'
    if (-not (Test-Path -LiteralPath $database)) { throw "No encuentro el mundo de este PC en $database" }
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Cierra antes el mundo online de este PC (Ctrl+C en la ventana de online-host.ps1).'
    }
    $existing = Invoke-Server 'cd /opt/lain && runuser -u lain -- env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tools.online_server --data-dir /var/lib/lain list-players'
    if ((($existing -join "`n") -match 'ACTIVO|REVOCADO') -and -not $Force) {
        throw 'El servidor ya tiene jugadores. Usa -Force para sustituir su mundo por el de este PC (se guarda copia).'
    }
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python).Source }
    $snapshot = Join-Path $env:TEMP 'lain-import.db'
    Remove-Item -LiteralPath $snapshot -Force -ErrorAction SilentlyContinue
    # SQLite's backup API gives one consistent file even with a pending WAL.
    & $python -c 'import sqlite3, sys; s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()' $database $snapshot
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo copiar el mundo local.' }
    Invoke-Server 'rm -rf /root/lain-import.db /root/lain-import-access'
    Copy-ToServer $snapshot '/root/lain-import.db'
    Remove-Item -LiteralPath $snapshot -Force
    $localAccess = Join-Path $hostDir 'access'
    if (Test-Path -LiteralPath $localAccess) { Copy-ToServer $localAccess '/root/lain-import-access' }
    Invoke-Server 'lain-import-world'
    foreach ($access in (Get-ChildItem -LiteralPath $localAccess -Directory -ErrorAction SilentlyContinue)) {
        $file = Join-Path $access.FullName 'lain-online.json'
        if (-not (Test-Path -LiteralPath $file)) { continue }
        $copy = Join-Path $accessDir $access.Name
        New-Item -ItemType Directory -Force -Path $copy | Out-Null
        Copy-Item -LiteralPath $file -Destination $copy -Force
        Set-ServerUrl (Join-Path $copy 'lain-online.json')
    }
    Write-Host "Mundo trasladado a https://$($server.host). Accesos en $accessDir"
    $Packages = $true
}

if ($AddPlayer) {
    if ($AddPlayer -notmatch '^[\p{L}\p{N} _.-]{1,32}$') { throw 'Usa un nombre corto con letras, números, espacios, puntos o guiones.' }
    $output = Invoke-Server ("lain-add-player '" + $AddPlayer + "'")
    $remote = $null
    foreach ($line in $output) {
        if ($line -match '^Archivo privado: (/var/lib/lain/access/[A-Za-z0-9_-]+/lain-online\.json)$') { $remote = $Matches[1] }
        elseif ($line -match '^Jugador:') { Write-Host $line }
    }
    if (-not $remote) { throw 'El servidor no devolvió el archivo de acceso.' }
    $folder = Join-Path $accessDir (Split-Path (Split-Path $remote -Parent) -Leaf)
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $options = Get-SshOptions
    & scp.exe @options -q "root@$($server.ip):$remote" (Join-Path $folder 'lain-online.json')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo traer el archivo de acceso.' }
    Write-Host "Acceso de $AddPlayer guardado en $folder (privado: solo para esa persona)."
    if (-not $Packages) { Build-Package (Get-Item -LiteralPath $folder) }
}

if ($Packages) {
    if ($GameZip) { Import-GameZip $GameZip }
    if (Test-Path -LiteralPath $savedGame) {
        foreach ($access in (Get-ChildItem -LiteralPath $accessDir -Directory)) {
            if (Test-Path -LiteralPath (Join-Path $access.FullName 'lain-online.json')) { Build-Package $access }
        }
        Write-Host ''
        Write-Host "Manda a cada amigo SOLO su ZIP de $friendsDir, por privado."
    } else {
        Build-Package $null
    }
}

if ($Update) { Invoke-Server 'lain-update' }
if ($Status) { Invoke-Server 'lain-status' }
if ($Shell) { Invoke-Server '' -Interactive }
