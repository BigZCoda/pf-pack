# launch-viewer.ps1 -- the double-click start for the Brain Viewer (2026-09-29, Zak: "why can't we just make a desktop
# app for the viewer and it opens when I double click it?").
#
# What it does, in order: if nothing answers on the viewer's port, start serve.py --supervise hidden from the brain root
# and wait for it; then open the viewer in its own window (Edge or Chrome in app mode: no tabs, no address bar, the page
# is the window). Run twice and it only opens a second window; the server is never started twice (serve.py exits when
# the port already answers). The Desktop shortcut "Brain Viewer" points here.

$brain = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)     # skills/brain-viewer -> skills -> the brain root
$port = 8765
$url = "http://127.0.0.1:$port/"
$python = if (Test-Path 'C:\Python314\python.exe') { 'C:\Python314\python.exe' } else { 'python' }

function Answering {
  try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; return $r.StatusCode -eq 200 } catch { return $false }
}

if (-not (Answering)) {
  Start-Process -FilePath $python -ArgumentList 'skills\brain-viewer\serve.py', '--supervise' -WorkingDirectory $brain -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds(25)
  while (-not (Answering) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 400 }
}

$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$browser = if (Test-Path $edge) { $edge } elseif (Test-Path $chrome) { $chrome } else { $null }
$profile = Join-Path $env:LOCALAPPDATA 'BrainViewer\app-profile'     # its own profile: the window remembers its size and place, and no extensions load in it

if ($browser) {
  Start-Process -FilePath $browser -ArgumentList "--app=$url", "--user-data-dir=$profile", '--no-first-run', '--no-default-browser-check'
} else {
  Start-Process $url
}
