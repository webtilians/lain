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
    # Publish a version (e.g. 0.13.1): GitHub builds it, players update on launch.
    [string]$Publish = '',
    # Invite code for new accounts: ver · nuevo · abierto · cerrado · <código>
    [string]$Invite = '',
    # A new password for a player who forgot theirs.
    [string]$ResetPassword = '',
    # Opens the live server panel in your browser (through SSH; nothing public).
    [switch]$Panel,
    # Download a verified copy of the world to this PC; from then on, every day.
    [switch]$Backup,
    # With -Backup: the folder for the copies (remembered). Default: %LOCALAPPDATA%\LAIN\VPS\copias
    [string]$BackupFolder = '',
    # With -Backup: stop the daily copy.
    [switch]$NoDaily,
    # Put a copy from this PC back on the server: a date (2026-10-04) or "ultima".
    [string]$Restore = '',
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
$backupSetting = Join-Path $vpsDir 'backup-folder.txt'
$backupTask = 'LAIN copia del servidor'
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

function Get-Python {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python).Source }
    return $python
}

function Get-BackupFolder {
    if ($BackupFolder) {
        [IO.File]::WriteAllText($backupSetting, [IO.Path]::GetFullPath($BackupFolder), $utf8)
    }
    $folder = Join-Path $vpsDir 'copias'
    if (Test-Path -LiteralPath $backupSetting) { $folder = (Get-Content -LiteralPath $backupSetting -Raw).Trim() }
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    return $folder
}

function Get-BackupSets([string]$folder) {
    # One set per server copy: the world dump and, beside it, the access files.
    $sets = foreach ($dump in (Get-ChildItem -LiteralPath $folder -Filter 'online-world-*.sql.gz')) {
        $stamp = $dump.Name -replace '^online-world-(.+)\.sql\.gz$', '$1'
        if ($stamp -notmatch '^\d{4}-\d{2}-\d{2}(-\d{6})?$') { continue }
        $digits = ($stamp -replace '-', '').PadRight(14, '0')
        $access = Join-Path $folder "access-$stamp.tar.gz"
        [pscustomobject]@{
            Stamp = $stamp
            # The server names its copies in UTC; shown here in this PC's time.
            Time = [datetime]::SpecifyKind([datetime]::ParseExact($digits, 'yyyyMMddHHmmss', $null), 'Utc').ToLocalTime()
            Dump = $dump.FullName
            Access = $(if (Test-Path -LiteralPath $access) { $access } else { '' })
        }
    }
    return @($sets | Sort-Object Time)
}

function Test-Backup($set, [string]$target = '') {
    # Rebuilds the world from the copy in a fresh database; a copy that cannot be read is not a copy.
    $arguments = @((Join-Path $PSScriptRoot 'tools\check_backup.py'), $set.Dump)
    if ($set.Access) { $arguments += @('--access', $set.Access) }
    if ($target) { $arguments += @('--to', $target) }
    $result = (& (Get-Python) @arguments | Select-Object -Last 1) | ConvertFrom-Json
    if (-not $result.ok) { throw "La copia $($set.Stamp) está dañada: $($result.error)" }
    return $result
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

if ($Ip -or $Install -or $Gemini -or $Groq -or $Migrate -or $AddPlayer -or $Status -or $Update -or $Shell -or $Publish -or $ResetPassword -or $Invite -or $Panel -or $Backup -or $Restore) { $server = Get-Server }

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
    # Plain ASCII: a UTF-8 output encoding would prefix a byte order mark.
    $OutputEncoding = New-Object Text.ASCIIEncoding
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

if ($Publish) {
    if ($Publish -notmatch '^\d+\.\d+\.\d+$') { throw 'Usa una versión como 0.13.1' }
    $repo = 'webtilians/lain'
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    # Versions are published only from main: what players get is what main holds.
    if ($branch -ne 'main') { throw "Publica desde main (ahora estás en $branch). Fusiona tu rama en main con una PR y vuelve a intentarlo." }
    if (git status --porcelain --untracked-files=no) { throw 'Hay cambios sin guardar en git. Haz commit antes de publicar.' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Tu main local no coincide con el de GitHub. Actualízalo antes de publicar.' }
    git push origin $branch
    git tag "v$Publish"
    git push origin "v$Publish"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo subir la etiqueta de la versión.' }
    Write-Host "GitHub está compilando la versión $Publish (unos 20 minutos)..."
    $api = @{ 'User-Agent' = 'LAIN-vps'; 'Accept' = 'application/vnd.github+json' }
    $deadline = (Get-Date).AddMinutes(50)
    while ($true) {
        Start-Sleep -Seconds 45
        try {
            $release = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/tags/v$Publish" -Headers $api
            if ($release.assets.name -contains 'manifest.json') { break }
        } catch { }
        try {
            $runs = Invoke-RestMethod "https://api.github.com/repos/$repo/actions/runs?branch=v$Publish&per_page=1" -Headers $api
            $run = $runs.workflow_runs | Select-Object -First 1
            if ($run -and $run.status -eq 'completed' -and $run.conclusion -ne 'success') {
                throw "La compilación de GitHub falló: $($run.html_url)"
            }
        } catch [System.Net.WebException] { }
        if ((Get-Date) -gt $deadline) { throw 'GitHub tarda demasiado. Revisa la pestaña Actions del repositorio.' }
    }
    Write-Host "Versión $Publish publicada. Actualizando el servidor..."
    Invoke-Server "bash /opt/lain/deploy/vps/setup.sh --branch $branch"
    Write-Host ''
    Write-Host "Listo. Los jugadores recibirán la $Publish al abrir LAIN.exe."
    Write-Host "Descarga para gente nueva: https://$($server.host)"
}

if ($Panel) {
    # A private tunnel: your PC's port 8765 reaches the engine's own port on the server.
    $options = Get-SshOptions
    $tunnel = Start-Process ssh.exe -ArgumentList ($options + @('-N', '-L', '8765:127.0.0.1:8000', "root@$($server.ip)")) -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
    if ($tunnel.HasExited) { throw 'No se pudo abrir el túnel SSH con el servidor.' }
    Start-Process 'http://localhost:8765/admin'
    Write-Host 'Panel abierto en http://localhost:8765/admin (se actualiza cada 5 segundos).'
    Read-Host 'Pulsa Enter aquí para cerrar el panel'
    Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
}

if ($Backup) {
    $folder = Get-BackupFolder
    $log = Join-Path $folder 'copias.log'
    try {
        # A fresh copy now, then every server copy this PC does not have yet.
        Invoke-Server 'lain-backup' | ForEach-Object { Write-Host "Servidor: $_" }
        $wanted = @()
        foreach ($line in (Invoke-Server "find /var/backups/lain -maxdepth 1 -type f -name '*.gz' -printf '%f %s\n'")) {
            $name, $size = "$line".Split(' ')
            if ($name -notmatch '^(online-world-[\d-]+\.sql|access-[\d-]+\.tar)\.gz$') { continue }
            $local = Join-Path $folder $name
            if ((Test-Path -LiteralPath $local) -and (Get-Item -LiteralPath $local).Length -eq [long]$size) { continue }
            $wanted += $name
        }
        if ($wanted) {
            $options = Get-SshOptions
            $sources = $wanted | ForEach-Object { "root@$($server.ip):/var/backups/lain/$_" }
            & scp.exe @options -q -p @sources $folder
            if ($LASTEXITCODE -ne 0) { throw 'No se pudieron descargar las copias del servidor.' }
        }
        $sets = Get-BackupSets $folder
        if (-not $sets) { throw 'El servidor no tiene ninguna copia del mundo todavía.' }
        $latest = $sets[-1]
        # Every new copy is rebuilt and read back; the newest one always.
        foreach ($set in $sets) {
            if ($set -ne $latest -and $wanted -contains (Split-Path $set.Dump -Leaf)) { Test-Backup $set | Out-Null }
        }
        $result = Test-Backup $latest
        Invoke-Server 'lain-backup --downloaded'
        $summary = "Copia del $($latest.Time.ToString('yyyy-MM-dd HH:mm')) verificada: $($result.players) jugadores, $($result.accounts) cuentas, minuto $($result.minute) del mundo"
        if ($latest.Access) { $summary += ", $($result.access) accesos" }
        # Every copy from the last 30 days; before that, the newest of each month.
        $limit = (Get-Date).AddDays(-30)
        $months = @{}
        foreach ($set in ($sets | Sort-Object Time -Descending)) {
            if ($set.Time -ge $limit) { continue }
            $month = $set.Time.ToString('yyyy-MM')
            if ($months.ContainsKey($month)) {
                Remove-Item -LiteralPath $set.Dump -Force
                if ($set.Access) { Remove-Item -LiteralPath $set.Access -Force }
            } else { $months[$month] = $true }
        }
        Write-Host "$summary."
        Write-Host "Copias en $folder ($(@(Get-BackupSets $folder).Count) en total)."
        Add-Content -LiteralPath $log -Encoding UTF8 -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm') OK $summary"
    } catch {
        Add-Content -LiteralPath $log -Encoding UTF8 -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm') ERROR $($_.Exception.Message)"
        throw
    }
    if ($NoDaily) {
        Unregister-ScheduledTask -TaskName $backupTask -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host 'Copia diaria desactivada.'
    } elseif (-not (Get-ScheduledTask -TaskName $backupTask -ErrorAction SilentlyContinue)) {
        # Only while you are signed in; if the PC was off at 13:00 it runs as soon as it is on.
        $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -File `"$PSCommandPath`" -Backup"
        $trigger = New-ScheduledTaskTrigger -Daily -At '13:00'
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
        Register-ScheduledTask -TaskName $backupTask -Description 'Descarga y comprueba una copia del mundo de LAIN (vps.ps1 -Backup).' -Action $action -Trigger $trigger -Settings $settings | Out-Null
        Write-Host 'Copia diaria programada: cada día a las 13:00, o al encender el PC si estaba apagado.'
        Write-Host 'Para quitarla: .\vps.ps1 -Backup -NoDaily'
    }
}

if ($Restore) {
    $folder = Get-BackupFolder
    $sets = Get-BackupSets $folder
    if (-not $sets) { throw "No hay copias en $folder. Haz una con: .\vps.ps1 -Backup" }
    if ($Restore -in 'ultima', 'última', 'latest') { $set = $sets[-1] }
    else { $set = $sets | Where-Object { $_.Stamp.StartsWith($Restore) } | Select-Object -Last 1 }
    if (-not $set) { throw "No hay ninguna copia de $Restore. Las últimas: $(($sets | Select-Object -Last 5 | ForEach-Object { $_.Stamp }) -join ', ')" }
    $restored = Join-Path $env:TEMP 'lain-import.db'
    $check = Test-Backup $set $restored
    Write-Host "Copia del $($set.Time.ToString('yyyy-MM-dd HH:mm')): $($check.players) jugadores, minuto $($check.minute) del mundo."
    Write-Host 'Sustituye el mundo del servidor por esta copia. El mundo actual se guarda antes en /var/backups/lain.'
    if ((Read-Host 'Escribe RESTAURAR para seguir') -cne 'RESTAURAR') {
        Remove-Item -LiteralPath $restored -Force
        throw 'Cancelado: no he cambiado nada.'
    }
    Invoke-Server 'rm -rf /root/lain-import.db /root/lain-import-access /root/lain-import-access.tar.gz'
    Copy-ToServer $restored '/root/lain-import.db'
    Remove-Item -LiteralPath $restored -Force
    if ($set.Access) {
        Copy-ToServer $set.Access '/root/lain-import-access.tar.gz'
        Invoke-Server 'install -d -m 700 /root/lain-import-access && tar -C /root/lain-import-access --strip-components=1 -xzf /root/lain-import-access.tar.gz && rm /root/lain-import-access.tar.gz'
    }
    # Checks the copy, saves the current world, swaps them and restarts the engine.
    Invoke-Server 'lain-import-world'
    Write-Host "Mundo restaurado desde la copia del $($set.Time.ToString('yyyy-MM-dd HH:mm'))."
}

if ($Invite) {
    if ($Invite -notmatch '^[\p{L}\p{N}_-]{3,40}$') { throw 'Usa: ver, nuevo, abierto, cerrado o un código de letras, números y guiones.' }
    Invoke-Server ('lain-signup ' + $(if ($Invite -eq 'ver') { '' } else { $Invite }))
}

if ($ResetPassword) {
    if ($ResetPassword -notmatch '^[\p{L}\p{N} _-]{3,16}$') { throw 'Ese nombre no es válido.' }
    Invoke-Server ("lain-reset-password '" + $ResetPassword + "'")
}

if ($Update) { Invoke-Server 'lain-update' }
if ($Status) { Invoke-Server 'lain-status' }
if ($Shell) { Invoke-Server '' -Interactive }
