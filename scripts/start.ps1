param(
    [switch]$NoNapCat
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
$BotDir = Join-Path $Root "qq-video-bot"
$NapCatDir = Join-Path $Root "NapCat.Shell"

if (-not (Test-Path (Join-Path $BotDir ".env.prod"))) {
    throw "The project is not initialized. Run scripts\setup.ps1 first."
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install uv first."
}

Start-Process -FilePath "cmd.exe" -WorkingDirectory $BotDir -ArgumentList @("/k", "uv run python bot.py")

if (-not $NoNapCat) {
    $Launcher = Join-Path $NapCatDir "launcher-user.bat"
    if (-not (Test-Path $Launcher)) {
        throw "NapCat.Shell\launcher-user.bat is missing. Download the complete Release ZIP."
    }
    Start-Process -FilePath "cmd.exe" -WorkingDirectory $NapCatDir -ArgumentList @("/k", "launcher-user.bat")
}

$Components = if ($NoNapCat) { "NoneBot" } else { "NoneBot and NapCat" }
Write-Host "$Components started. Keep the new windows open." -ForegroundColor Green
