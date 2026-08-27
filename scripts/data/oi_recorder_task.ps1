# oi_recorder_task.ps1 - the daily wrapper for scripts/data/oi_recorder.py.
#
# WHY A DAILY TASK AND NOT A NOTE IN A RUNBOOK: Binance serves
# futures/data/openInterestHist on a 30-DAY ROLLING WINDOW (measured
# 2026-08-27: period=1d&limit=500 returns 31 rows; startTime 60 days back is
# refused with code -1130). A day nobody polls is a day of history destroyed,
# and no amount of money buys it back later. This is the whole reason the job
# is scheduled rather than run when someone remembers.
#
# WHY IT IS SEPARATE FROM host_watchdog.ps1: the watchdog is PLUMBING - it
# revives Docker, Postgres and the spine and touches nothing else. This is
# RESEARCH collection. Folding a data pull into the dead-man switch would mean
# a data failure looks like an infrastructure failure, and an infrastructure
# revival waits on an HTTP call to a third party. Two jobs, two failure modes,
# two logs.
#
# THIS FILE IS ASCII ONLY, DELIBERATELY. powershell.exe reads an unmarked
# script as ANSI, so a single non-ASCII character (an em dash in a comment is
# the usual culprit) is enough to corrupt a scheduled run that works perfectly
# when pasted into a console. Measured on this host.
#
# WHAT IT WRITES: docs/research/data/oi/<SYMBOL>.jsonl, plus a run log at
# logs/oi_recorder.log. It never touches the event log, the NAV fold or any
# decision path - this is research data, not a fund fact.
#
# REGISTER (run once, from an elevated prompt; the chair does this, not the
# builder - a diff does not schedule itself):
#
#   schtasks /create /tn KryptonOIRecorder /sc daily /st 00:20 /f `
#     /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"C:\Users\user\Documents\Krypton Fund\ClarkHarness\scripts\data\oi_recorder_task.ps1`""
#
# 00:20 UTC-local is arbitrary but not accidental: it is well clear of the
# 00:00 daily boundary the 1d grid is stamped on, and the 1h grid this records
# reaches back 20.8 days per run, so a missed day repairs itself on the next
# one. That margin is the point - a daily job that only works if it runs every
# day is a daily job that will eventually lose data.
#
# VERIFY (any time, read-only):
#   python scripts\data\oi_recorder.py --verify
#
# REMOVE:
#   schtasks /delete /tn KryptonOIRecorder /f

$ErrorActionPreference = "Continue"
$root = "C:\Users\user\Documents\Krypton Fund\ClarkHarness"
$python = Join-Path $root "venv\Scripts\python.exe"
$script = Join-Path $root "scripts\data\oi_recorder.py"
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
$log = Join-Path $logDir "oi_recorder.log"

function Log([string]$msg) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss'Z'")
    Add-Content -Path $log -Value "$ts  $msg" -Encoding UTF8
}

if (-not (Test-Path $python)) { Log "ABSENT: $python - not run"; exit 2 }
if (-not (Test-Path $script)) { Log "ABSENT: $script - not run"; exit 2 }

# The recorder prints one line per symbol and exits non-zero when ANY symbol
# was unreadable or came back with a conflicting value. Both go to the log
# verbatim: a summary written by the wrapper would be a second opinion about
# something the recorder already decided.
$out = & $python -X utf8 $script 2>&1
$code = $LASTEXITCODE
foreach ($line in $out) { Log $line }

if ($code -eq 0) {
    Log "oi_recorder OK"
} else {
    # Loud, and it stays in the log. A collector that fails quietly on a
    # rolling window loses the exact days nobody was watching.
    Log "oi_recorder EXIT $code - at least one symbol was unreadable or restated a stored value; run 'python scripts\data\oi_recorder.py --verify' to see the coverage"
}
exit $code
