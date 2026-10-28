$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 环境创建失败" }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }
$env:QT_QPA_PLATFORM = "offscreen"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "测试失败" }
Remove-Item Env:QT_QPA_PLATFORM
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SmartCalculatorNotepad run.py
if ($LASTEXITCODE -ne 0) { throw "打包失败" }
$env:QT_QPA_PLATFORM = "offscreen"
$env:APPDATA = Join-Path $env:TEMP ([guid]::NewGuid().ToString())
$env:LOCALAPPDATA = $env:APPDATA
$process = Start-Process -FilePath ".\dist\SmartCalculatorNotepad.exe" -ArgumentList "--smoke-test" -PassThru
if (-not $process.WaitForExit(60000)) { $process.Kill(); throw "exe 启动超时" }
if ($process.ExitCode -ne 0) { throw "exe 自检失败" }
Remove-Item Env:QT_QPA_PLATFORM
Write-Host "完成：dist\SmartCalculatorNotepad.exe"
