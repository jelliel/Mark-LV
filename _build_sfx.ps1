# Build THEOLOGICUS SFX Installer
$repo = "C:\Users\toshr\AppData\Local\Programs\MarkLV"
Set-Location $repo

$pkgDir = "$repo\_installer_pkg"
$zipPath = "$repo\_temp_installer.zip"
$outExe = "$repo\THEOLOGICUS-v1.0.8-Setup.exe"
$sfxModule = "C:\Program Files\7-Zip\7z.sfx"

# Clean previous
if (Test-Path $outExe) { Remove-Item $outExe -Force }
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
if (Test-Path $pkgDir) { Remove-Item $pkgDir -Recurse -Force }
New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null

# Copy files (skip large/build dirs)
$skip = @('dist','build','.git','__pycache__','_installer_pkg','.claude','.venv','node_modules','_build_sfx.py','_temp_installer.zip')
Get-ChildItem $repo -Directory | Where-Object { $_.Name -notin $skip } | ForEach-Object {
    $dest = Join-Path $pkgDir $_.Name
    if (-not (Test-Path $dest)) { Copy-Item $_.FullName $dest -Recurse -Force }
}
Get-ChildItem $repo -File | Where-Object { $_.Name -notin $skip } | ForEach-Object {
    Copy-Item $_.FullName $pkgDir -Force
}

# Write SFX config
$configContent = @'
;!@Install@!UTF-8!
Title="THEOLOGICUS v1.0.9"
BeginPrompt="Theologicus Installation"
ExtractDialogText="Extracting files..."
ExtractTimeout=600
GUIMode="0"
;!@InstallEnd@!
'@
$configPath = "$pkgDir\config.cfg"
[System.IO.File]::WriteAllText($configPath, $configContent, [System.Text.Encoding]::Unicode)

# Create ZIP
Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force

$zipSize = (Get-Item $zipPath).Length / 1KB
Write-Host "ZIP: $([math]::Round($zipSize, 1)) KB"

# Concatenate: SFX module + config + ZIP
$sfxBytes = [System.IO.File]::ReadAllBytes($sfxModule)
$configBytes = [System.IO.File]::ReadAllBytes($configPath)
$zipBytes = [System.IO.File]::ReadAllBytes($zipPath)

$allBytes = New-Object byte[] ($sfxBytes.Length + $configBytes.Length + $zipBytes.Length)
[System.Buffer]::BlockCopy($sfxBytes, 0, $allBytes, 0, $sfxBytes.Length)
[System.Buffer]::BlockCopy($configBytes, 0, $allBytes, $sfxBytes.Length, $configBytes.Length)
[System.Buffer]::BlockCopy($zipBytes, 0, $allBytes, $sfxBytes.Length + $configBytes.Length, $zipBytes.Length)

[System.IO.File]::WriteAllBytes($outExe, $allBytes)

$szMB = (Get-Item $outExe).Length / 1MB
Write-Host "SUCCESS: $outExe ($([math]::Round($szMB, 1)) MB)"

# Cleanup temp files
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
Remove-Item $configPath -Force -ErrorAction SilentlyContinue
Remove-Item $pkgDir -Recurse -Force -ErrorAction SilentlyContinue
