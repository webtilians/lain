@echo off
setlocal
rem Cambia solo la direccion del servidor en lain-online.json; el token del jugador no se toca.
set "JSON=%~dp0lain-online.json"
if not exist "%JSON%" (
  echo No encuentro lain-online.json junto a este archivo.
  echo Copia este .bat y tu lain-online.json en la carpeta donde esta LAIN.exe.
  pause
  exit /b 1
)
echo.
set /p "LAIN_URL=Pega la direccion que te ha pasado el anfitrion y pulsa Enter: "
powershell -NoProfile -ExecutionPolicy Bypass -Command "$u = $env:LAIN_URL.Trim().TrimEnd('/'); if ($u -notmatch '^https://[A-Za-z0-9.-]+$' -and $u -notmatch '^http://(localhost|127\.[0-9.]+|10\.[0-9.]+|192\.168\.[0-9.]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9.]+)(:[0-9]+)?$') { Write-Host ''; Write-Host 'Esa direccion no es valida. Debe empezar por https://'; exit 1 }; $j = Get-Content -LiteralPath $env:JSON -Raw | ConvertFrom-Json; $j.server_url = $u; [IO.File]::WriteAllText($env:JSON, ($j | ConvertTo-Json), (New-Object Text.UTF8Encoding $false)); Write-Host ''; Write-Host 'Listo. Ya puedes abrir LAIN.exe.'"
echo.
pause
