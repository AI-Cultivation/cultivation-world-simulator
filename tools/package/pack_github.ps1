$ErrorActionPreference = "Stop"

# Locate repository root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

# Get Git TAG (only the tag name, without commit hash or dirty flag)
$tag = ""
Push-Location $RepoRoot

# Get the most recent tag name
$tagDesc = & git describe --tags --abbrev=0 2>$null
if ($LASTEXITCODE -eq 0 -and $tagDesc) {
    $tag = $tagDesc.Trim()
}

Pop-Location

if (-not $tag) {
    Write-Error "Cannot get git tag. Please run in a Git repository with at least one tag."
    exit 1
}

# Paths and directories (Use _github suffix to differentiate)
$DistDir = Join-Path $RepoRoot ("tmp\" + $tag + "_github")
$BuildDir = Join-Path $RepoRoot ("tmp\build\" + $tag + "_github")
$SpecDir = Join-Path $RepoRoot ("tmp\spec\" + $tag + "_github")
$ReleaseResourcesDir = Join-Path $RepoRoot ("tmp\build\" + $tag + "_release_resources")
$ReleaseResourcesReport = Join-Path $DistDir "release-resource-report.json"
$ReleaseResourcesScript = Join-Path $ScriptDir "release_resources.py"
$PackageSizeReportScript = Join-Path $ScriptDir "package_size_report.py"
$GitHubBuildMarker = Join-Path $RepoRoot "tmp\github_build_dir.txt"
New-Item -ItemType Directory -Force -Path $DistDir, $BuildDir, $SpecDir | Out-Null

Write-Host "Preparing shared release resources..." -ForegroundColor Cyan
& python $ReleaseResourcesScript --project-root $RepoRoot --output $ReleaseResourcesDir --report $ReleaseResourcesReport --markdown-report (Join-Path $DistDir "release-resource-report.md")
if ($LASTEXITCODE -ne 0) {
    throw "Release resource staging failed."
}

# --- Web Frontend Build ---
$WebDir = Join-Path $RepoRoot "web"
$WebDistDir = Join-Path $WebDir "dist"

Write-Host "Checking Web Frontend..." -ForegroundColor Cyan
if (Test-Path $WebDir) {
    Push-Location $WebDir
    try {
        if (-not (Test-Path "node_modules")) {
            Write-Host "Installing npm dependencies..."
            # Use cmd /c to ensure npm is found on Windows
            cmd /c "npm install"
        }
        $env:CWS_RELEASE_PUBLIC_DIR = Join-Path $ReleaseResourcesDir "public"
        Write-Host "Building web frontend from shared release resources..."
        cmd /c "npm run build"
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Web build failed."
            exit 1
        }
    } catch {
        Write-Error "Web build process failed: $_"
        exit 1
    } finally {
        Remove-Item Env:CWS_RELEASE_PUBLIC_DIR -ErrorAction SilentlyContinue
        Pop-Location
    }
} else {
    Write-Error "Web directory not found at $WebDir"
    exit 1
}

# Entry and app name
$EntryPy = Join-Path $RepoRoot "src\server\main.py"
$AppName = "AICultivationSimulator_WebMode"

if (-not (Test-Path $EntryPy)) {
    Write-Error "Entry script not found: $EntryPy"
    exit 1
}

# Assets and static paths
$AssetsPath = Join-Path $ReleaseResourcesDir "assets"
$StaticPath = Join-Path $RepoRoot "static"

# Icon path
$IconPath = Join-Path $AssetsPath "icon.ico"

# Runtime hook
$RuntimeHookPath = Join-Path $ScriptDir "runtime_hook_setcwd.py"

# Additional hooks directory
$AdditionalHooksPath = $ScriptDir

# Source path
$SrcPath = Join-Path $RepoRoot "src"

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

# Assemble PyInstaller arguments
$argsList = @(
    $EntryPy,
    "--name", $AppName,
    "--onedir",
    "--clean",
    "--noconfirm",
    # Keep the executable windowless while the Python process opens the system browser.
    "--windowed",
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--specpath", $SpecDir,
    "--paths", $RepoRoot,
    "--additional-hooks-dir", $AdditionalHooksPath,
    
    # Data Files
    "--add-data", "${AssetsPath};assets",       # Game Assets (Images) -> _internal/assets
    "--add-data", "${StaticPath};static",       # Configs -> _internal/static (backup)
    
    # Excludes
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
    $argsList += @("--runtime-hook", $RuntimeHookPath)
}

# Add icon if available
if (Test-Path $IconPath) {
    $argsList += @("--icon", $IconPath)
}

# Call PyInstaller
Push-Location $RepoRoot
try {
    Write-Host "Executing PyInstaller for GitHub Release..."
    & pyinstaller @argsList
    
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller execution failed with exit code $LASTEXITCODE. Please check the error logs above."
    }
    $BuildSuccess = $true
} catch {
    Write-Error "Build failed: $_"
    exit 1
} finally {
    Pop-Location
    
    if ($BuildSuccess) {
        Write-Host "`n=== Post-build processing ===" -ForegroundColor Green
        
        $ExeDir = Join-Path $DistDir $AppName
        
        if (Test-Path $ExeDir) {        
            if (Test-Path $WebDistDir) {
                 $DestWeb = Join-Path $ExeDir "web_static"
                 Copy-Item -Path $WebDistDir -Destination $DestWeb -Recurse -Force
                 Write-Host "✓ Copied web_dist to web_static in exe directory" -ForegroundColor Green
            }

            Assert-NoSensitiveConfigs -RootPath $ExeDir
            Write-Host "✓ Verified package contains no sensitive config files" -ForegroundColor Green
            & python $PackageSizeReportScript --root $ExeDir --output (Join-Path $DistDir "package-size-report.json") --markdown-output (Join-Path $DistDir "package-size-report.md")
            if ($LASTEXITCODE -ne 0) {
                throw "Package size report generation failed."
            }
            
            $BuildDirRoot = Join-Path $RepoRoot "tmp\build"
            if (Test-Path $BuildDirRoot) {
                Remove-Item -Path $BuildDirRoot -Recurse -Force
                Write-Host "✓ Deleted entire build directory: $BuildDirRoot" -ForegroundColor Green
            }
            
            Write-Host "`n=== Package completed for GitHub Release ===" -ForegroundColor Cyan
            Write-Host "Distribution directory: " (Resolve-Path $DistDir).Path
            if (Test-Path $ExeDir) {
                $ResolvedExeDir = (Resolve-Path $ExeDir).Path
                $utf8NoBom = New-Object System.Text.UTF8Encoding $false
                [System.IO.File]::WriteAllText($GitHubBuildMarker, $ResolvedExeDir, $utf8NoBom)
                Write-Host "Executable directory: " $ResolvedExeDir
                Write-Host "Build marker: " $GitHubBuildMarker
            }
            Write-Host ""
            Write-Host "Next:" -ForegroundColor Cyan
            Write-Host "  Compress: powershell ./tools/package/compress.ps1"
            Write-Host "  Publish:  powershell ./tools/package/publish_github.ps1 -NoBuild"
        } else {
             Write-Error "Build finished but executable directory not found at $ExeDir"
        }
    } else {
        Write-Warning "Build failed. Keeping build directory for debugging."
    }
}
