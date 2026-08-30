<div align="center">

  <h1>📚 Miniread (极读)</h1>

  <p><strong>在线阅读管理平台 —— 兼容性第一，功能强大第二，美观第三</strong></p>

  <p>
    <img src="https://img.shields.io/badge/Version-2.1-blue" alt="Version">
    <img src="https://img.shields.io/badge/Python-3.8+-blue" alt="Python">
    <img src="https://img.shields.io/badge/Flask-3.0-green" alt="Flask">
    <img src="https://img.shields.io/badge/Database-SQLite-orange" alt="SQLite">
    <img src="https://img.shields.io/badge/Browser-Chrome%2091+-success" alt="Chrome">
    <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  </p>

</div>

---

## 📖 简介

**Miniread（极读）** 是一个轻量级、高兼容性的在线阅读管理平台。支持 TXT / EPUB / PDF / DOCX / PPTX 等多种格式导入与阅读、RSS 订阅聚合、书架分组管理，并集成了 [SoNovel](https://github.com/freeok/so-novel) 服务端的书籍搜索下载功能。零前端框架依赖，兼容 Chrome 91+ 内核浏览器。

### 核心特性

| 模块 | 能力 |
|------|------|
| 📖 读书 | 全格式导入阅读（TXT/EPUB/PDF/DOCX/PPTX/MOBI/CBZ…）、滚动与翻页双模式、进度全格式记忆、书签与高亮、字体/主题/版式调节 |
| 🗂️ 书架 | 分组管理（文件夹机制）、多选批量操作、顶部实时搜索、RSS 订阅聚合阅读 |
| 📡 RSS | 链接一键解析、自定义同步间隔（默认 24 小时）、按天分组无限滚动阅读、暗色主题自适应 |
| ⬇️ 下书 | SoNovel 集成搜索下载、多格式选择、SSE 实时进度、自动入库 |
| 🛠️ 管理 | 公告系统（Markdown + 媒体上传）、用户管理（封禁/删除）、邀请码、维护模式、在线更新、ZIP 备份/恢复 |

### 界面展示

<img width="2880" height="1739" alt="展示1" src="https://github.com/user-attachments/assets/30091418-ac53-4060-91f4-05fbcb6acd01" />

<img width="2867" height="1915" alt="展示2" src="https://github.com/user-attachments/assets/de3a0d1b-4868-4aa1-ac57-5ced7eace99d" />

### 支持的电子书格式

| 层级 | 格式 | 支持程度 |
|------|------|----------|
| **T1 完美阅读** | TXT, EPUB, PDF | 全文阅读内页、章节解析、目录导航 |
| **T2 转 HTML 阅读** | FB2, HTML, MD, DOCX | 服务端解析转 HTML，分章节阅读 |
| **T2 转 PDF 阅读** | PPTX, PPT | LibreOffice 服务端转 PDF，Office 不可用时回退浏览器渲染 |
| **T3 原生渲染** | MOBI, AZW, AZW3, PRC, CBZ | Foliate 引擎原生打开 |
| **T4 解析管理** | RTF, DJVU, CHM, CBR, PDB, LIT | 上传管理、文本提取、下载导出 |

---

## 📋 使用指南

### 首次使用

1. 访问网站 → 未检测到管理员账户 → 自动跳转管理员注册页
2. 创建管理员账号（用户名/密码各 ≥ 4 个字符）
3. 注册成功后自动登录，进入书架

### 书架

| 操作 | 说明 |
|------|------|
| **添加** | 点击「添加」展开面板：**上传书籍**（多文件）、**新增分组**、**添加RSS订阅** |
| **搜索** | 顶部搜索框实时过滤书架内容；管理员额外可搜索用户账号并跳转后台 |
| **分组** | 分组类似文件夹：点击进入组内视图，左上角返回上一级；分组封面显示组内前 4 本书封面 |
| **右键菜单** | 桌面右键 / 移动端长按卡片：打开、属性、加入分组、多选、删除等 |
| **多选批量** | 菜单「多选」进入复选模式，勾选后底部操作条可批量删除或移动至分组 |
| **RSS 订阅** | 「添加RSS订阅」粘贴链接自动解析标题，设置名称与同步间隔（默认 24 小时）；点击卡片进入文章列表，按天分组、无限滚动 |

### 阅读器

| 操作 | 说明 |
|------|------|
| **阅读模式** | 上下滚动 / 左右翻页，设置中自由切换并记忆 |
| **进度记忆** | 文字书按章节+偏移、EPUB 按 CFI、PDF/PPT 按页码，重开自动回到上次位置 |
| **阅读设置** | 字号、行高、段距、字距、页边距、两端对齐、首行缩进、字体、主题（含文字颜色与自定义取色） |
| **目录** | 侧边栏目录点击直接跳转对应章节 |
| **书签/标注** | 添加书签（可重命名）、选中文字收藏高亮 |
| **PDF/PPT 工具** | 缩放、适应宽度/页面、旋转；移动端支持捏合缩放与双击放大 |

### 下书板块（SoNovel 集成）

| 操作 | 说明 |
|------|------|
| **配置服务器** | 填写 SoNovel 服务器地址和 API Token |
| **搜索/下载** | 搜索网络书籍，选择 EPUB/TXT/HTML/PDF 格式提交下载 |
| **下载管理** | 浮窗实时查看 SSE 进度，完成后自动入库书架 |

### 管理后台

管理员顶栏进入「后台」，包含：

| 模块 | 说明 |
|------|------|
| **公告管理** | Markdown 编辑器 + 实时预览，图片/视频上传（自动转 WebP/MP4），按用户组可见，发布/草稿，排序，不再提示 |
| **用户管理** | 列表查看、封禁（IP 封锁 5 天）/解封、永久删除（附原因公告）、封禁日志 |
| **邀请码** | 开关注册限制、批量生成（次数/有效期/备注）、单个编辑与批量删除 |
| **维护与更新** | 维护模式（仅管理员可登录）、版本检查（GitHub Release）、在线更新与进度页 |
| **备份恢复** | 一键导出 ZIP（数据库 + 密钥 + 上传文件 + 规范书），支持完整恢复 |

### 兼容版（/old）

访问 `/old` 可使用兼容版界面。书架层功能（搜索、分组、多选、RSS、下载）与标准版完全一致，阅读器使用更保守的实现，面向老旧浏览器环境。

---

## 🚀 部署指南

> 两个平台的一键脚本均具备：**启动时选择界面语言（中文/English）**、**自动检测服务器环境**（发行版 / 包管理器 / Python）、**自动检测是否位于中国大陆**（是则默认使用阿里云镜像源：pip / 系统包管理器 / 下载加速，可交互确认），以及 **Nginx 反向代理选装**（交互选择安装或不安装，不安装时直接通过端口访问）。

### Debian / Ubuntu 一键部署（含 Nginx 自动配置）

```bash
curl -sSL https://raw.githubusercontent.com/linlelest/Miniread/main/scripts/install-linux.sh | sudo bash
```

脚本自动完成：选择语言 → 检测发行版与包管理器 → 检测区域并切换镜像源 → 安装 Python3 与依赖 → 下载项目文件 → **systemd 服务一键配置（开机自启）** → 交互选择是否安装 Nginx → 启动服务。

部署后访问：`http://你的服务器IP/miniread`（未装 Nginx 则为 `http://服务器IP:7766`）

### Windows 一键部署（PowerShell）

以管理员身份运行 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/linlelest/Miniread/main/scripts/install-windows.ps1" -OutFile "$env:TEMP\install-miniread.ps1"
& "$env:TEMP\install-miniread.ps1"
```

脚本自动完成：选择语言 → 检测环境（管理员权限 / Python，缺失时自动安装）→ 检测区域并切换镜像源 → 下载项目文件 → 安装依赖 → 配置计划任务（开机自启）→ 交互选择是否安装 Nginx（自动下载并配置 80 端口反代）→ 配置防火墙 → 启动并打开浏览器。

部署后访问：`http://你的本机IP:7766`（装 Nginx 则为 `http://本机IP/miniread/`）

### 手动部署

```bash
git clone https://github.com/linlelest/Miniread.git
cd Miniread
pip install -r requirements.txt
python run.py
# 访问 http://localhost:7766
```

### 手动配置 systemd（Linux 开机自启）

Linux 服务器上推荐用 systemd 管理服务进程：

```bash
sudo tee /etc/systemd/system/miniread.service > /dev/null << 'EOF'
[Unit]
Description=Miniread - Online Reading Platform
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/miniread
Environment=MINIREAD_PRODUCTION=1
Environment=HOST=0.0.0.0
Environment=PORT=7766
ExecStart=/usr/bin/python3 run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now miniread.service

# 常用管理命令
sudo systemctl status miniread
sudo systemctl restart miniread
journalctl -u miniread -f
```

> 注意：`WorkingDirectory` 与 `ExecStart` 需按实际安装路径调整；`Restart=always` 保证进程崩溃后 5 秒自动拉起。

### Gunicorn（Linux 生产环境推荐）

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:7766 app:app
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `7766` | 监听端口 |
| `MINIREAD_SECRET_KEY` | 自动生成 | Flask 密钥（留空则自动持久化到 data/secret_key） |
| `MINIREAD_PRODUCTION` | `0` | 设为 `1` 启用 waitress 生产模式 |

### Nginx 反向代理（手动配置参考）

```nginx
location /miniread/ {
    proxy_pass http://127.0.0.1:7766/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_buffering off;
    proxy_read_timeout 3600s;
}
```

### 可选依赖

| 组件 | 用途 | 缺失时的降级行为 |
|------|------|------------------|
| LibreOffice | PPT/PPTX 转 PDF | 回退浏览器端原生渲染 PPTX |
| ffmpeg | 公告视频转 MP4 | 保留原始上传格式 |
| Pillow | 公告图片转 WebP | 保留原始上传格式 |

---

## 🧰 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.8+ / Flask 3 / SQLite（WAL 模式） |
| 前端 | 原生 HTML/CSS/JS（无框架），现代版 + Chrome 91 兼容版双实现 |
| 阅读引擎 | 自研规范书滚动引擎 / foliate-js（EPUB/MOBI）/ PDF.js / PptxViewJS |
| 外部集成 | SoNovel Server（搜索下载）、GitHub Releases（版本检查） |
| 部署 | systemd / 计划任务 / Nginx / Gunicorn / waitress |

---

## 📚 文档索引

| 文档 | 内容 |
|------|------|
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | **V2.0 / V2.1 完整更新记录** |
| [API.md](API.md) | 全部 REST API 端点参考（认证/书籍/分组/RSS/阅读/下载/管理/公开） |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 技术架构与实现细节（规范书管线、阅读器引擎矩阵、RSS 同步、双版本兼容、数据库表结构、安全特性） |

---

## 🔄 更新机制

管理员进入后台 → 维护与更新 → 点击「检查更新」，系统比对 [GitHub Release](https://github.com/linlelest/Miniread/releases) 最新版本。发现新版本后可在线下载安装，更新期间普通用户看到升级进度页，完成后自动恢复。

---

## 📄 许可证

MIT License

Copyright (c) 2025 Miniread

本项目为原创作品，SoNovel API 集成部分基于 [SoNovel Web](https://github.com/linlelest/so-novel-web) 项目的 API 规范。

---

## 🙏 致谢

- [SoNovel](https://github.com/freeok/so-novel) - 开源小说下载器
- [SoNovel Web](https://github.com/linlelest/so-novel-web) - SoNovel 服务端改版 API 规范
- [Flask](https://flask.palletsprojects.com/) - Python Web 框架
- [ebooklib](https://github.com/aerkalov/ebooklib) - EPUB 处理库
- [foliate-js](https://github.com/johnfactotum/foliate-js) - EPUB/MOBI 渲染引擎
- [PDF.js](https://mozilla.github.io/pdf.js/) - PDF 渲染引擎
- [Linuxdo](https://linux.do/) - L站
