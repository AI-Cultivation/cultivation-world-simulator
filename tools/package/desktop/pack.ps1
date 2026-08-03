param(
    [string]$BuildDesc = "",
    [switch]$SkipNpmInstall,
    [ValidateSet("generic", "epic")][string]$Distribution = "generic",
    [ValidateSet("dev", "live")][string]$EosEnv = "live",
    [switch]$RequireEosRuntime
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path
$PackageDir = Split-Path -Parent $ScriptDir
$DesktopSeedDir = $ScriptDir

function Get-GitTag {
    Push-Location $RepoRoot
    try {
        $tagDesc = & git describe --tags --abbrev=0 2>$null
        if ($LASTEXITCODE -eq 0 -and $tagDesc) {
            return $tagDesc.Trim()
        }
        throw "Cannot get git tag. Please run in a Git repository with at least one tag."
    }
    finally {
        Pop-Location
    }
}

function Assert-NoSensitiveConfigs {
    param(
        [Parameter(Mandatory = $true)][string]$RootPath
    )

    $SensitiveConfigNames = @("local_config.yml", "settings.json", "secrets.json")
    $MatchedFiles = Get-ChildItem -Path $RootPath -Include $SensitiveConfigNames -Recurse -Force -ErrorAction SilentlyContinue
    if ($MatchedFiles) {
        $List = ($MatchedFiles | ForEach-Object { $_.FullName }) -join "`n"
        throw "Sensitive config files remain in package:`n$List"
    }
}

function Import-EnvFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -match "^#" -or $line -eq "") { return }
        if ($line -match "^([^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            Set-Item -Path "Env:$key" -Value $value
        }
    }
}

function Write-DesktopSeedFile {
    param(
        [Parameter(Mandatory = $true)][string]$OutputPath
    )

    $SeedKeys = @(
        "CWS_DEFAULT_LLM_BASE_URL",
        "CWS_DEFAULT_LLM_MODEL",
        "CWS_DEFAULT_LLM_FAST_MODEL",
        "CWS_DEFAULT_LLM_API_FORMAT",
        "CWS_DEFAULT_LLM_MODE",
        "CWS_DEFAULT_LLM_MAX_CONCURRENT_REQUESTS",
        "CWS_DEFAULT_LLM_API_KEY"
    )

    $Seed = [ordered]@{}
    foreach ($Key in $SeedKeys) {
        $Value = [Environment]::GetEnvironmentVariable($Key)
        if ($Value) {
            $Seed[$Key] = $Value
        }
    }

    if ($Seed.Count -eq 0) {
        return $false
    }

    $Parent = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    $Json = $Seed | ConvertTo-Json -Depth 3
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($OutputPath, $Json, $utf8NoBom)
    return $true
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [Parameter(Mandatory = $true)]$Value
    )

    $Parent = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    $Json = $Value | ConvertTo-Json -Depth 8
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($OutputPath, $Json, $utf8NoBom)
}

function Get-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name
    )
    return [Environment]::GetEnvironmentVariable($Name)
}

function Resolve-EosDeploymentId {
    param(
        [Parameter(Mandatory = $true)][string]$EnvironmentName
    )

    $SpecificName = "EPIC_EOS_$($EnvironmentName.ToUpperInvariant())_DEPLOYMENT_ID"
    $SpecificValue = Get-EnvValue -Name $SpecificName
    if ($SpecificValue) {
        return $SpecificValue
    }
    return Get-EnvValue -Name "EPIC_EOS_DEPLOYMENT_ID"
}

function Write-DistributionManifest {
    param(
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [Parameter(Mandatory = $true)][string]$DistributionName,
        [Parameter(Mandatory = $true)][bool]$EpicEosMetricsEnabled
    )

    $Manifest = [ordered]@{
        distribution = $DistributionName
        features = [ordered]@{
            epicEosMetrics = $EpicEosMetricsEnabled
        }
    }
    Write-JsonFile -OutputPath $OutputPath -Value $Manifest
}

function Write-EosRuntimeFile {
    param(
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [Parameter(Mandatory = $true)][string]$EnvironmentName
    )

    $ProductId = Get-EnvValue -Name "EPIC_EOS_PRODUCT_ID"
    $SandboxId = Get-EnvValue -Name "EPIC_EOS_SANDBOX_ID"
    $DeploymentId = Resolve-EosDeploymentId -EnvironmentName $EnvironmentName
    $ClientId = Get-EnvValue -Name "EPIC_EOS_CLIENT_ID"
    $ClientSecret = Get-EnvValue -Name "EPIC_EOS_CLIENT_SECRET"

    $Missing = @()
    if (-not $ProductId) { $Missing += "EPIC_EOS_PRODUCT_ID" }
    if (-not $DeploymentId) { $Missing += "EPIC_EOS_DEPLOYMENT_ID" }
    if (-not $ClientId) { $Missing += "EPIC_EOS_CLIENT_ID" }
    if (-not $ClientSecret) { $Missing += "EPIC_EOS_CLIENT_SECRET" }

    if ($Missing.Count -gt 0) {
        return @{
            ok = $false
            missing = $Missing
        }
    }

    $Runtime = [ordered]@{
        environment = $EnvironmentName
        productId = $ProductId
        sandboxId = $SandboxId
        deploymentId = $DeploymentId
        clientId = $ClientId
        clientSecret = $ClientSecret
    }
    Write-JsonFile -OutputPath $OutputPath -Value $Runtime

    return @{
        ok = $true
        missing = @()
    }
}

$tag = Get-GitTag
if (-not $BuildDesc) {
    $BuildDesc = "$tag-desktop"
}

$DistRoot = Join-Path $RepoRoot ("tmp\" + $tag + "_desktop")
$BackendDistRoot = Join-Path $DistRoot "backend_dist"
$BackendBuildDir = Join-Path $RepoRoot ("tmp\build\" + $tag + "_desktop_backend")
$BackendSpecDir = Join-Path $RepoRoot ("tmp\spec\" + $tag + "_desktop_backend")
$ReleaseResourcesDir = Join-Path $RepoRoot ("tmp\build\" + $tag + "_release_resources")
$ReleaseResourcesReport = Join-Path $DistRoot "release-resource-report.json"
$ReleaseResourcesScript = Join-Path $PackageDir "release_resources.py"
$PackageSizeReportScript = Join-Path $PackageDir "package_size_report.py"
$SeedFile = Join-Path $DistRoot "desktop-seed.json"
$DistributionManifestFile = Join-Path $DistRoot "desktop-distribution.json"
$EosRuntimeFile = Join-Path $DistRoot "eos-runtime.json"
$ContentRootFile = Join-Path $RepoRoot "tmp\desktop_content_root.txt"

New-Item -ItemType Directory -Force -Path $DistRoot, $BackendDistRoot, $BackendBuildDir, $BackendSpecDir | Out-Null

Write-Host "Preparing shared release resources..." -ForegroundColor Cyan
& python $ReleaseResourcesScript --project-root $RepoRoot --output $ReleaseResourcesDir --report $ReleaseResourcesReport --markdown-report (Join-Path $DistRoot "release-resource-report.md")
if ($LASTEXITCODE -ne 0) {
    throw "Release resource staging failed."
}

Write-Host ">>> Desktop Electron package tag: $tag" -ForegroundColor Cyan
Write-Host ">>> Build desc: $BuildDesc" -ForegroundColor Cyan
Write-Host ">>> Distribution: $Distribution" -ForegroundColor Cyan
if ($Distribution -eq "epic") {
    Write-Host ">>> EOS environment: $EosEnv" -ForegroundColor Cyan
}

# Load optional private desktop/LLM settings. This file is ignored by git via *.env rules.
Import-EnvFile -Path (Join-Path $DesktopSeedDir "desktop_seed.env")
$HasSeed = Write-DesktopSeedFile -OutputPath $SeedFile
if ($HasSeed) {
    Write-Host "[OK] Prepared desktop private LLM seed file." -ForegroundColor Green
}
else {
    Write-Host "i No CWS_DEFAULT_LLM_* seed values found; building without private LLM seed." -ForegroundColor Yellow
}

$EosMetricsEnabled = $false
$EosHelperDir = $null
if ($Distribution -eq "epic") {
    Import-EnvFile -Path (Join-Path $PackageDir "epic\eos_runtime.env")
    $EosResult = Write-EosRuntimeFile -OutputPath $EosRuntimeFile -EnvironmentName $EosEnv
    $ConfiguredHelperDir = Get-EnvValue -Name "EPIC_EOS_HELPER_DIR"
    if ($ConfiguredHelperDir) {
        if (-not [System.IO.Path]::IsPathRooted($ConfiguredHelperDir)) {
            $ConfiguredHelperDir = Join-Path $RepoRoot $ConfiguredHelperDir
        }
        $EosHelperDir = $ConfiguredHelperDir
    }
    else {
        $EosHelperDir = Join-Path $RepoRoot "desktop-eos-helper\publish\win-x64"
    }

    $HelperExe = Join-Path $EosHelperDir "eos-helper.exe"
    if ($EosResult.ok -and (Test-Path $HelperExe)) {
        $EosMetricsEnabled = $true
        Write-Host "[OK] Prepared Epic EOS runtime config and helper." -ForegroundColor Green
    }
    else {
        $Reasons = @()
        if (-not $EosResult.ok) {
            $Reasons += "missing runtime values: $($EosResult.missing -join ', ')"
        }
        if (-not (Test-Path $HelperExe)) {
            $Reasons += "helper not found: $HelperExe"
        }
        $Message = "Epic EOS Metrics will be disabled for this package ($($Reasons -join '; '))."
        if ($RequireEosRuntime) {
            throw $Message
        }
        Write-Host $Message -ForegroundColor Yellow
        if (Test-Path $EosRuntimeFile) {
            Remove-Item -Path $EosRuntimeFile -Force
        }
    }
}
Write-DistributionManifest -OutputPath $DistributionManifestFile -DistributionName $Distribution -EpicEosMetricsEnabled $EosMetricsEnabled

# --- Web Frontend Build ---
$WebDir = Join-Path $RepoRoot "web"
$WebDistDir = Join-Path $WebDir "dist"

if (-not (Test-Path $WebDir)) {
    throw "Web directory not found at $WebDir"
}

Push-Location $WebDir
try {
    if (-not (Test-Path "node_modules") -and -not $SkipNpmInstall) {
        Write-Host "Installing web npm dependencies..."
        cmd /c "npm install"
    }
    $env:CWS_RELEASE_PUBLIC_DIR = Join-Path $ReleaseResourcesDir "public"
    Write-Host "Building web frontend from shared release resources..."
    cmd /c "npm run build"
    if ($LASTEXITCODE -ne 0) {
        throw "Web build failed."
    }
}
finally {
    Remove-Item Env:CWS_RELEASE_PUBLIC_DIR -ErrorAction SilentlyContinue
    Pop-Location
}

# --- Backend PyInstaller Build ---
$EntryPy = Join-Path $RepoRoot "src\server\main.py"
$AppName = "AICultivationSimulator_Backend"
$AssetsPath = Join-Path $ReleaseResourcesDir "assets"
$StaticPath = Join-Path $RepoRoot "static"
$IconPath = Join-Path $AssetsPath "icon.ico"
$RuntimeHookPath = Join-Path $PackageDir "runtime_hook_setcwd.py"

if (-not (Test-Path $EntryPy)) {
    throw "Entry script not found: $EntryPy"
}

$PyInstallerArgs = @(
    $EntryPy,
    "--name", $AppName,
    "--onedir",
    "--clean",
    "--noconfirm",
    "--windowed",
    "--distpath", $BackendDistRoot,
    "--workpath", $BackendBuildDir,
    "--specpath", $BackendSpecDir,
    "--paths", $RepoRoot,
    "--additional-hooks-dir", $PackageDir,
    "--add-data", "${AssetsPath};assets",
    "--add-data", "${StaticPath};static",
    "--exclude-module", "litellm",
    "--exclude-module", "google",
    "--exclude-module", "scipy",
    "--exclude-module", "pygame",
    "--exclude-module", "matplotlib",
    "--exclude-module", "tkinter",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "PySide2",
    "--exclude-module", "PySide6",
    "--exclude-module", "wx",
    "--exclude-module", "notebook",
    "--exclude-module", "ipython",
    "--exclude-module", "boto3",
    "--exclude-module", "botocore",
    "--exclude-module", "s3transfer",
    "--exclude-module", "azure",
    "--exclude-module", "huggingface_hub",
    "--exclude-module", "transformers",
    "--exclude-module", "tensorflow",
    "--exclude-module", "torch",
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "PIL",
    "--exclude-module", "Pillow",
    "--exclude-module", "tiktoken"
)

if (Test-Path $RuntimeHookPath) {
    $PyInstallerArgs += @("--runtime-hook", $RuntimeHookPath)
}
if (Test-Path $IconPath) {
    $PyInstallerArgs += @("--icon", $IconPath)
}

Push-Location $RepoRoot
try {
    Write-Host "Executing PyInstaller for desktop Electron backend..."
    & pyinstaller @PyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller execution failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$BackendExeDir = Join-Path $BackendDistRoot $AppName
if (-not (Test-Path $BackendExeDir)) {
    throw "Backend build finished but executable directory was not found: $BackendExeDir"
}

if (Test-Path $WebDistDir) {
    $DestWeb = Join-Path $BackendExeDir "web_static"
    if (Test-Path $DestWeb) {
        Remove-Item -Path $DestWeb -Recurse -Force
    }
    Copy-Item -Path $WebDistDir -Destination $DestWeb -Recurse -Force
}

Assert-NoSensitiveConfigs -RootPath $BackendExeDir
Write-Host "[OK] Verified backend package contains no local sensitive config files." -ForegroundColor Green

# --- Electron Build ---
$DesktopAppDir = Join-Path $RepoRoot "desktop"
if (-not (Test-Path $DesktopAppDir)) {
    throw "Desktop Electron directory not found: $DesktopAppDir"
}

Push-Location $DesktopAppDir
try {
    if (-not (Test-Path "node_modules") -and -not $SkipNpmInstall) {
        Write-Host "Installing desktop npm dependencies..."
        cmd /c "npm install"
    }

    $env:CWS_DESKTOP_BACKEND_DIR = $BackendExeDir
    $env:CWS_DESKTOP_DISTRIBUTION_MANIFEST = $DistributionManifestFile
    $env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
    if ($HasSeed) {
        $env:CWS_DESKTOP_SEED_FILE = $SeedFile
    }
    if ($EosMetricsEnabled) {
        $env:CWS_DESKTOP_EOS_RUNTIME_FILE = $EosRuntimeFile
        $env:CWS_DESKTOP_EOS_HELPER_DIR = $EosHelperDir
    }

    Write-Host "Building Electron desktop package..."
    cmd /c "npm run dist:desktop"
    if ($LASTEXITCODE -ne 0) {
        throw "Electron build failed."
    }
}
finally {
    Remove-Item Env:CWS_DESKTOP_BACKEND_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:CWS_DESKTOP_DISTRIBUTION_MANIFEST -ErrorAction SilentlyContinue
    Remove-Item Env:CWS_DESKTOP_SEED_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:CWS_DESKTOP_EOS_RUNTIME_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:CWS_DESKTOP_EOS_HELPER_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:CSC_IDENTITY_AUTO_DISCOVERY -ErrorAction SilentlyContinue
    Pop-Location
}

$ElectronOutput = Join-Path $DesktopAppDir "release\win-unpacked"
if (-not (Test-Path $ElectronOutput)) {
    throw "Electron unpacked output not found: $ElectronOutput"
}

$FinalContentRoot = Join-Path $DistRoot "win-unpacked"
if (Test-Path $FinalContentRoot) {
    Remove-Item -Path $FinalContentRoot -Recurse -Force
}
Copy-Item -Path $ElectronOutput -Destination $FinalContentRoot -Recurse -Force

Assert-NoSensitiveConfigs -RootPath $FinalContentRoot
$SourceMaps = Get-ChildItem -Path $FinalContentRoot -Include "*.map" -Recurse -Force -ErrorAction SilentlyContinue
if ($SourceMaps) {
    $List = ($SourceMaps | ForEach-Object { $_.FullName }) -join "`n"
    throw "Source maps remain in desktop Electron package:`n$List"
}
& python $PackageSizeReportScript --root $FinalContentRoot --output (Join-Path $DistRoot "package-size-report.json") --markdown-output (Join-Path $DistRoot "package-size-report.md")
if ($LASTEXITCODE -ne 0) {
    throw "Package size report generation failed."
}

$ResolvedContentRoot = (Resolve-Path $FinalContentRoot).Path
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($ContentRootFile, $ResolvedContentRoot, $utf8NoBom)

Write-Host "`n=== Desktop Electron package completed ===" -ForegroundColor Cyan
Write-Host "Content root: $ResolvedContentRoot"
Write-Host "Content root marker: $ContentRootFile"
Write-Host "Build desc: $BuildDesc"
Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  Publish Steam: powershell ./tools/package/publish_steam.ps1 -NoBuild"
Write-Host "  Prepare Epic:  powershell ./tools/package/publish_epic.ps1 -NoBuild"
