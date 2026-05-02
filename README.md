<div align="center">
  <h1>📚 Miniread (极读)</h1>
  <p><strong>在线阅读管理平台 —— 兼容性第一，功能强大第二，美观第三</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.8+-blue" alt="Python">
    <img src="https://img.shields.io/badge/Flask-3.0-green" alt="Flask">
    <img src="https://img.shields.io/badge/Database-SQLite-orange" alt="SQLite">
    <img src="https://img.shields.io/badge/Browser-Chrome%2091+-success" alt="Chrome">
    <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
  </p>
</div>

---

## 📖 概述

**Miniread（极读）**是一个轻量级、高兼容性的在线阅读管理平台。支持多种电子书格式的导入与阅读，同时集成了 [SoNovel](https://github.com/freeok/so-novel) 服务端的书籍搜索下载功能。

### 设计理念

| 优先级 | 理念 | 说明 |
|--------|------|------|
| **1** | **兼容性第一** | 兼容 Chrome 91+ 内核浏览器，不依赖任何前端框架，纯 HTML/CSS/JS 实现 |
| **2** | **功能强大第二** | 全格式电子书支持、完整用户系统、SoNovel 集成下载、管理员后台 |
| **3** | **美观第三** | 简洁优雅的 UI，护眼阅读模式，响应式布局 |

### 界面展示
<img width="2880" height="1739" alt="展示1" src="https://github.com/user-attachments/assets/30091418-ac53-4060-91f4-05fbcb6acd01" />
<img width="2867" height="1915" alt="展示2" src="https://github.com/user-attachments/assets/de3a0d1b-4868-4aa1-ac57-5ced7eace99d" />

### 核心功能

```
┌─────────────────────────────────────────────────────────┐
│                     Miniread (极读)                       │
├───────────────┬──────────────────┬──────────────────────┤
│   读  书      │    下  书        │     管  理           │
│               │                  │                      │
│ · 导入本地书籍 │ · 搜索网络书籍    │ · 修改用户名/密码     │
│ · 书架增删改查 │ · SoNovel API   │ · 退出登录           │
│ · 自动目录识别 │ · 多格式下载     │                      │
│ · 阅读器       │ · 下载进度浮窗   │  【管理员额外】       │
│ · 书签/高亮    │ · 自动入库      │ · 公告管理           │
│ · 字体/背景调节│                  │ · 用户管理(封禁/删除) │
│ · 阅读进度     │                  │ · 邀请码管理         │
│               │                  │ · 维护模式           │
│               │                  │ · 版本更新           │
└───────────────┴──────────────────┴──────────────────────┘
```

### 支持的电子书格式

| 层级 | 格式 | 支持程度 |
|------|------|----------|
| **T1 完美阅读** | TXT, EPUB, PDF | 全文阅读内页，章节解析，目录导航 |
| **T2 转HTML阅读** | FB2, HTML, MD, DOCX | 服务端解析转HTML，分章节阅读 |
| **T3 解析管理** | MOBI, AZW3, RTF, DJVU, CHM, CBR, CBZ, PRC, PDB, LIT | 上传管理、文本提取、下载导出 |

---

## 🚀 一键部署

### Debian / Ubuntu (含 Nginx 自动配置)

```bash
curl -sSL https://raw.githubusercontent.com/linlelest/Miniread/main/scripts/install-linux.sh | sudo bash
```

脚本自动完成：
- ✅ 安装 Python3 + pip
- ✅ 安装 Nginx
- ✅ 下载最新项目文件
- ✅ 安装 Python 依赖
- ✅ 配置 systemd 服务（开机自启）
- ✅ 配置 Nginx 反向代理
- ✅ 启动所有服务

**部署后访问：**
```
http://你的服务器IP/miniread
```

### Windows (PowerShell)

**以管理员身份**运行 PowerShell，执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/linlelest/Miniread/main/scripts/install-windows.ps1" -OutFile "$env:TEMP\install-miniread.ps1"
& "$env:TEMP\install-miniread.ps1"
```

脚本自动完成：
- ✅ 检查/安装 Python3
- ✅ 下载项目文件
- ✅ 安装依赖
- ✅ 配置计划任务（开机自启）
- ✅ 配置防火墙规则
- ✅ 自动打开浏览器

**部署后访问：**
```
http://你的本机IP:7766
```

### 手动部署

```bash
# 1. 克隆仓库
git clone https://github.com/linlelest/Miniread.git
cd Miniread/miniread

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python run.py

# 4. 访问 http://localhost:7766
```

### 使用 Gunicorn (Linux 生产环境推荐)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:7766 app:app
```

---

## 📋 使用指南

### 首次使用

1. 访问网站 → 未检测到管理员账户 → 自动跳转管理员注册页
2. 创建管理员账号（用户名/密码各 ≥4 个字符）
3. 注册成功后自动登录，进入主界面

### 读书板块

| 操作 | 说明 |
|------|------|
| **导入书籍** | 点击书架上的「+ 导入书籍」或拖拽区域，支持多文件同时上传 |
| **书籍阅读** | 点击书籍封面进入阅读器，自动识别目录结构 |
| **阅读设置** | 字号、行间距、背景色（含护眼/夜间模式）、字体、页面宽度 |
| **章节导航** | 目录浮窗、上一章/下一章按钮、进度条 |
| **书签** | 阅读时点击工具栏 🔖 添加书签，设置面板可查看所有书签 |
| **文字收藏** | 选中文字后确认收藏，高亮内容可在设置面板查看 |
| **下载/删除** | 每个书籍卡片底部有下载原始文件和删除按钮 |

### 下书板块（SoNovel 集成）

| 操作 | 说明 |
|------|------|
| **配置服务器** | 点击右上角 ⚙ 设置，填写 SoNovel 服务器地址和 API Token |
| **搜索书籍** | 在中央搜索框输入书名/作者，回车或点击搜索 |
| **选择格式** | 搜索结果每行可选择 EPUB/TXT/HTML/PDF 格式 |
| **下载** | 点击下载按钮提交任务 |
| **下载管理** | 右下角浮动按钮 📥 打开下载管理浮窗，实时查看进度 |
| **自动入库** | 下载完成后自动添加到读书书架，弹出提示 |

### 管理板块（普通用户）

| 操作 | 说明 |
|------|------|
| **修改用户名** | 输入新用户名保存（≥4个字符） |
| **修改密码** | 输入原密码和新密码（≥4个字符） |
| **退出登录** | 清除会话并跳转登录页 |

### 管理员后台

管理员在顶栏可见「管理员」按钮，点击进入管理后台，包含四个子模块：

#### 📢 公告管理
- 多条公告，支持 Markdown 内容
- 可拖动排序（桌面端拖拽）
- 可见范围设置（所有用户 / 仅注册用户）
- 是否显示「不再提示」按钮
- 置顶开关
- 启用/禁用切换

#### 👥 用户管理
- 查看所有注册用户（ID、用户名、角色、状态、注册时间）
- **封禁用户**：强制下线 + IP 封锁 5 天，5 天后可重新注册新号
- **解封用户**：恢复被封禁用户的正常访问
- **永久删除**：填写原因后删除用户，首页显示删除公告
- 封禁/删除日志完整记录

#### 🔑 邀请码管理
- 开启/关闭邀请码注册限制
- 自定义提示文字
- **批量生成**：设置数量、使用次数（0=不限）、有效期（天）、备注
- 单个编辑：修改次数限制、备注
- 单个/批量删除

#### 🔧 维护与更新
- **维护模式**：开启后全站进入维护页，管理员可通过 API 访问
- 维护公告 Markdown 编辑器
- **版本更新**：
  - 显示当前版本
  - 点击「检查更新」比对 GitHub Release
  - 发现新版本后显示「下载并安装更新」
  - 更新期间普通用户自动跳转升级页（显示进度条）
  - 更新完成后自动恢复

---

## 🏗️ 技术架构

### 技术栈

```
Frontend          Backend           Database
┌──────────┐     ┌──────────┐      ┌──────────┐
│  HTML5   │────▶│  Flask   │─────▶│  SQLite  │
│  CSS3    │     │  (Python)│      │  (单文件) │
│  JS ES5  │     │          │      │          │
│  (无框架) │     │  RESTful │      │  WAL模式  │
└──────────┘     │  API     │      └──────────┘
                 └──────────┘
                      │
                 ┌────┴────┐
                 │ SoNovel │  ← 外部API集成
                 │ Server  │
                 └─────────┘
```

### 项目结构

```
miniread/
├── app.py                      # Flask 应用入口，蓝图注册，路由定义
├── config.py                   # 全局配置（路径、端口、版本、格式限制）
├── database.py                 # SQLite 数据库初始化、建表、索引、设置读写
├── run.py                      # 启动脚本（开发/生产模式切换）
├── requirements.txt            # Python 依赖列表
│
├── routes/                     # API 路由层
│   ├── auth.py                 #   用户认证（登录/注册/登出/管理员注册/改密）
│   ├── books.py                #   书籍管理（上传/CRUD/目录/内容/阅读进度/书签/高亮）
│   ├── download.py             #   SoNovel集成（搜索/下载/SSE进度/任务管理）
│   ├── admin.py                #   管理员接口（用户管理/公告/邀请码/维护/更新）
│   └── public.py               #   公开接口（公告/封号日志/维护状态/更新状态）
│
├── services/                   # 业务服务层
│   ├── book_parser.py          #   电子书解析（EPUB/FB2/DOCX/HTML/MD/RTF/TXT）
│   ├── novel_api.py            #   SoNovel API 调用封装
│   └── update.py               #   版本更新逻辑
│
├── utils/                      # 工具函数
│   └── helpers.py              #   密码哈希/token生成/认证装饰器/章节检测/响应格式化
│
├── static/                     # 前端静态资源
│   ├── css/
│   │   ├── style.css           #     全局样式、工具类、滚动条美化、响应式
│   │   └── reader.css          #     阅读器专属样式（页面版式、设置面板、夜间模式）
│   └── js/
│       ├── app.js              #     主应用逻辑（书架/阅读器/下载/用户设置）
│       └── admin.js            #     管理后台逻辑（公告/用户/邀请码/维护更新）
│
├── templates/                  # HTML 模板
│   ├── index.html              #   主界面（读书/下书/管理 三Tab SPA）
│   ├── login.html              #   登录/注册页面
│   ├── admin.html              #   管理员后台（侧边栏 + 四个子模块）
│   ├── maintenance.html        #   维护页面（公告浮窗）
│   └── upgrade.html            #   升级进度页面（实时进度条）
│
├── uploads/                    # 用户上传书籍存储目录
├── downloads/                  # 临时下载缓存目录
├── data/                       # SQLite 数据库文件位置
└── scripts/                    # 一键部署脚本
    ├── install-windows.ps1     #   Windows PowerShell 安装脚本
    └── install-linux.sh        #   Debian/Ubuntu bash 安装脚本
```

### 数据库表结构

```
┌─────────────┐   ┌───────────────┐   ┌─────────────┐
│    users    │   │    books      │   │  bookmarks  │
├─────────────┤   ├───────────────┤   ├─────────────┤
│ id          │◀──│ user_id (FK)  │◀──│ book_id(FK) │
│ username    │   │ title         │   │ user_id(FK) │
│ password_hash│  │ author        │   │ chapter     │
│ role        │   │ format        │   │ position    │
│ banned      │   │ file_path     │   │ note        │
│ banned_ip   │   │ file_size     │   │ created_at  │
│ ban_expires │   │ source        │   └─────────────┘
│ deleted     │   │ last_read_pos │
│ delete_reason│  │ total_chapters│   ┌─────────────┐
│ created_at  │   │ created_at    │   │ highlights  │
└─────────────┘   └───────────────┘   ├─────────────┤
                                      │ book_id(FK) │
┌─────────────┐   ┌───────────────┐   │ selected_text│
│  sessions   │   │ announcements │   │ chapter     │
├─────────────┤   ├───────────────┤   │ color       │
│ user_id(FK) │   │ content       │   │ note        │
│ token       │   │ visibility    │   │ created_at  │
│ expires_at  │   │ show_dismiss  │   └─────────────┘
│ created_at  │   │ pinned        │
└─────────────┘   │ sort_order    │   ┌──────────────┐
                  │ active        │   │invite_codes  │
┌─────────────┐   │ created_at    │   ├──────────────┤
│   settings  │   └───────────────┘   │ code         │
├─────────────┤                       │ max_uses     │
│ key (PK)    │   ┌───────────────┐   │ used_count   │
│ value       │   │  banned_log   │   │ expires_at   │
└─────────────┘   ├───────────────┤   │ note         │
                  │ username      │   │ created_at   │
┌───────────────┐ │ reason        │   └──────────────┘
│download_tasks │ │ action        │
├───────────────┤ │ created_at    │   ┌───────────────┐
│ user_id(FK)   │ └───────────────┘   │novel_server   │
│ book_name     │                     │    _config    │
│ format        │ ┌───────────────┐   ├───────────────┤
│ url           │ │reading_setting│   │ user_id(FK)   │
│ dlid          │ ├───────────────┤   │ server_url    │
│ status        │ │ user_id(FK)   │   │ api_token     │
│ progress      │ │ book_id(FK)   │   └───────────────┘
│ error_message │ │ font_size     │
└───────────────┘ │ bg_color      │
                  │ text_color    │
                  │ line_spacing  │
                  │ para_spacing  │
                  │ font_family   │
                  └───────────────┘
```

### API 端点一览

#### 认证 (/api/auth/)
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/check-admin` | 检查管理员是否存在 | 无 |
| POST | `/admin-register` | 管理员首次注册 | 无 |
| POST | `/login` | 用户登录 | 无 |
| POST | `/register` | 用户注册（含邀请码） | 无 |
| GET | `/check` | 检查登录状态 | 无 |
| POST | `/logout` | 登出 | 无 |
| POST | `/change-password` | 修改密码 | 需要 |
| POST | `/change-username` | 修改用户名 | 需要 |

#### 书籍 (/api/books/)
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 获取书架列表 | 需要 |
| POST | `/upload` | 上传书籍 | 需要 |
| GET | `/<id>` | 书籍详情 | 需要 |
| PUT | `/<id>` | 更新书籍信息 | 需要 |
| DELETE | `/<id>` | 删除书籍 | 需要 |
| GET | `/<id>/toc` | 获取目录 | 需要 |
| GET | `/<id>/content` | 获取章节内容 | 需要 |
| GET | `/<id>/download` | 下载源文件 | 需要 |

#### 阅读 (/api/reading/)
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET/PUT | `/<book_id>/settings` | 阅读设置 | 需要 |
| PUT | `/<book_id>/position` | 保存进度 | 需要 |
| GET | `/<book_id>/bookmarks` | 书签列表 | 需要 |
| POST/DELETE | `/<book_id>/bookmarks` | 添加/删除书签 | 需要 |
| GET | `/<book_id>/highlights` | 高亮列表 | 需要 |
| POST/DELETE | `/<book_id>/highlights` | 添加/删除高亮 | 需要 |

#### SoNovel 下载 (/api/download/)
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET/PUT | `/config` | SoNovel服务器配置 | 需要 |
| GET | `/search` | 搜索书籍 | 需要 |
| POST | `/fetch` | 开始下载 | 需要 |
| GET | `/tasks` | 任务列表 | 需要 |
| DELETE | `/tasks/<id>` | 删除任务 | 需要 |
| GET | `/progress` | SSE下载进度流 | 需要 |

#### 管理员 (/api/admin/)
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/users` | 用户列表 | 管理员 |
| POST | `/users/ban` | 封禁/解封用户 | 管理员 |
| POST | `/users/delete` | 永久删除用户 | 管理员 |
| CRUD | `/announcements` | 公告管理 | 管理员 |
| PUT | `/announcements/reorder` | 排序 | 管理员 |
| CRUD | `/invite-codes` | 邀请码管理 | 管理员 |
| POST | `/invite-codes/generate` | 批量生成 | 管理员 |
| POST | `/invite-codes/batch-delete` | 批量删除 | 管理员 |
| PUT | `/invite-codes/config` | 邀请码设置 | 管理员 |
| GET/PUT | `/maintenance` | 维护模式 | 管理员 |
| GET | `/update/check` | 检查更新 | 管理员 |
| POST | `/update/apply` | 执行更新 | 管理员 |
| GET | `/banned-log` | 封禁日志 | 管理员 |

#### 公开 (/api/public/)
| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/announcements` | 公开公告 | 无 |
| GET | `/banned-log` | 封号记录 | 无 |
| GET | `/maintenance` | 维护状态 | 无 |
| GET | `/update-status` | 更新进度 | 无 |
| GET | `/invite-status` | 邀请码状态 | 无 |

---

## 🔧 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `7766` | 监听端口 |
| `SECRET_KEY` | 内置默认值 | Flask 密钥（生产环境务必修改） |
| `MINIREAD_PRODUCTION` | `0` | 设为 `1` 启用 waitress 生产模式 |

### Nginx 反向代理（手动配置）

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

---

## 🔄 更新机制

Miniread 支持从 GitHub Release 自动检查和安装更新：

1. 管理员进入后台 → 维护与更新 → 点击「检查更新」
2. 系统比对当前版本与 [GitHub Release](https://github.com/linlelest/Miniread/releases) 最新版
3. 若有新版本，点击「下载并安装更新」
4. 系统自动下载更新包 → 解压 → 替换文件 → 重启服务
5. 更新期间普通用户看到升级进度页，管理员不受影响
6. 更新完成后全站恢复

---

## 🛡️ 安全特性

| 特性 | 实现 |
|------|------|
| 密码存储 | bcrypt 哈希 |
| Session 管理 | 随机 64 位 token，可设置过期时间 |
| 记住登录 | 30 天持久会话 |
| CSRF 防护 | HttpOnly + SameSite=Lax Cookie |
| IP 封禁 | 封禁用户时封锁 IP 5 天 |
| SQL 注入防护 | 参数化查询 |
| 维护模式 | 管理员 API 白名单，普通用户仅访问维护页 |
| 访问控制 | 认证装饰器 + 角色检查装饰器 |

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
