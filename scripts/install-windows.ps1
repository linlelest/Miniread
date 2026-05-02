# Miniread (极读) - Windows 一键安装脚本
# 以管理员身份运行此脚本

param(
    [int]$Port = 7766,
    [string]$InstallDir = "C:\Miniread"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Miniread (极读) - Windows 安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "[X] 请以管理员身份运行此脚本" -ForegroundColor Red
    Write-Host "    右键点击脚本 -> 以管理员身份运行" -ForegroundColor Yellow
    pause
    exit 1
}

# 检查Python
Write-Host "[1/6] 检查 Python 环境..." -ForegroundColor Yellow
$pythonCmd = $null
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pythonCmd = "python"
        Write-Host "  [OK] 找到 $pythonVersion" -ForegroundColor Green
    }
} catch {
    try {
        $pythonVersion = python3 --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = "python3"
            Write-Host "  [OK] 找到 $pythonVersion" -ForegroundColor Green
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "  [X] 未找到 Python，正在下载安装..." -ForegroundColor Red
    $pythonInstaller = "$env:TEMP\python-installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe" -OutFile $pythonInstaller
    Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0"
    Remove-Item $pythonInstaller
    # 刷新环境变量
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $pythonCmd = "python"
    Write-Host "  [OK] Python 安装完成" -ForegroundColor Green
}

# 创建安装目录
Write-Host "[2/6] 创建安装目录..." -ForegroundColor Yellow
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}
Write-Host "  [OK] 目录: $InstallDir" -ForegroundColor Green

# 下载项目文件
Write-Host "[3/6] 下载项目文件..." -ForegroundColor Yellow
$zipPath = "$env:TEMP\miniread.zip"
try {
    # 尝试从 GitHub Release 下载
    $releaseUrl = "https://api.github.com/repos/linlelest/Miniread/releases/latest"
    $release = Invoke-RestMethod -Uri $releaseUrl
    $zipAsset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
    if ($zipAsset) {
        Invoke-WebRequest -Uri $zipAsset.browser_download_url -OutFile $zipPath
    } else {
        # 从 main 分支下载
        Invoke-WebRequest -Uri "https://github.com/linlelest/Miniread/archive/refs/heads/main.zip" -OutFile $zipPath
    }
} catch {
    Write-Host "  [!] 无法下载远程文件，将创建本地安装" -ForegroundColor Yellow
    Write-Host "  [i] 请确保 $InstallDir 中已有项目文件" -ForegroundColor Yellow
    $zipPath = $null
}

if ($zipPath -and (Test-Path $zipPath)) {
    Write-Host "  [OK] 下载完成，正在解压..." -ForegroundColor Green
    Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
    Remove-Item $zipPath -Force
    
    # 如果解压后嵌套了一层目录，移动文件
    $nested = Get-ChildItem -Path $InstallDir -Directory | Where-Object { $_.Name -like "Miniread*" } | Select-Object -First 1
    if ($nested) {
        Get-ChildItem -Path $nested.FullName | Move-Item -Destination $InstallDir -Force
        Remove-Item $nested.FullName -Recurse -Force
    }
    
    # 查找miniread子目录
    $minireadDir = "$InstallDir\miniread"
    if (Test-Path "$InstallDir\miniread\app.py") {
        $AppDir = "$InstallDir\miniread"
    } else {
        $AppDir = $InstallDir
    }
} else {
    $AppDir = $InstallDir
}

# 安装Python依赖
Write-Host "[4/6] 安装 Python 依赖..." -ForegroundColor Yellow
$reqPath = "$AppDir\requirements.txt"
if (Test-Path $reqPath) {
    & $pythonCmd -m pip install --upgrade pip --quiet
    & $pythonCmd -m pip install -r $reqPath --quiet
    Write-Host "  [OK] 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  [!] 未找到 requirements.txt，正在安装基本依赖..." -ForegroundColor Yellow
    & $pythonCmd -m pip install flask flask-cors waitress bcrypt requests ebooklib PyPDF2 pdfplumber python-docx beautifulsoup4 lxml markdown striprtf --quiet
}

# 创建Windows服务或启动脚本
Write-Host "[5/6] 配置启动方式..." -ForegroundColor Yellow

# 创建启动脚本
$startScript = @"
@echo off
title Miniread (极读)
cd /d "$AppDir"
set MINIREAD_PRODUCTION=1
$pythonCmd run.py
pause
"@
$startScript | Out-File -FilePath "$InstallDir\start-miniread.bat" -Encoding UTF8

# 创建计划任务（开机自启）
$taskName = "MinireadServer"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $pythonCmd -Argument "run.py" -WorkingDirectory $AppDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartInterval (New-TimeSpan -Minutes 5) -RestartCount 10

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "  [OK] 已配置开机自启" -ForegroundColor Green

# 配置Windows防火墙
Write-Host "[6/6] 配置防火墙..." -ForegroundColor Yellow
$ruleName = "Miniread Server Port $Port"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existingRule) {
    Remove-NetFirewallRule -DisplayName $ruleName
}
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
Write-Host "  [OK] 防火墙规则已添加 (端口 $Port)" -ForegroundColor Green

# 立即启动服务
Write-Host ""
Write-Host "正在启动 Miniread 服务..." -ForegroundColor Cyan
Start-Process -FilePath $pythonCmd -ArgumentList "run.py" -WorkingDirectory $AppDir -WindowStyle Hidden
Start-ScheduledTask -TaskName $taskName

# 获取本机IP
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress
if (-not $ip) { $ip = "localhost" }

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  访问地址: http://$ip`:$Port" -ForegroundColor White
Write-Host "  安装目录: $AppDir" -ForegroundColor White
Write-Host "  启动方式: 开始菜单运行或 $InstallDir\start-miniread.bat" -ForegroundColor White
Write-Host ""
Write-Host "  首次访问将自动跳转到管理员注册页" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

# 打开浏览器
Start-Process "http://localhost:$Port"

pause
