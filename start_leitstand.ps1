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

# Reste alter Umbenenn-Versuche entfernen, falls noch vorhanden.
# Zwei Fallen, beide am 04.08.2026 aufgefallen:
#
#  1. Windows kann diese Ordner nicht loeschen, weil eine engine.sock darin
#     liegt - derselbe AF_UNIX-Reparse-Point wie oben ("Das System kann auf die
#     Datei nicht zugreifen"). Remove-Item scheiterte deshalb bei JEDEM Start.
#     Loesung ist dieselbe wie oben: WSL kann es.
#  2. Im catch-Block ist $_ das FEHLEROBJEKT, nicht der Ordner aus der Pipeline.
#     Die Meldung "bleibt liegen:" kam dadurch ohne Namen - man sah, dass etwas
#     klemmt, aber nicht was. Der Ordner wird jetzt vorher festgehalten.
foreach ($basis in @("$env:LOCALAPPDATA", "$env:LOCALAPPDATA\Docker")) {
    Get-ChildItem $basis -Directory -Filter "*_alt_*" -ErrorAction SilentlyContinue | ForEach-Object {
        $ordner = $_
        try {
            Remove-Item $ordner.FullName -Recurse -Force -ErrorAction Stop
            Write-Host "  geloescht: $($ordner.Name)"
        }
        catch {
            $wsl = "/mnt/" + $ordner.FullName.Substring(0, 1).ToLower() +
                   $ordner.FullName.Substring(2).Replace("\", "/")
            wsl -d Ubuntu -e rm -rf $wsl 2>&1 | Out-Null
            if (Test-Path $ordner.FullName) {
                # Harmlos, nur nicht wegzubekommen: Diese Ordner enthalten eine
                # 0-Byte-engine.sock als Reparse-Point. Windows kommt nicht ran,
                # und WSL SIEHT den Ordner nicht einmal (04.08.2026 geprueft:
                # `ls` in AppData/Local listet ihn nicht, obwohl Windows ihn
                # zeigt). Kein Grund zur Warnfarbe - Docker startet damit.
                Write-Host "  bleibt liegen (harmlos, 0 Byte): $($ordner.Name)" -ForegroundColor DarkGray
            } else {
                Write-Host "  geloescht via WSL: $($ordner.Name)"
            }
        }
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

# 3) Stack hochfahren - IMMER mit --build.
#    Der Code haengt NICHT als Volume im Container; das Dockerfile backt ihn mit
#    `COPY . .` ins Image. Ohne --build startet der Stack den Stand des letzten
#    Builds, waehrend im Projektordner laengst neuer Code liegt - und das faellt
#    erst auf, wenn ein Clip anders aussieht als erwartet oder ein Fix scheinbar
#    nicht wirkt. Genau deshalb steht --build hier fest drin.
#    Kostet kaum Zeit: apt-get und pip haengen an fruehereren Schichten und
#    bleiben im Cache, solange requirements.txt unveraendert ist. Neu laeuft nur
#    das COPY.
Write-Host "== Blaulicht-Stack (Image wird neu gebaut) ==" -ForegroundColor Cyan
Push-Location $projekt
& $docker compose up -d --build
$startCode = $LASTEXITCODE
& $docker compose ps
Pop-Location

# Ohne diese Pruefung meldete das Skript auch nach einem fehlgeschlagenen Build
# "Leitstand: http://localhost:8000" - und man sucht den Fehler an der falschen
# Stelle.
if ($startCode -ne 0) {
    Write-Host "`nBuild oder Start fehlgeschlagen (Exit $startCode)." -ForegroundColor Red
    Write-Host "Letzte Zeilen des Build-Logs oben pruefen; danach:" -ForegroundColor Yellow
    Write-Host "  docker compose logs --tail 50" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nLeitstand: http://localhost:8000" -ForegroundColor Green
