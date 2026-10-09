<#
  Start the Stock Analysis Engine: the API (port 8000) and the dashboard (port 5173).

  The first run sets everything up: a Python environment with the packages in
  requirements.txt, and the website's packages. Later runs start straight away.

  Usage (Windows):  double-click start.cmd, or run .\start.cmd in a terminal.
  Stop:             press Ctrl+C in this window (it also closes the API window).
#>

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

function Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Fail($message) { Write-Host "`n$message" -ForegroundColor Red; exit 1 }

# 1. Python environment (first run only)
if (-not (Test-Path $py)) {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $python) { Fail 'Python 3.12 or newer is required: https://www.python.org/downloads/ (tick "Add python.exe to PATH").' }
  Step 'First run: creating the Python environment in .venv'
  & python -m venv .venv
  if ($LASTEXITCODE -ne 0) { Fail 'Could not create the Python environment.' }
  Step 'Installing Python packages (this takes several minutes the first time)'
  & $py -m pip install --upgrade pip
  & $py -m pip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) { Fail 'Installing the Python packages failed; see the messages above.' }
}

# 2. Website packages (first run only)
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail 'Node.js 20.19 or newer is required: https://nodejs.org/' }
if (-not (Test-Path 'frontend\node_modules')) {
  Step 'First run: installing the website packages'
  & npm --prefix frontend install
  if ($LASTEXITCODE -ne 0) { Fail 'Installing the website packages failed; see the messages above.' }
}

# 3. Both ports must be free
foreach ($port in 8000, 5173) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    Fail "Port $port is already in use, probably by an earlier run. Close that window (or press Ctrl+C in it) and try again."
  }
}

# 4. The local AI model is optional
try {
  Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null
  Write-Host "`nOllama is running: news tagging and the AI thesis are available." -ForegroundColor Green
} catch {
  Write-Host "`nOllama is not running: everything works except news tagging and the AI thesis." -ForegroundColor Yellow
  Write-Host 'To enable them, install Ollama (https://ollama.com), run "ollama pull qwen2.5:7b-instruct", then restart this script.' -ForegroundColor Yellow
}

# 5. API in its own window, so its log stays readable
Step 'Starting the API on http://localhost:8000 (in a separate window)'
$api = Start-Process -FilePath $py -ArgumentList '-m', 'uvicorn', 'src.api.main:app', '--port', '8000' -WorkingDirectory $PSScriptRoot -PassThru

# 6. Open the browser once the website answers
Start-Job -ScriptBlock {
  for ($i = 0; $i -lt 90; $i++) {
    try {
      Invoke-WebRequest 'http://localhost:5173' -UseBasicParsing -TimeoutSec 1 | Out-Null
      Start-Process 'http://localhost:5173'
      break
    } catch { Start-Sleep -Seconds 1 }
  }
} | Out-Null

# 7. Website in this window; stopping it also stops the API
Step 'Starting the website on http://localhost:5173 (press Ctrl+C to stop everything)'
try {
  & npm --prefix frontend run dev
} finally {
  if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
  Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue
}
