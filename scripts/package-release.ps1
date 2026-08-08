param(
    [string]$Version = "v0.1.0",
    [string]$OutputDir = "release"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path
$Output = Join-Path $Root $OutputDir
$Stage = Join-Path ([System.IO.Path]::GetTempPath()) ("QQBot-" + [guid]::NewGuid().ToString("N"))
$PackageRoot = Join-Path $Stage ("QQBot-" + $Version)

if (-not (Test-Path (Join-Path $Root "NapCat.Shell\NapCatWinBootMain.exe"))) {
    throw "NapCat.Shell is incomplete. Add the NapCat runtime before packaging."
}

New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null
try {
    $tracked = @(git -C $Root -c core.quotePath=false ls-files -co --exclude-standard)
    if ($LASTEXITCODE -ne 0 -or $tracked.Count -eq 0) { throw "Could not list distributable Git files." }

    foreach ($relative in $tracked) {
        $source = Join-Path $Root $relative
        $destination = Join-Path $PackageRoot $relative
        $parent = Split-Path $destination -Parent
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }

    $forbidden = Get-ChildItem $PackageRoot -Recurse -Force -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -match "\\(config|cache|logs)\\" -or
            ($_.Name -eq ".env") -or
            ($_.Name -like ".env.*" -and $_.Name -notlike "*.example")
        }
    if ($forbidden) { throw "Local configuration or runtime files found in package: $($forbidden.FullName -join ', ')" }

    New-Item -ItemType Directory -Force -Path $Output | Out-Null
    $Zip = Join-Path $Output ("QQBot-" + $Version + ".zip")
    if (Test-Path $Zip) { Remove-Item -LiteralPath $Zip -Force }
    Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -CompressionLevel Optimal
    Write-Host "Created: $Zip" -ForegroundColor Green
}
finally {
    if (Test-Path $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
}
