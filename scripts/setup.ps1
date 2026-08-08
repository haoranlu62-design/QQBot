param(
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
$BotDir = Join-Path $Root "qq-video-bot"
$ParserCache = (Join-Path $Root "nonebot-plugin-parser\cache") -replace "\\", "/"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install uv and reopen PowerShell: https://docs.astral.sh/uv/getting-started/installation/"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg was not found. Install ffmpeg and add it to PATH before processing videos."
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "nonebot-plugin-parser\cache") | Out-Null

$EnvFile = Join-Path $BotDir ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $BotDir ".env.example") $EnvFile
}

$ProdExample = Join-Path $BotDir ".env.prod.example"
$ProdFile = Join-Path $BotDir ".env.prod"
if (-not (Test-Path $ProdFile)) {
    $ProdText = Get-Content -Raw -Encoding UTF8 $ProdExample
    $ProdText = [regex]::Replace(
        $ProdText,
        "(?m)^LOCALSTORE_PLUGIN_CACHE_DIR=.*$",
        "LOCALSTORE_PLUGIN_CACHE_DIR={`"nonebot_plugin_parser`":`"$ParserCache`"}"
    )
    Set-Content -Path $ProdFile -Value $ProdText -Encoding UTF8
}

if (-not $SkipSync) {
    Push-Location $BotDir
    try {
        & uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit code $LASTEXITCODE." }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Setup complete. Run scripts\start.ps1 or double-click the start batch file." -ForegroundColor Green
