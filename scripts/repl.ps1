# Opens the SWI-Prolog interactive prompt with an example file loaded.
#
# Usage:  scripts\repl.cmd                    # loads examples/characters.pl
#         scripts\repl.cmd path/to/other.pl
#
# Quit with:  halt.

$ErrorActionPreference = "Stop"

$root   = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

# Ask the tool where SWI-Prolog is, so this finds it exactly the way the tool
# does: LOGICLAYER_SWIPL, then the standard install folder, then the PATH.
$binary = & $python -c "from logiclayer.engines.swipl import find_swipl; print(find_swipl() or '')"

if (-not $binary) {
    Write-Error "SWI-Prolog not found. Install it, or set LOGICLAYER_SWIPL to the full path of swipl.exe."
}

$file = if ($args.Count -gt 0) { $args[0] } else { Join-Path $root "examples\characters.pl" }

if (-not (Test-Path $file)) {
    Write-Error "No such file: $file"
}

Write-Host "Loading $file"
Write-Host "End every query with a full stop. Press ; for more answers. Type halt. to quit.`n"

& $binary $file
