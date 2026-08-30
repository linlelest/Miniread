#!/bin/bash
###############################################
#  Miniread (极读) - Linux 一键安装脚本
#  特性: 语言选择 / 发行版自动检测 / 中国大陆自动切换阿里云源 / Nginx 选装 / systemd 一键配置
#  使用方法: sudo bash install-linux.sh
###############################################

# 交互输入来自终端（兼容 curl ... | bash 管道安装方式）
exec < /dev/tty 2>/dev/null || true

set -u

APP_DIR="/opt/miniread"
APP_PORT=7766
NGINX_PATH="/miniread"
REPO_URL="https://github.com/linlelest/Miniread.git"
REPO_ZIP="https://github.com/linlelest/Miniread/archive/refs/heads/main.zip"
GH_ACCEL_PREFIXES=("https://ghfast.top/" "https://mirror.ghproxy.com/")
PIP_MIRROR="https://mirrors.aliyun.com/pypi/simple/"
PYTHON_CMD=""
USE_CN=0
INSTALL_NGINX=0
PKG=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 双语言输出助手: t "中文" "English"
t() {
    if [ "${SCRIPT_LANG:-zh}" = "en" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi
}

###############################################
# [1] 语言选择（脚本第一步）
###############################################
echo ""
echo "=========================================="
echo "   Miniread (极读) - Linux Installer"
echo "=========================================="
echo ""
echo "请选择语言 / Select language:"
echo "  1) 中文"
echo "  2) English"
printf "选择 / Choice [1]: "
read -r LANG_IN || LANG_IN="1"
case "$LANG_IN" in
    2) SCRIPT_LANG="en" ;;
    *) SCRIPT_LANG="zh" ;;
esac

echo ""
echo -e "${CYAN}$(t '开始安装 Miniread' 'Installing Miniread')${NC}"
echo ""

###############################################
# [2] 环境自动检测
###############################################
STEP=2
echo -e "${YELLOW}[$STEP/9] $(t '自动检测服务器环境...' 'Detecting server environment...')${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[X] $(t '请使用 sudo 运行此脚本' 'Please run this script with sudo')${NC}"
    exit 1
fi

# 发行版与包管理器检测
DISTRO="unknown"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="${ID:-unknown}"
fi

if command -v apt-get >/dev/null 2>&1; then
    PKG="apt"
elif command -v dnf >/dev/null 2>&1; then
    PKG="dnf"
elif command -v yum >/dev/null 2>&1; then
    PKG="yum"
else
    echo -e "${RED}[X] $(t '未受支持的发行版（需要 apt/dnf/yum）。请参考 README 手动部署。' 'Unsupported distro (apt/dnf/yum required). See README for manual deployment.')${NC}"
    exit 1
fi

HAS_SYSTEMD=0
if [ -d /run/systemd/system ]; then HAS_SYSTEMD=1; fi

ARCH=$(uname -m)
echo -e "  ${GREEN}[OK] $(t '发行版' 'Distro'): $DISTRO (${ARCH}), pkg=$PKG, systemd=$HAS_SYSTEMD${NC}"

if [ "$HAS_SYSTEMD" -ne 1 ]; then
    echo -e "${YELLOW}[!] $(t '未检测到 systemd，将跳过开机自启配置，安装后需手动启动。' 'systemd not detected; auto-start config will be skipped.')${NC}"
fi

###############################################
# [3] 区域检测 → 阿里云镜像源
###############################################
STEP=3
echo -e "${YELLOW}[$STEP/9] $(t '检测服务器所在区域...' 'Detecting server region...')${NC}"

REGION=""
REGION_AUTO=0
if command -v curl >/dev/null 2>&1; then
    REGION=$(curl -m 4 -s https://ipinfo.io/country 2>/dev/null | tr -d '[:space:]')
    [ -z "$REGION" ] && REGION=$(curl -m 4 -s http://cip.cc 2>/dev/null | grep -io 'CN' | head -n 1)
    [ -n "$REGION" ] && REGION_AUTO=1
fi

if [ "$REGION_AUTO" -eq 1 ]; then
    echo -e "  ${GREEN}[OK] $(t '检测到区域' 'Detected region'): ${REGION}${NC}"
else
    echo -e "  ${YELLOW}[!] $(t '自动检测失败' 'Auto detection failed')${NC}"
fi

if [ "$REGION" = "CN" ]; then
    printf "$(t '检测到中国大陆环境，默认使用阿里云镜像源。确认? [Y/n]: ' 'Mainland China detected. Use Aliyun mirrors by default? [Y/n]: ')"
    read -r CN_IN || CN_IN=""
    case "$CN_IN" in n|N|no|No) USE_CN=0 ;; *) USE_CN=1 ;; esac
else
    printf "$(t '是否位于中国大陆并使用阿里云镜像源? [y/N]: ' 'Located in mainland China and use Aliyun mirrors? [y/N]: ')"
    read -r CN_IN || CN_IN=""
    case "$CN_IN" in y|Y|yes|Yes) USE_CN=1 ;; *) USE_CN=0 ;; esac
fi

if [ "$USE_CN" -eq 1 ]; then
    echo -e "  ${GREEN}[OK] $(t '已启用阿里云镜像源 (pip / 系统包 / 下载加速)' 'Aliyun mirrors enabled (pip / system packages / download acceleration)')${NC}"

    # 系统包管理器换源（阿里云）
    if [ "$PKG" = "apt" ]; then
        cp -f /etc/apt/sources.list /etc/apt/sources.list.miniread.bak 2>/dev/null || true
        sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g; s|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g; s|http://cn.archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g; s|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g; s|http://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list 2>/dev/null || true
        if [ -d /etc/apt/sources.list.d ]; then
            find /etc/apt/sources.list.d -name '*.sources' -exec sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g; s|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g; s|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g; s|http://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' {} \; 2>/dev/null || true
        fi
    elif [ "$PKG" = "yum" ] && [ "$DISTRO" = "centos" ]; then
        cp -f /etc/yum.repos.d/CentOS-Base.repo /etc/yum.repos.d/CentOS-Base.repo.miniread.bak 2>/dev/null || true
        curl -m 20 -sfLo /etc/yum.repos.d/CentOS-Base.repo "https://mirrors.aliyun.com/repo/Centos-7.repo" || true
    fi
fi

PIP_ARGS=""
if [ "$USE_CN" -eq 1 ]; then
    PIP_ARGS="-i $PIP_MIRROR"
fi

###############################################
# [4] 系统依赖（Nginx 在后面对话中选装）
###############################################
STEP=4
echo -e "${YELLOW}[$STEP/9] $(t '安装系统依赖...' 'Installing system dependencies...')${NC}"

if [ "$PKG" = "apt" ]; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-pip python3-venv git curl unzip wget 2>&1 | tail -1
elif [ "$PKG" = "dnf" ]; then
    dnf install -y -q python3 python3-pip git curl unzip wget 2>&1 | tail -1
else
    yum install -y -q python3 python3-pip git curl unzip wget 2>&1 | tail -1
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
    echo -e "  ${GREEN}[OK] Python3: $(python3 --version)${NC}"
else
    echo -e "${RED}[X] $(t '未找到 Python3' 'Python3 not found')${NC}"
    exit 1
fi

# 创建目录
mkdir -p "$APP_DIR" "$APP_DIR/uploads" "$APP_DIR/downloads" "$APP_DIR/data"
echo -e "  ${GREEN}[OK] $(t '目录' 'Directory'): $APP_DIR${NC}"

###############################################
# [5] 下载项目文件
###############################################
STEP=5
echo -e "${YELLOW}[$STEP/9] $(t '下载项目文件...' 'Downloading project files...')${NC}"

download_project() {
    cd /tmp
    rm -rf miniread-download miniread.zip
    if git clone --depth 1 "$REPO_URL" miniread-download 2>/dev/null; then
        return 0
    fi
    wget -q "$REPO_ZIP" -O miniread.zip 2>/dev/null || curl -m 60 -sfL "$REPO_ZIP" -o miniread.zip 2>/dev/null || return 1
    unzip -qo miniread.zip
    mv Miniread-main miniread-download
    rm -f miniread.zip
    return 0
}

NEED_DOWNLOAD=1
if [ -f "$APP_DIR/app.py" ]; then
    printf "$(t '检测到已有安装，是否重新下载覆盖? [y/N]: ' 'Existing installation found. Re-download and overwrite? [y/N]: ')"
    read -r REDOWNLOAD || REDOWNLOAD=""
    case "$REDOWNLOAD" in y|Y|yes|Yes) NEED_DOWNLOAD=1 ;; *) NEED_DOWNLOAD=0 ;; esac
fi

if [ "$NEED_DOWNLOAD" -eq 1 ]; then
    if ! download_project; then
        if [ "$USE_CN" -eq 1 ]; then
            echo -e "  ${YELLOW}[!] $(t '直连下载失败，尝试加速通道...' 'Direct download failed, trying acceleration...')${NC}"
            for PREFIX in "${GH_ACCEL_PREFIXES[@]}"; do
                cd /tmp && rm -rf miniread-download miniread.zip
                if curl -m 90 -sfL "${PREFIX}${REPO_ZIP}" -o miniread.zip; then
                    unzip -qo miniread.zip && mv Miniread-main miniread-download && rm -f miniread.zip
                    break
                fi
            done
        fi
    fi
    if [ -d /tmp/miniread-download ]; then
        if [ -d /tmp/miniread-download/miniread ]; then
            cp -rf /tmp/miniread-download/miniread/* "$APP_DIR/"
        else
            cp -rf /tmp/miniread-download/* "$APP_DIR/"
        fi
        rm -rf /tmp/miniread-download
        echo -e "  ${GREEN}[OK] $(t '下载完成' 'Download completed')${NC}"
    fi
else
    echo -e "  ${GREEN}[OK] $(t '跳过下载' 'Download skipped')${NC}"
fi

if [ ! -f "$APP_DIR/app.py" ]; then
    echo -e "${RED}[X] $(t '未找到 app.py，请检查项目文件' 'app.py not found, please check project files')${NC}"
    exit 1
fi

###############################################
# [6] Python 依赖
###############################################
STEP=6
echo -e "${YELLOW}[$STEP/9] $(t '安装 Python 依赖...' 'Installing Python dependencies...')${NC}"
cd "$APP_DIR"
if [ -f requirements.txt ]; then
    # shellcheck disable=SC2086
    $PYTHON_CMD -m pip install --upgrade pip -q $PIP_ARGS || true
    # shellcheck disable=SC2086
    $PYTHON_CMD -m pip install -r requirements.txt -q $PIP_ARGS
    echo -e "  ${GREEN}[OK] $(t '依赖安装完成' 'Dependencies installed')${NC}"
else
    echo -e "  ${YELLOW}[!] requirements.txt $(t '未找到' 'not found')${NC}"
fi

###############################################
# [7] systemd 服务一键配置
###############################################
STEP=7
echo -e "${YELLOW}[$STEP/9] $(t '配置 systemd 服务...' 'Configuring systemd service...')${NC}"

if [ "$HAS_SYSTEMD" -eq 1 ]; then
    cat > /etc/systemd/system/miniread.service << EOF
[Unit]
Description=Miniread - Online Reading Platform
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment=MINIREAD_PRODUCTION=1
Environment=HOST=0.0.0.0
Environment=PORT=$APP_PORT
ExecStart=$PYTHON_CMD run.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable miniread.service >/dev/null 2>&1
    echo -e "  ${GREEN}[OK] systemd $(t '服务已配置并设为开机自启' 'service configured and enabled')${NC}"
else
    echo -e "  ${YELLOW}[!] $(t '跳过（无 systemd）' 'Skipped (no systemd)')${NC}"
fi

###############################################
# [8] Nginx 选装（交互决定）
###############################################
STEP=8
echo -e "${YELLOW}[$STEP/9] $(t 'Nginx 反向代理（选装）' 'Nginx reverse proxy (optional)')${NC}"
echo -e "  $(t '不安装 Nginx 也可直接通过端口访问服务。' 'The app can be accessed directly via port without Nginx.')"
printf "$(t '是否安装并配置 Nginx 反向代理? [y/N]: ' 'Install and configure Nginx reverse proxy? [y/N]: ')"
read -r NGINX_IN || NGINX_IN=""
case "$NGINX_IN" in y|Y|yes|Yes) INSTALL_NGINX=1 ;; *) INSTALL_NGINX=0 ;; esac

if [ "$INSTALL_NGINX" -eq 1 ]; then
    echo -e "  $(t '安装 Nginx...' 'Installing Nginx...')"
    if [ "$PKG" = "apt" ]; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx 2>&1 | tail -1
    elif [ "$PKG" = "dnf" ]; then
        dnf install -y -q nginx 2>&1 | tail -1
    else
        yum install -y -q nginx 2>&1 | tail -1
    fi

    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    [ -z "$SERVER_IP" ] && SERVER_IP=$(curl -m 5 -s ifconfig.me 2>/dev/null || echo "your-server-ip")

    cat > /etc/nginx/conf.d/miniread.conf << EOF
server {
    listen 80;
    server_name _;

    access_log /var/log/nginx/miniread_access.log;
    error_log /var/log/nginx/miniread_error.log;

    location /miniread/ {
        proxy_pass http://127.0.0.1:$APP_PORT/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        chunked_transfer_encoding off;
    }
}
EOF

    # Debian/Ubuntu 的 sites-enabled 结构兼容
    if [ -d /etc/nginx/sites-enabled ]; then
        ln -sf /etc/nginx/sites-available/miniread /etc/nginx/sites-enabled/miniread 2>/dev/null || true
        rm -f /etc/nginx/sites-enabled/default
        cat > /etc/nginx/sites-available/miniread << EOF
server {
    listen 80;
    server_name _;
    location /miniread/ {
        proxy_pass http://127.0.0.1:$APP_PORT/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
EOF
        ln -sf /etc/nginx/sites-available/miniread /etc/nginx/sites-enabled/miniread
    fi

    nginx -t 2>/dev/null && echo -e "  ${GREEN}[OK] Nginx $(t '配置验证通过' 'config test passed')" || {
        echo -e "  ${RED}[X] Nginx $(t '配置有误' 'config error')${NC}"
        nginx -t || true
    }
    echo -e "  ${GREEN}[OK] Nginx $(t '配置完成' 'configured')${NC}"
else
    echo -e "  ${GREEN}[OK] $(t '已跳过 Nginx，将直接通过端口访问' 'Nginx skipped, direct port access')${NC}"
fi

###############################################
# [9] 启动服务
###############################################
STEP=9
echo -e "${YELLOW}[$STEP/9] $(t '启动服务...' 'Starting services...')${NC}"

if [ "$HAS_SYSTEMD" -eq 1 ]; then
    systemctl restart miniread.service
    sleep 2
    if systemctl is-active --quiet miniread; then
        echo -e "  ${GREEN}[OK] Miniread $(t '服务运行中' 'service is running')${NC}"
    else
        echo -e "  ${RED}[X] Miniread $(t '服务启动失败' 'service failed to start')${NC}"
        systemctl status miniread --no-pager || true
    fi
else
    cd "$APP_DIR"
    MINIREAD_PRODUCTION=1 nohup $PYTHON_CMD run.py >/tmp/miniread.log 2>&1 &
    sleep 2
    echo -e "  ${GREEN}[OK] Miniread $(t '已后台启动（无 systemd，日志: /tmp/miniread.log）' 'started in background (no systemd, log: /tmp/miniread.log)')${NC}"
fi

if [ "$INSTALL_NGINX" -eq 1 ]; then
    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable nginx >/dev/null 2>&1 || true
        systemctl restart nginx 2>/dev/null || nginx 2>/dev/null || true
    else
        nginx 2>/dev/null || nginx -s reload 2>/dev/null || true
    fi
    if pgrep nginx >/dev/null 2>&1; then
        echo -e "  ${GREEN}[OK] Nginx $(t '运行中' 'is running')${NC}"
    else
        echo -e "  ${RED}[X] Nginx $(t '启动失败' 'failed to start')${NC}"
    fi
fi

###############################################
# 安装完成
###############################################
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$SERVER_IP" ] && SERVER_IP=$(curl -m 5 -s ifconfig.me 2>/dev/null || echo "your-server-ip")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   $(t '安装完成！' 'Installation complete!')${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
if [ "$INSTALL_NGINX" -eq 1 ]; then
    echo -e "  ${CYAN}$(t '访问地址' 'Access URL'):${NC}"
    echo -e "    http://${SERVER_IP}${NGINX_PATH}"
    echo -e "    $(t '或' 'or') http://${SERVER_IP}:${APP_PORT}"
else
    echo -e "  ${CYAN}$(t '访问地址' 'Access URL'):${NC}"
    echo -e "    http://${SERVER_IP}:${APP_PORT}"
fi
echo ""
echo -e "  ${CYAN}$(t '安装目录' 'Install dir'):${NC} $APP_DIR"
echo -e "  ${CYAN}$(t '数据目录' 'Data dir'):${NC} $APP_DIR/data"
echo ""
if [ "$HAS_SYSTEMD" -eq 1 ]; then
    echo -e "  ${CYAN}$(t '管理命令' 'Management'):${NC}"
    echo -e "    systemctl status miniread"
    echo -e "    systemctl restart miniread"
    echo -e "    journalctl -u miniread -f"
fi
echo ""
echo -e "  ${YELLOW}$(t '首次访问将自动跳转到管理员注册页' 'First visit will redirect to admin registration')${NC}"
echo ""
