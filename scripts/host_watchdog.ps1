# host_watchdog.ps1 - the stack's dead-man switch (2026-08-27, CEO-approved
# as a prerequisite of the autopilot program: "Agree lets get this in motion").
#
# WHY THIS EXISTS, measured twice: the full stack (Docker -> Postgres -> spine)
# was down for TWO DAYS (2026-08-24/26) and nobody knew until a session went
# looking; Docker died AGAIN within hours of that restart. An unattended
# trading loop on an unwatched host is a machine for discovering outages days
# late - and every hole in the record is a due-diligence question at the demo.
#
# WHAT IT DOES: bottom-up revival, infrastructure only. Docker Desktop ->
# krypton-pg -> the spine on :8090. It never touches orders, strategies,
# thresholds, or any control surface - it is plumbing, not policy.
#
# WHAT IT CANNOT SAVE, said loudly: live LEAN sessions are in-memory and DO
# NOT survive a spine restart. When this script revives the spine it logs that
# fact, so a vanished session reads as "the watchdog restarted the spine at
# HH:MM", never as a mystery. (Session persistence is the engine-machinery
# builder's job; until it lands, the watchdog plus the day's log is the
# honest state.)
#
# Registered as scheduled task "KryptonHostWatchdog", every 5 minutes.
# Remove with: schtasks /delete /tn KryptonHostWatchdog /f

$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\user\Documents\Krypton Fund\ClarkHarness"
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
$log = Join-Path $logDir "watchdog.log"

function Log([string]$msg) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss'Z'")
    Add-Content -Path $log -Value "$ts  $msg"
}

# --- 1. Is the spine well? If yes, exit silently (no log spam on health). ---
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8090/api/v1/fund/liveness" -UseBasicParsing -TimeoutSec 8
    if ($r.StatusCode -eq 200) { exit 0 }
} catch {}

Log "spine liveness FAILED - starting bottom-up revival"

# --- 2. Docker engine. -------------------------------------------------------
docker ps 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Log "docker engine down - starting Docker Desktop"
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    $up = $false
    foreach ($i in 1..40) {
        Start-Sleep -Seconds 3
        docker ps 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $up = $true; break }
    }
    if ($up) { Log "docker engine up after $($i*3)s" }
    else { Log "docker engine DID NOT come up in 120s - giving up this cycle"; exit 1 }
}

# --- 3. Postgres container. --------------------------------------------------
$pg = docker ps --format "{{.Names}}" | Select-String -SimpleMatch "krypton-pg"
if (-not $pg) {
    Log "krypton-pg not running - docker start krypton-pg"
    docker start krypton-pg 2>&1 | Out-Null
    Start-Sleep -Seconds 5
}

# --- 4. The spine. -----------------------------------------------------------
$listening = Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Log "spine not listening - starting uvicorn (NOTE: any live LEAN session did not survive; sessions are in-memory)"
    $env:FUND_STORE = "postgres"
    Start-Process -FilePath (Join-Path $root "venv\Scripts\python.exe") `
        -ArgumentList "-X","utf8","-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8090" `
        -WorkingDirectory $root -WindowStyle Hidden
    Start-Sleep -Seconds 12
}

try {
    $r = Invoke-WebRequest -Uri "http://localhost:8090/api/v1/fund/liveness" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -eq 200) { Log "revival COMPLETE - spine 200" }
    else { Log "spine answered $($r.StatusCode) after revival - NOT healthy" }
} catch {
    Log "spine still unreachable after revival attempt - will retry next cycle"
}
