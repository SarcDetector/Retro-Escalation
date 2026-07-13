param(
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [switch]$Package
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$workRoot = Join-Path $repoRoot '.artifacts\pyinstaller'
$appName = 'Retro-Escalation'
$appOutput = Join-Path $OutputRoot $appName
$version = '11.1.0-re.1-dev'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'The repository virtual environment is missing. Create .venv and install .[pyinst].'
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
New-Item -ItemType Directory -Force -Path $workRoot | Out-Null

Push-Location $repoRoot
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --name $appName `
        --distpath $OutputRoot `
        --workpath (Join-Path $workRoot 'work') `
        --specpath $workRoot `
        --add-data 'assets;assets' `
        --add-data 'locales;locales' `
        --add-data 'theme_assets;theme_assets' `
        --windowed `
        --icon 'assets\oscr_icon_small.ico' `
        'retro_escalation.py'
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Copy-Item -LiteralPath (Join-Path $repoRoot 'LICENSE') -Destination $appOutput -Force
Copy-Item -LiteralPath (Join-Path $repoRoot 'README.md') -Destination $appOutput -Force
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\TESTING.md') -Destination $appOutput -Force

$commit = (& git -c "safe.directory=$($repoRoot.Replace('\', '/'))" -C $repoRoot rev-parse HEAD).Trim()
$buildInfo = @"
Retro Escalation $version
OSCR-UI baseline: 11.1.0
Commit: $commit
Built: $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))

Experimental, unofficial community development build.
Settings are stored in the settings folder beside the executable.
"@
Set-Content -LiteralPath (Join-Path $appOutput 'BUILD_INFO.txt') -Value $buildInfo -Encoding utf8

if ($Package) {
    $zipPath = Join-Path $OutputRoot "$appName-$version-windows-x64.zip"
    Compress-Archive -LiteralPath $appOutput -DestinationPath $zipPath -CompressionLevel Optimal -Force
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$zipPath.sha256" -Value "$hash  $([System.IO.Path]::GetFileName($zipPath))" -Encoding ascii
    Write-Output "Package: $zipPath"
    Write-Output "SHA-256: $hash"
}

Write-Output "Application: $appOutput"
