#!/bin/bash
###############################################
#  Miniread (极读) - Debian/Ubuntu 一键安装脚本
#  包含 Nginx 自动配置 (访问 /miniread)
#  使用方法: sudo bash install-linux.sh
###############################################

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

APP_DIR="/opt/miniread"
APP_PORT=7766
NGINX_PATH="/miniread"
REPO_URL="https://github.com/linlelest/Miniread.git"
PYTHON_CMD=""

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}   Miniread (极读) - Linux 安装脚本${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[X] 请使用 sudo 运行此脚本${NC}"
    echo -e "${YELLOW}    sudo bash install-linux.sh${NC}"
    exit 1
fi

# ============ [1/7] 安装系统依赖 ============
echo -e "${YELLOW}[1/7] 更新系统并安装依赖...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx git curl unzip wget 2>&1 | tail -1

# 确定Python命令
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo -e "  ${GREEN}[OK] Python3: $(python3 --version)${NC}"
else
    echo -e "${RED}[X] 未找到 Python3${NC}"
    exit 1
fi

# ============ [2/7] 创建目录 ============
echo -e "${YELLOW}[2/7] 创建应用目录...${NC}"
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/uploads"
mkdir -p "$APP_DIR/downloads"
mkdir -p "$APP_DIR/data"
echo -e "  ${GREEN}[OK] 目录: $APP_DIR${NC}"

# ============ [3/7] 下载项目 ============
echo -e "${YELLOW}[3/7] 下载项目文件...${NC}"

if [ -f "$APP_DIR/app.py" ]; then
    echo -e "  ${YELLOW}[i] 检测到已有安装，是否重新下载? [y/N]${NC}"
    read -r REDOWNLOAD
    if [ "$REDOWNLOAD" != "y" ] && [ "$REDOWNLOAD" != "Y" ]; then
        echo -e "  ${GREEN}[OK] 跳过下载${NC}"
    else
        cd /tmp
        rm -rf miniread-download
        git clone --depth 1 "$REPO_URL" miniread-download 2>/dev/null || {
            # Git不可用则尝试wget
            wget -q "https://github.com/linlelest/Miniread/archive/refs/heads/main.zip" -O miniread.zip
            unzip -qo miniread.zip
            mv Miniread-main miniread-download
            rm miniread.zip
        }
        if [ -d "miniread-download/miniread" ]; then
            cp -rf miniread-download/miniread/* "$APP_DIR/"
        else
            cp -rf miniread-download/* "$APP_DIR/"
        fi
        rm -rf miniread-download
        echo -e "  ${GREEN}[OK] 下载完成${NC}"
    fi
else
    cd /tmp
    rm -rf miniread-download
    git clone --depth 1 "$REPO_URL" miniread-download 2>/dev/null || {
        wget -q "https://github.com/linlelest/Miniread/archive/refs/heads/main.zip" -O miniread.zip
        unzip -qo miniread.zip
        mv Miniread-main miniread-download
        rm miniread.zip
    }
    if [ -d "miniread-download/miniread" ]; then
        cp -rf miniread-download/miniread/* "$APP_DIR/"
    else
        cp -rf miniread-download/* "$APP_DIR/"
    fi
    rm -rf miniread-download
    echo -e "  ${GREEN}[OK] 下载完成${NC}"
fi

# 确保app.py存在
if [ ! -f "$APP_DIR/app.py" ]; then
    echo -e "${RED}[X] 未找到 app.py，请检查项目文件${NC}"
    exit 1
fi

# ============ [4/7] 安装Python依赖 ============
echo -e "${YELLOW}[4/7] 安装 Python 依赖...${NC}"
cd "$APP_DIR"
if [ -f "requirements.txt" ]; then
    $PYTHON_CMD -m pip install --upgrade pip -q
    $PYTHON_CMD -m pip install -r requirements.txt -q
    echo -e "  ${GREEN}[OK] 依赖安装完成${NC}"
else
    echo -e "  ${YELLOW}[!] 未找到 requirements.txt${NC}"
fi

# ============ [5/7] 配置 systemd 服务 ============
echo -e "${YELLOW}[5/7] 配置 systemd 服务...${NC}"

cat > /etc/systemd/system/miniread.service << EOF
[Unit]
Description=Miniread (极读) - 在线阅读管理平台
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
systemctl enable miniread.service
echo -e "  ${GREEN}[OK] systemd 服务已配置${NC}"

# ============ [6/7] 配置 Nginx 反向代理 ============
echo -e "${YELLOW}[6/7] 配置 Nginx 反向代理...${NC}"

# 获取服务器IP
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$SERVER_IP" ] && SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "your-server-ip")

cat > /etc/nginx/sites-available/miniread << EOF
# Miniread (极读) Nginx 配置
# 访问: http://服务器IP/miniread

server {
    listen 80;
    server_name _;

    # 日志
    access_log /var/log/nginx/miniread_access.log;
    error_log /var/log/nginx/miniread_error.log;

    # Miniread 代理
    location /miniread/ {
        proxy_pass http://127.0.0.1:$APP_PORT/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket/SSE 支持
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

# 激活站点
if [ -L /etc/nginx/sites-enabled/miniread ]; then
    rm /etc/nginx/sites-enabled/miniread
fi
ln -s /etc/nginx/sites-available/miniread /etc/nginx/sites-enabled/miniread

# 移除默认站点（避免冲突）
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi

# 测试Nginx配置
nginx -t 2>/dev/null && echo -e "  ${GREEN}[OK] Nginx 配置验证通过${NC}" || {
    echo -e "  ${RED}[X] Nginx 配置有误，请检查${NC}"
    nginx -t
}

# ============ [7/7] 启动服务 ============
echo -e "${YELLOW}[7/7] 启动服务...${NC}"

systemctl restart miniread.service
systemctl restart nginx

sleep 2

# 检查服务状态
if systemctl is-active --quiet miniread; then
    echo -e "  ${GREEN}[OK] Miniread 服务运行中${NC}"
else
    echo -e "  ${RED}[X] Miniread 服务启动失败${NC}"
    systemctl status miniread --no-pager
fi

if systemctl is-active --quiet nginx; then
    echo -e "  ${GREEN}[OK] Nginx 运行中${NC}"
else
    echo -e "  ${RED}[X] Nginx 启动失败${NC}"
fi

# ============ 安装完成 ============
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  ${CYAN}访问地址:${NC}"
echo -e "    http://${SERVER_IP}${NGINX_PATH}"
echo -e "    (或直接访问) http://${SERVER_IP}:${APP_PORT}"
echo ""
echo -e "  ${CYAN}安装目录:${NC} $APP_DIR"
echo -e "  ${CYAN}数据目录:${NC} $APP_DIR/data"
echo -e "  ${CYAN}上传目录:${NC} $APP_DIR/uploads"
echo ""
echo -e "  ${YELLOW}首次访问将自动跳转到管理员注册页${NC}"
echo ""
echo -e "  ${CYAN}管理命令:${NC}"
echo -e "    systemctl status miniread    # 查看状态"
echo -e "    systemctl restart miniread   # 重启服务"
echo -e "    systemctl stop miniread      # 停止服务"
echo -e "    journalctl -u miniread -f    # 查看日志"
echo ""
echo -e "${GREEN}========================================${NC}"
