# Miniread 技术架构与实现细节

> 本文档面向开发者，描述 V2.1 的内部实现。使用说明请见 [README](../README.md)，接口定义见 [API 文档](../API.md)，版本变更见 [更新记录](CHANGELOG.md)。

---

## 项目结构

```
miniread/
├── app.py                      # Flask 应用工厂：全局中间件（更新/维护/首次注册拦截）、蓝图注册、页面路由、静态资源缓存策略
├── config.py                   # 全局配置（路径、端口、版本、格式白名单 FORMAT_KIND）
├── database.py                 # SQLite 初始化：建表、索引、幂等迁移（try/except ALTER 模式）、设置读写、session 清理线程
├── run.py                      # 启动脚本（开发 / waitress 生产模式切换）
├── requirements.txt
│
├── routes/                     # API 路由层（全部返回统一 JSON 封装 {code, message, data}）
│   ├── auth.py                 #   认证：管理员注册、登录/注册（邀请码）、改密/改名、会话检查
│   ├── books.py                #   书籍与书架：上传、CRUD、批量移动/删除、分组 CRUD、规范书 manifest/章节/资产、封面、进度、书签、高亮、阅读设置
│   ├── rss.py                  #   RSS 订阅：创建（解析+首抓）、改名/改间隔、手动同步、文章分页
│   ├── download.py             #   SoNovel 集成：配置、搜索、下载任务、SSE 进度流
│   ├── admin.py                #   管理员：用户管理、公告（含媒体上传）、邀请码、维护模式、更新检查/应用、封禁日志、ZIP 导出/导入
│   └── public.py               #   公开接口：公告、公告媒体、封号日志、维护状态、更新状态、邀请码状态
│
├── services/                   # 业务服务层
│   ├── book_store.py           #   规范书存储：manifest 读写、章节/资产落盘、封面缓存、版本迁移
│   ├── parser_epub.py          #   EPUB 解析（ebooklib + zip 回退，导航过滤与目录重映射）
│   ├── parser_docx.py          #   DOCX 解析（中英文标题层级）
│   ├── parser_fb2.py           #   FB2 解析
│   ├── parser_html.py          #   HTML / MD / RTF 解析
│   ├── convert_office.py       #   LibreOffice 无头转换（PPT/PPTX → PDF，跨平台 soffice 探测）
│   ├── rss_sync.py             #   RSS 解析（RSS 2.0 + Atom）、正文净化、同步循环线程
│   ├── sanitizer.py            #   规范书章节 HTML 净化
│   ├── novel_api.py            #   SoNovel API 封装
│   └── update.py               #   GitHub Release 版本检查与在线更新
│
├── utils/helpers.py            # 密码哈希、token、认证装饰器、章节检测、响应格式化
│
├── static/
│   ├── css/                    # tokens（主题变量）/ components / pages / reader / v21 样式
│   ├── js/
│   │   ├── app.modern.js       # 共享工具（api/esc/toast/modal/confirmDialog/debounce/mdAnn 渲染）
│   │   ├── main.modern.js      # 书架层（搜索/添加面板/分组/多选/长按/RSS 入口）—— 标准版与 /old 共用
│   │   ├── reader.modern.js    # 阅读器编排（引擎选择、设置抽屉、进度、书签）
│   │   ├── foliate-bridge.js   # foliate-js 桥接（EPUB/MOBI 分页与滚动）
│   │   ├── pdf-viewer.js       # PDF.js 滚动/翻页查看器（窗口化渲染）
│   │   ├── pptx-viewer.js      # PPTX 原生渲染（旋转/缩放/自动适配）
│   │   ├── rss-viewer.js       # RSS 阅读视图（按天分组、无限滚动）—— 双版本共用
│   │   ├── admin.modern.js     # 管理后台
│   │   ├── loader.js           # 第三方库按需加载（pdf.js / foliate / pptx / JSZip）
│   │   ├── detect.js / theme.js# 浏览器探测 / 主题
│   │   ├── app.legacy.js       # 兼容版共享工具（Chrome 91 语法）
│   │   └── reader.legacy.js    # 兼容版阅读器
│   └── vendor/                 # 本地化的第三方库
│
├── templates/                  # 模板（landing/login/main/admin/maintenance/upgrade + old/ 兼容版全套）
├── uploads/                    # 用户上传原始文件（按用户分目录）
├── data/                       # SQLite 数据库、secret_key、规范书目录 data/books/<id>/
├── tests/                      # 单元与 API 冒烟测试
└── scripts/                    # 一键部署脚本（Windows PowerShell / Linux bash）
```

---

## 阅读引擎路由矩阵

上传时按扩展名在 `Config.FORMAT_KIND` 中决定 `read_kind`，阅读器据此选择引擎：

| read_kind | 格式 | 引擎 | 进度定位 |
|-----------|------|------|----------|
| `canonical` | TXT/EPUB/DOCX/FB2/HTML/MD/RTF | 自研滚动引擎（章节窗口化渲染 ±4）或 Foliate 分页引擎（翻页模式，DOCX 仅滚动） | 章节+偏移 / CFI |
| `native` | MOBI/AZW/AZW3/PRC/CBZ | Foliate 引擎直接打开原文件 | CFI |
| `pdf` | PDF | PDF.js 滚动/翻页查看器 | 页码 |
| `pptx` | PPT/PPTX | 转换完成后走 `pdf`；LibreOffice 缺失时回退 PptxViewJS 浏览器渲染 | 页码 / 幻灯片序号 |

进度保存走 `PUT/POST /api/reading/<id>/position`，`position_data` 携带类型化定位（`{type:'canonical'|'cfi'|'pdf'|'pptx', ...}`），sendBeacon（POST）与 PUT 双通道兼容。

---

## 规范书管线

```
上传文件 ──▶ parser_*.py 解析 ──▶ sanitizer 净化 ──▶ book_store 落盘
                                                      ├─ data/books/<id>/manifest.json（章节索引/目录/封面/导入选项/gen 版本）
                                                      ├─ data/books/<id>/sections/n.html
                                                      └─ data/books/<id>/assets/（图片等）
```

- **manifest.gen 版本迁移**：打开旧书时自动检查并迁移到当前 schema（当前 gen 4）
- **目录识别**：TXT 中英文章节正则（可自定义 regex/编码/分卷），EPUB 导航文档过滤 + 链接密度启发式剔除伪目录，无章节书自动 400 行分块
- **章节窗口化**：滚动引擎只渲染当前章节 ±4，配合 40% 视口判定线推进章节进度，避免超长书籍一次性渲染

---

## Office 转换链

```
PPT/PPTX 上传 ──▶ convert_status='pending'（书架卡片模糊遮罩）
              ──▶ LibreOffice 无头转换（soffice --headless --convert-to pdf，带进程锁与超时）
              ├─ 成功 ──▶ convert_status='done'，manifest 指向转换后 PDF
              └─ 失败/无 LibreOffice ──▶ 前端回退 PptxViewJS 浏览器渲染（sldSz 真实宽高比 + 旋转补偿）
```

---

## RSS 同步管线

```
POST /api/rss ──▶ fetch_feed（urllib, UA 标识, 20s 超时）──▶ parse_feed（RSS 2.0 / Atom）
              ──▶ sanitize_html 净化（script/iframe/事件属性/javascript:/内联颜色剥离）
              ──▶ INSERT books(kind='rss') + 首次抓取 rss_items（UNIQUE(book_id,guid) 去重）

后台线程（daemon，每 1800s）：扫描 last_synced + sync_interval*3600 到期的订阅
              ──▶ 逐个同步，单个失败静默跳过下轮重试
```

- 解析双协议：RSS 2.0（item/guid/pubDate/content:encoded）与 Atom（entry/id/published/content），日期双格式解析（RFC 822 / ISO 8601）
- 净化包含内联颜色剥离（`color/background-*`），配合阅读视图的 `!important` 主题色覆盖，保证暗色模式可读
- 阅读视图按 `published DESC` 分页（每页 20），前端按天分组渲染 + IntersectionObserver 无限滚动

---

## 双版本兼容策略

| 层 | 标准版 | 兼容版（/old） | 策略 |
|----|--------|----------------|------|
| 书架/管理 | main.modern.js | **共用 main.modern.js** | 同一实现自动同步 |
| 模板 | main.html 等 | old/*.html | 结构同步修改（引用相同 JS） |
| 阅读器 | reader.modern.js + 引擎组 | reader.legacy.js | 独立实现，保守语法 |
| RSS 阅读视图 | rss-viewer.js | **共用** | Chrome 91 兼容语法编写 |
| 主题 | CSS 变量（data-theme） | 同 | 变量层双版一致 |

兼容目标为 Chrome 91 内核：可使用可选链等 ES2020 语法，禁用 top-level await 与 ES Module 顶层特性（rss-viewer 以普通 script 提供）。

---

## 数据库表结构

```
users ──┬──< books ──┬──< bookmarks
        │            ├──< highlights
        │            ├──< reading_settings
        │            ├──< rss_items
        │            └──> book_groups（group_id，可空 = 未分组）
        ├──< sessions
        ├──< download_tasks
        ├──< novel_server_config
        └──< user_prefs

books 关键列：id / user_id / title / author / format / kind(''|"rss") / file_path /
             rss_url / sync_interval / last_synced / group_id / cover_path /
             fingerprint / canonical_status / canonical_dir / convert_status / convert_path /
             last_read_position / last_read_chapter / position_data / total_chapters / created_at

book_groups：id / user_id / name / sort_order / created_at
rss_items： id / book_id / guid / title / link / published / content（UNIQUE(book_id, guid)）
其余：announcements / invite_codes / banned_log / settings / download_tasks / novel_server_config / user_prefs
```

- 外键级联已开启（PRAGMA foreign_keys=ON），删除书籍自动清理 rss_items
- 迁移采用 try/except ALTER 幂等模式，旧库启动时自动补列补表

---

## 全局中间件（app.py before_request）

1. **更新拦截**：`updating=1` 时非管理员全部跳转 /upgrade（API 返回 503）
2. **维护拦截**：`maintenance_mode=1` 时非管理员跳转 /maintenance（API 501），管理员白名单通行
3. **首次注册拦截**：无管理员账户时强制跳转 /login 完成管理员注册
4. **after_request**：静态资源响应 `Cache-Control: no-cache`（协商缓存，代码更新即时生效）

---

## 安全特性

| 特性 | 实现 |
|------|------|
| 密码存储 | bcrypt 哈希 |
| 会话管理 | 随机 token，可选 30 天持久化，HttpOnly + SameSite=Lax Cookie |
| 访问控制 | require_auth / 管理员角色装饰器；资源归属全部按 user_id 过滤 |
| SQL 注入防护 | 全量参数化查询 |
| 上传防护 | 扩展名白名单 + secure_filename + 内容校验 |
| 路径安全 | 规范书资产/公告媒体读取含路径穿越校验 |
| RSS 内容安全 | 入库前净化 script/iframe/事件属性/javascript: 协议/内联颜色 |
| IP 封禁 | 封禁用户同时封锁注册 IP 5 天 |
| 备份导入防护 | ZIP 条目路径穿越校验 |

---

## 测试

```
cd miniread
python -m unittest discover -s tests
```

覆盖：解析器（TXT/EPUB/DOCX/FB2/HTML/MD/RTF）、规范书存储、API 冒烟（认证/上传/阅读/书签）、V2.1 迁移/分组/RSS/批量操作。临时环境隔离，不触碰真实数据。
