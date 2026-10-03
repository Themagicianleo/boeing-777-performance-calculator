# Prefer Codex's bundled Python; otherwise use an installed Python interpreter.
$labBundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (Test-Path -LiteralPath $labBundledPython) {
    $labPython = $labBundledPython
} else {
    $labCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $labCommand -or $labCommand.Source -like '*WindowsApps*') {
        throw 'Install Python 3.10 or newer, then run python b777_calculator.py --gui.'
    }
    $labPython = $labCommand.Source
}
& $labPython (Join-Path $PSScriptRoot 'b777_calculator.py') --gui @args
exit $LASTEXITCODE
