param(
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [switch]$Package
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$workRoot = Join-Path $repoRoot '.artifacts\pyinstaller'
$appName = 'RE-OSCR'
$appOutput = Join-Path $OutputRoot $appName
$versionSource = Get-Content -LiteralPath (Join-Path $repoRoot 'retro_escalation.py') -Raw
if ($versionSource -notmatch "__version__\s*=\s*'([^']+)'") {
    throw 'Could not determine the RE-OSCR version from retro_escalation.py.'
}
$version = $Matches[1]
$assetsData = "$(Join-Path $repoRoot 'assets');assets"
$localesData = "$(Join-Path $repoRoot 'locales');locales"
$themeAssetsData = "$(Join-Path $repoRoot 'theme_assets');theme_assets"
$iconPath = Join-Path $repoRoot 'assets\oscr_icon_small.ico'

# Capture source identity before PyInstaller creates or replaces any output files.
$commit = (& git -c "safe.directory=$($repoRoot.Replace('\', '/'))" -C $repoRoot rev-parse HEAD).Trim()
$workingTreeStatus = & git -c "safe.directory=$($repoRoot.Replace('\', '/'))" -C $repoRoot status --porcelain
$workingTree = if ([string]::IsNullOrWhiteSpace($workingTreeStatus)) {
    'clean'
}
else {
    'uncommitted changes included'
}

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
        --add-data $assetsData `
        --add-data $localesData `
        --add-data $themeAssetsData `
        --windowed `
        --icon $iconPath `
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
$docsOutput = Join-Path $appOutput 'docs'
$windowsGuideOutput = Join-Path $appOutput 'distribution\windows'
New-Item -ItemType Directory -Force -Path $docsOutput | Out-Null
New-Item -ItemType Directory -Force -Path $windowsGuideOutput | Out-Null
foreach ($document in @('PROJECT_SCOPE.md', 'TESTING.md', 'DEVELOPMENT.md')) {
    Copy-Item `
        -LiteralPath (Join-Path $repoRoot "docs\$document") `
        -Destination $docsOutput `
        -Force
}
$releaseNote = Join-Path $repoRoot "docs\releases\v$version.md"
if (Test-Path -LiteralPath $releaseNote -PathType Leaf) {
    Copy-Item -LiteralPath $releaseNote -Destination $docsOutput -Force
}
Copy-Item `
    -LiteralPath (Join-Path $repoRoot 'distribution\windows\README.md') `
    -Destination $windowsGuideOutput `
    -Force

$buildInfo = @"
RE-OSCR - Retro Escalation $version
Upstream GPLv3 frontend baseline: 11.1.0
Commit: $commit
Working tree: $workingTree
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
