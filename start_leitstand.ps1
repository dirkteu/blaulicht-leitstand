# start_leitstand.ps1 - Docker Desktop + Blaulicht-Stack hochfahren
# Angelegt 2026-07-28 nach dem Socket-Problem (verwaiste AF_UNIX-Sockets nach Hart-Beendigung).

$ErrorActionPreference = "Continue"
$docker  = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$projekt = "C:\Users\Dirk\Desktop\blaulicht"

# 1) Verwaiste Sockets wegraeumen - SONST STARTET DOCKER NICHT.
#    Windows kann diese AF_UNIX-Reparse-Points nicht loeschen ("The file cannot be
#    accessed by the system"), WSL dagegen schon. Das ersetzt den frueher noetigen Reboot.
Write-Host "== Verwaiste Sockets wegraeumen ==" -ForegroundColor Cyan
$sockets = @(
    "/mnt/c/Users/Dirk/AppData/Local/Docker/run/dockerInference",
    "/mnt/c/Users/Dirk/AppData/Local/Docker/run/dockerEthernetVfkit",
    "/mnt/c/Users/Dirk/AppData/Local/Docker/run/userAnalyticsOtlpHttp.sock",
    "/mnt/c/Users/Dirk/AppData/Local/docker-secrets-engine/engine.sock"
)
foreach ($s in $sockets) { wsl -d Ubuntu -e rm -f $s 2>&1 | Out-Null }
Write-Host "  erledigt (via WSL)"

# Reste alter Umbenenn-Versuche entfernen, falls noch vorhanden
foreach ($basis in @("$env:LOCALAPPDATA", "$env:LOCALAPPDATA\Docker")) {
    Get-ChildItem $basis -Directory -Filter "*_alt_*" -ErrorAction SilentlyContinue | ForEach-Object {
        try { Remove-Item $_.FullName -Recurse -Force -ErrorAction Stop; Write-Host "  geloescht: $($_.Name)" }
        catch { Write-Host "  bleibt liegen: $($_.Name)" -ForegroundColor Yellow }
    }
}

# 2) Docker Desktop starten und auf die Engine warten
Write-Host "== Docker Desktop ==" -ForegroundColor Cyan
if (-not (Get-Process | Where-Object { $_.Name -like "*ocker*" })) { Start-Process $desktop }
$bereit = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 5
    $v = & $docker version --format "{{.Server.Version}}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $v) { Write-Host "  Engine bereit: Docker $v" -ForegroundColor Green; $bereit = $true; break }
}
if (-not $bereit) {
    Write-Host "  Engine kam nicht hoch. Letzter Absturzgrund:" -ForegroundColor Red
    Get-Content "$env:LOCALAPPDATA\Docker\log\host\com.docker.backend.exe.log" |
        Select-String 'backend crashed' | Select-Object -Last 1 | ForEach-Object { $_.Line }
    exit 1
}

# 3) Stack hochfahren (--build nur noetig, wenn sich Code/Dockerfile geaendert hat)
Write-Host "== Blaulicht-Stack ==" -ForegroundColor Cyan
Push-Location $projekt
& $docker compose up -d
& $docker compose ps
Pop-Location

Write-Host "`nLeitstand: http://localhost:8000" -ForegroundColor Green
