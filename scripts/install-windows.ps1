# Miniread (极读) - Windows 一键安装脚本
# 特性: 语言选择 / 环境自动检测 / 中国大陆自动切换阿里云源 / Nginx 选装 / 计划任务开机自启
# 以管理员身份运行此脚本

param(
    [int]$Port = 7766,
    [string]$InstallDir = "C:\Miniread"
)

$ErrorActionPreference = "Stop"

# ============================================================
# [1] 语言选择（脚本第一步）
# ============================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Miniread (极读) - Windows Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "请选择语言 / Select language:"
Write-Host "  1) 中文"
Write-Host "  2) English"
$LangIn = Read-Host "选择 / Choice [1]"
if ($LangIn -eq "2") { $Script:Lang = "en" } else { $Script:Lang = "zh" }

# 双语言输出助手: T "中文" "English"
function T([string]$zh, [string]$en) {
    if ($Script:Lang -eq "en") { return $en } else { return $zh }
}

function Info([string]$zh, [string]$en) { Write-Host (T $zh $en) -ForegroundColor Yellow }
function Ok([string]$zh, [string]$en) { Write-Host "  [OK] $(T $zh $en)" -ForegroundColor Green }
function Warn([string]$zh, [string]$en) { Write-Host "  [!] $(T $zh $en)" -ForegroundColor Yellow }
function Fail([string]$zh, [string]$en) { Write-Host "  [X] $(T $zh $en)" -ForegroundColor Red }

Write-Host ""
Info "开始安装 Miniread..." "Installing Miniread..."
Write-Host ""

# ============================================================
# [2] 环境自动检测
# ============================================================
Info "[2/8] 自动检测环境..." "Detecting environment..."

# 管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "[X] $(T '请以管理员身份运行此脚本（右键 -> 以管理员身份运行）' 'Please run as Administrator (right-click -> Run as administrator)')" -ForegroundColor Red
    pause
    exit 1
}
Ok "管理员权限" "Administrator privileges"

# 执行策略（保证脚本能运行）
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force } catch {}

# Python 检测
$pythonCmd = $null
try {
    $pv = python --version 2>&1
    if ($LASTEXITCODE -eq 0) { $pythonCmd = "python"; Ok "Python: $pv" "Python: $pv" }
} catch {}
if (-not $pythonCmd) {
    try {
        $pv = py -3 --version 2>&1
        if ($LASTEXITCODE -eq 0) { $pythonCmd = "py -3"; Ok "Python (py launcher): $pv" "Python (py launcher): $pv" }
    } catch {}
}

# ============================================================
# [3] 区域检测 → 阿里云镜像源
# ============================================================
Info "[3/8] 检测所在区域..." "Detecting region..."

$region = ""
try {
    $region = (Invoke-RestMethod -Uri "https://ipinfo.io/country" -TimeoutSec 5).Trim()
} catch {
    try {
        $cc = (Invoke-WebRequest -Uri "http://cip.cc" -TimeoutSec 5 -UseBasicParsing).Content
        if ($cc -match "CN") { $region = "CN" }
    } catch {}
}

if ($region) { Ok "$(T '检测到区域' 'Detected region'): $region" } else { Warn "自动检测失败" "Auto detection failed" }

if ($region -eq "CN") {
    $ans = Read-Host (T "检测到中国大陆环境，默认使用阿里云镜像源。确认? [Y/n]" "Mainland China detected. Use Aliyun mirrors by default? [Y/n]")
    if ($ans -match "^[nN]") { $UseCnMirror = $false } else { $UseCnMirror = $true }
} else {
    $ans = Read-Host (T "是否位于中国大陆并使用阿里云镜像源? [y/N]" "Located in mainland China and use Aliyun mirrors? [y/N]")
    if ($ans -match "^[yY]") { $UseCnMirror = $true } else { $UseCnMirror = $false }
}

$PipMirror = "https://mirrors.aliyun.com/pypi/simple/"
if ($UseCnMirror) {
    Ok "已启用阿里云镜像源 (pip / Python 安装包 / 下载加速)" "Aliyun mirrors enabled (pip / Python installer / download acceleration)"
} else {
    Ok "使用官方源" "Official sources will be used"
}

# ============================================================
# [4] Python 安装（缺失时）与项目下载
# ============================================================
if (-not $pythonCmd) {
    Info "[4/8] 未找到 Python，正在下载安装..." "Python not found, downloading..."
    $pyVer = "3.12.3"
    if ($UseCnMirror) {
        $pyUrl = "https://mirrors.aliyun.com/python-release/windows/python-$pyVer-amd64.exe"
    } else {
        $pyUrl = "https://www.python.org/ftp/python/$pyVer/python-$pyVer-amd64.exe"
    }
    $pythonInstaller = "$env:TEMP\python-installer.exe"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $pyUrl -OutFile $pythonInstaller -UseBasicParsing
        Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0"
        Remove-Item $pythonInstaller -Force -ErrorAction SilentlyContinue
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $pythonCmd = "python"
        Ok "Python 安装完成" "Python installed"
    } catch {
        Fail "Python 自动安装失败，请手动安装 Python 3.10+ 后重跑本脚本" "Automatic Python install failed. Install Python 3.10+ manually and re-run."
        pause
        exit 1
    }
} else {
    Info "[4/8] Python 已就绪" "Python is ready"
}

# 项目下载（GitHub；中国网络失败自动走加速通道）
Info "下载项目文件..." "Downloading project files..."
$zipPath = "$env:TEMP\miniread.zip"
$downloaded = $false
$urls = @()
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/linlelest/Miniread/releases/latest" -TimeoutSec 15
    $zipAsset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
    if ($zipAsset) { $urls += $zipAsset.browser_download_url }
} catch {}
$urls += "https://github.com/linlelest/Miniread/archive/refs/heads/main.zip"
if ($UseCnMirror) {
    foreach ($pfx in @("https://ghfast.top/", "https://mirror.ghproxy.com/")) {
        $urls += ($pfx + "https://github.com/linlelest/Miniread/archive/refs/heads/main.zip")
    }
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
foreach ($u in $urls) {
    try {
        Invoke-WebRequest -Uri $u -OutFile $zipPath -UseBasicParsing -TimeoutSec 120
        if ((Get-Item $zipPath).Length -gt 10000) { $downloaded = $true; break }
    } catch { Warn "$(T '下载失败，尝试下一个源' 'Download failed, trying next source'): $u" }
}

if ($downloaded) {
    Ok "下载完成，正在解压..." "Downloaded, extracting..."
    Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
    Remove-Item $zipPath -Force
    $nested = Get-ChildItem -Path $InstallDir -Directory | Where-Object { $_.Name -like "Miniread*" } | Select-Object -First 1
    if ($nested) {
        Get-ChildItem -Path $nested.FullName | Move-Item -Destination $InstallDir -Force
        Remove-Item $nested.FullName -Recurse -Force
    }
} else {
    Warn "无法从网络下载，请手动将项目文件放入 $InstallDir 后重新运行" "Network download failed. Place project files into the install dir and re-run."
    pause
    exit 1
}

# 定位应用目录
if (Test-Path "$InstallDir\miniread\app.py") { $AppDir = "$InstallDir\miniread" } else { $AppDir = $InstallDir }
Ok "应用目录: $AppDir" "App dir: $AppDir"

# ============================================================
# [5] Python 依赖（阿里云 pip 源）
# ============================================================
Info "[5/8] 安装 Python 依赖..." "Installing Python dependencies..."
$reqPath = "$AppDir\requirements.txt"
if (Test-Path $reqPath) {
    if ($UseCnMirror) {
        & $pythonCmd -m pip install --upgrade pip -q -i $PipMirror
        & $pythonCmd -m pip install -r $reqPath -q -i $PipMirror
        # 持久化 pip 阿里云源（此后用户手动 pip 也走镜像）
        & $pythonCmd -m pip config set global.index-url $PipMirror | Out-Null
    } else {
        & $pythonCmd -m pip install --upgrade pip -q
        & $pythonCmd -m pip install -r $reqPath -q
    }
    Ok "依赖安装完成" "Dependencies installed"
} else {
    Warn "未找到 requirements.txt，安装基本依赖..." "requirements.txt not found, installing base deps..."
    if ($UseCnMirror) {
        & $pythonCmd -m pip install flask flask-cors waitress bcrypt requests ebooklib PyPDF2 pdfplumber python-docx beautifulsoup4 lxml markdown striprtf -q -i $PipMirror
    } else {
        & $pythonCmd -m pip install flask flask-cors waitress bcrypt requests ebooklib PyPDF2 pdfplumber python-docx beautifulsoup4 lxml markdown striprtf -q
    }
}

# ============================================================
# [6] 启动脚本 + 计划任务（开机自启）
# ============================================================
Info "[6/8] 配置启动方式..." "Configuring startup..."

$startScript = @"
@echo off
title Miniread (极读)
cd /d "$AppDir"
set MINIREAD_PRODUCTION=1
$pythonCmd run.py
pause
"@
$startScript | Out-File -FilePath "$InstallDir\start-miniread.bat" -Encoding UTF8

$taskName = "MinireadServer"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }

$action = New-ScheduledTaskAction -Execute $pythonCmd -Argument "run.py" -WorkingDirectory $AppDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartInterval (New-TimeSpan -Minutes 5) -RestartCount 10
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Ok "已配置开机自启（计划任务 MinireadServer）" "Auto-start configured (scheduled task MinireadServer)"

# ============================================================
# [7] Nginx 选装（交互决定）
# ============================================================
Info "[7/8] Nginx 反向代理（选装）" "Nginx reverse proxy (optional)"
Write-Host "  $(T '不安装 Nginx 也可直接通过端口访问服务。' 'The app can be accessed directly via port without Nginx.')"
$nginxIn = Read-Host (T "是否安装并配置 Nginx 反向代理? [y/N]" "Install and configure Nginx reverse proxy? [y/N]")
$InstallNginx = $nginxIn -match "^[yY]"

if ($InstallNginx) {
    $nginxDir = "C:\nginx-miniread"
    $nginxZip = "$env:TEMP\nginx.zip"
    $nginxOk = $false
    if ($UseCnMirror) {
        # 阿里云无 Windows Nginx 二进制镜像，优先本地已有，其次官方源（提示可能较慢）
        if (Test-Path "$nginxDir\nginx.exe") { $nginxOk = $true; Warn "检测到已有 Nginx，跳过下载" "Existing Nginx found, skip download" }
    }
    if (-not $nginxOk) {
        Info "下载 Nginx（Windows 版）..." "Downloading Nginx (Windows)..."
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri "https://nginx.org/download/nginx-1.24.0.zip" -OutFile $nginxZip -UseBasicParsing -TimeoutSec 120
            Expand-Archive -Path $nginxZip -DestinationPath "C:\" -Force
            Rename-Item -Path "C:\nginx-1.24.0" -NewName "nginx-miniread" -Force
            $nginxOk = $true
        } catch {
            Warn "Nginx 下载失败，跳过（服务仍可通过端口直接访问）" "Nginx download failed, skipped (service still accessible via port)"
        }
    }
    if ($nginxOk) {
        # 生成反向代理配置
        $nginxConf = @"
worker_processes  1;
error_log  logs/error.log;
pid        logs/nginx.pid;

events { worker_connections  1024; }

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout  65;

    server {
        listen       80;
        server_name  _;

        location /miniread/ {
            proxy_pass http://127.0.0.1:$Port/;
            proxy_set_header Host `$host;
            proxy_set_header X-Real-IP `$remote_addr;
            proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;
            proxy_http_version 1.1;
            proxy_set_header Upgrade `$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_buffering off;
            proxy_read_timeout 3600s;
        }
    }
}
"@
        $nginxConf | Out-File -FilePath "$nginxDir\conf\nginx.conf" -Encoding ASCII -Force
        # 启动 nginx（若已运行则重载）
        Push-Location $nginxDir
        Start-Process -FilePath "$nginxDir\nginx.exe" -WindowStyle Hidden
        Pop-Location
        Start-Sleep -Seconds 2
        $nginxProc = Get-Process nginx -ErrorAction SilentlyContinue
        if ($nginxProc) { Ok "Nginx 运行中 (80 端口反代 /miniread/)" "Nginx running (port 80 -> /miniread/)" }
        else { Warn "Nginx 启动失败，检查 $nginxDir\logs\error.log" "Nginx failed to start, check $nginxDir\logs\error.log" }
    }
} else {
    Ok "已跳过 Nginx，将直接通过端口访问" "Nginx skipped, direct port access"
}

# ============================================================
# [8] 防火墙 + 启动
# ============================================================
Info "[8/8] 配置防火墙并启动服务..." "Configuring firewall and starting..."

$ruleName = "Miniread Server Port $Port"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existingRule) { Remove-NetFirewallRule -DisplayName $ruleName }
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
Ok "防火墙规则已添加 (端口 $Port)" "Firewall rule added (port $Port)"
if ($InstallNginx) {
    $rule80 = "Miniread Nginx Port 80"
    $r80 = Get-NetFirewallRule -DisplayName $rule80 -ErrorAction SilentlyContinue
    if ($r80) { Remove-NetFirewallRule -DisplayName $rule80 }
    New-NetFirewallRule -DisplayName $rule80 -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow | Out-Null
    Ok "防火墙规则已添加 (端口 80)" "Firewall rule added (port 80)"
}

Start-Process -FilePath $pythonCmd -ArgumentList "run.py" -WorkingDirectory $AppDir -WindowStyle Hidden
Start-ScheduledTask -TaskName $taskName

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress
if (-not $ip) { $ip = "localhost" }

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   $(T '安装完成！' 'Installation complete!')" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
if ($InstallNginx) {
    Write-Host "  $(T '访问地址' 'Access URL'): http://$ip/miniread/" -ForegroundColor White
    Write-Host "  $(T '或' 'or'): http://$ip`:$Port" -ForegroundColor White
} else {
    Write-Host "  $(T '访问地址' 'Access URL'): http://$ip`:$Port" -ForegroundColor White
}
Write-Host "  $(T '安装目录' 'Install dir'): $AppDir" -ForegroundColor White
Write-Host "  $(T '启动方式' 'Start'): $InstallDir\start-miniread.bat" -ForegroundColor White
Write-Host ""
Write-Host "  $(T '首次访问将自动跳转到管理员注册页' 'First visit will redirect to admin registration')" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

Start-Process "http://localhost:$Port"
pause
