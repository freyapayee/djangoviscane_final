param([int]$Port = 5000)
$ErrorActionPreference = 'Stop'
$projectPython = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv-django\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Missing .venv-django. Follow WINDOWS_SETUP.md.'
}
Push-Location $PSScriptRoot
try {
    & $projectPython manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Django system check failed.' }
    & $projectPython manage.py migrate --check
    if ($LASTEXITCODE -ne 0) { throw 'Pending migrations. Run manage.py migrate before starting.' }
    & $projectPython manage.py runserver "127.0.0.1:$Port" --noreload
} finally {
    Pop-Location
}
