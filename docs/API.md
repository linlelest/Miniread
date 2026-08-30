# Miniread (极读) API 文档 v2.1

> 本文档覆盖 Miniread V2.1 的全部 REST API 端点。技术实现细节见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 基础信息

### 响应格式

所有 API 统一返回 JSON：

```json
{ "code": 200, "message": "OK", "data": { ... } }
```

### 状态码

| code | 含义 |
|------|------|
| 200  | 成功 |
| 400  | 请求参数错误 |
| 401  | 未认证 / Token 无效 |
| 403  | 权限不足 / 账号被封禁 |
| 404  | 资源不存在 |
| 409  | 资源冲突（如重复上传） |
| 500  | 服务器内部错误 |
| 501  | 服务器维护中 |
| 503  | 服务不可用 / 升级中 |

### 认证方式

- **Session Cookie**: 登录后自动设置 `miniread_session` Cookie，浏览器自动携带
- **Authorization Header**: `Authorization: Bearer <session_token>`

---

## 1. 用户认证 `/api/auth/`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/check-admin` | 检查管理员是否已存在 | 无 |
| POST | `/admin-register` | 管理员首次注册（仅当无管理员时可用） | 无 |
| POST | `/login` | 登录 `{username, password, remember}` | 无 |
| POST | `/register` | 用户注册 `{username, password, password2, inviteCode?}` | 无 |
| GET | `/check` | 检查登录状态，返回用户信息 | 无 |
| POST | `/logout` | 登出 | 无 |
| POST | `/change-password` | 修改密码 `{oldPassword, newPassword}` | 需要 |
| POST | `/change-username` | 修改用户名 `{username}` | 需要 |

---

## 2. 书籍与书架 `/api/books`

### 2.1 书架列表

```http
GET /api/books?query=关键词&group=root|<分组id>
```

| 参数 | 说明 |
|------|------|
| `query` | 标题/作者模糊过滤（可省略） |
| `group` | `root`=仅未分组；数字=指定分组；省略=全部 |

返回书籍数组，每项含：`id, title, author, format, kind(''|"rss"), group_id, rss_url, sync_interval, last_synced, cover_url, read_kind, last_read_percent, position, total_chapters, created_at` 等。

### 2.2 书籍 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传书籍（multipart：`file`、`title?`、`author?`、`import_options?` JSON） |
| GET | `/<book_id>` | 书籍详情（含阅读进度） |
| PUT | `/<book_id>` | 更新书籍信息（`{title?, author?, note?}`） |
| DELETE | `/<book_id>` | 删除书籍（清理原文件/规范书/转换产物/RSS 条目） |
| POST | `/<book_id>/reparse` | 用当前导入选项重新解析 |
| GET | `/by-fp/<fingerprint>` | 按指纹取书（阅读器入口用） |

### 2.3 批量操作（V2.1 新增）

```http
POST /api/books/batch-move   { "ids": [1,2,3], "group_id": 5 | null }
POST /api/books/batch-delete { "ids": [1,2,3] }
```

- `batch-move`：`group_id` 为 `null` 表示移出分组；返回 `{moved: N}`，非本人书籍自动忽略
- `batch-delete`：复用单本删除清理逻辑；返回 `{deleted: N}`

### 2.4 内容与文件

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/<book_id>/manifest` | 规范书 manifest（canonical）或 `{format, file_url, convert_status}`（native/pdf/pptx） |
| GET | `/<book_id>/section/<n>` | 第 n 章 HTML |
| GET | `/<book_id>/asset/<name>` | 规范书内资产（图片等） |
| GET | `/<book_id>/cover` | 封面图片 |
| GET | `/<book_id>/file` | 原始文件 |
| GET | `/<book_id>/converted` | PPT/PPTX 转换后的 PDF |
| GET | `/<book_id>/download` | 下载源文件 |

### 2.5 导入默认值

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/api/import/defaults` | 上传导入选项默认值（encoding/chapter_regex/toc_mode 等） |

---

## 3. 分组 `/api/groups`（V2.1 新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/groups` | 当前用户全部分组，含 `member_count`，按 `sort_order, created_at` 排序 |
| POST | `/api/groups` | 创建 `{name}`（strip 后非空，≤100 字符） |
| PUT | `/api/groups/<gid>` | 重命名 `{name}` |
| DELETE | `/api/groups/<gid>` | 删除分组；组内书籍 `group_id` 自动置 NULL（回到未分组） |

> 分组归属校验：非本人分组返回 404。

---

## 4. RSS 订阅 `/api/rss`（V2.1 新增）

> RSS 订阅在数据层复用 books 表（`kind='rss'`），因此书架展示、封面、分组、删除等复用书籍接口；以下为订阅专属端点。

### 4.1 创建订阅

```http
POST /api/rss
{ "url": "https://example.com/rss.xml", "name": "可选，默认取站点标题", "interval": 24 }
```

- `interval` 为同步间隔小时数，最小 1，无上限
- 创建后立即抓取一次；返回 `{book_id, title, items: 首次入库数}`
- 抓取/解析失败返回 400 `订阅解析失败，请检查链接`

### 4.2 修改订阅

```http
PUT /api/rss/<book_id>
{ "name": "新名称", "interval": 6 }
```

两者均可选；返回 `{title, sync_interval}`。

### 4.3 手动同步

```http
POST /api/rss/<book_id>/sync
```

返回 `{added: 新增条数, last_synced: epoch}`。后台另有 daemon 线程每 30 分钟扫描到期订阅（`last_synced + interval*3600`）自动同步。

### 4.4 文章分页

```http
GET /api/rss/<book_id>/items?page=1&size=20
```

返回：

```json
{ "total": 100, "page": 1, "size": 20,
  "items": [ { "id": 1, "guid": "...", "title": "...", "link": "...", "published": 1700000000.0, "content": "<p>净化后的 HTML</p>" } ] }
```

按 `published DESC, id DESC` 排序；`content` 入库前已净化（移除 script/iframe/事件属性/javascript: 协议/内联颜色声明）。

---

## 5. 阅读 `/api/reading/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/<book_id>/settings` | 按书阅读设置（font_size/line_spacing/theme_preset/text_color/page_mode 等） |
| GET/PUT | `/settings` | 全局默认阅读设置 |
| PUT/POST | `/<book_id>/position` | 保存进度 `{position, chapter_title, position_data}`；`position_data` 类型：`{type:'canonical', chapter, offset}` / `{type:'cfi', cfi, section}` / `{type:'pdf', page}` / `{type:'pptx', slide}`；POST 兼容 sendBeacon |
| GET/POST | `/<book_id>/bookmarks` | 书签列表 / 添加书签 |
| PUT/DELETE | `/<book_id>/bookmarks/<mark_id>` | 重命名 / 删除书签 |
| GET/POST | `/<book_id>/highlights` | 高亮列表 / 添加高亮 |
| PUT/DELETE | `/<book_id>/highlights/<hl_id>` | 修改备注 / 删除高亮 |

---

## 6. SoNovel 下载 `/api/download/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/config` | SoNovel 服务器地址与 API Token |
| GET | `/search?keyword=` | 搜索网络书籍 |
| POST | `/fetch` | 提交下载任务 `{book_url, format}` |
| GET | `/tasks` | 任务列表 |
| DELETE | `/tasks/<task_id>` | 删除任务记录 |
| GET | `/progress` | SSE 实时进度流（text/event-stream） |

---

## 7. 管理员 `/api/admin/`

### 7.1 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/users` | 用户列表 |
| POST | `/users/ban` | 封禁/解封 `{user_id, action}`；封禁含 IP 封锁 5 天 |
| POST | `/users/delete` | 永久删除 `{user_id, reason}`，首页显示删除公告 |

### 7.2 公告管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/announcements` | 全部公告 |
| POST | `/announcements` | 创建（Markdown 内容、visibility、show_dismiss、pinned、draft） |
| PUT | `/announcements/<ann_id>` | 编辑（自动刷新"不再提示"记忆） |
| DELETE | `/announcements/<ann_id>` | 删除（联动清理引用的媒体文件） |
| POST | `/announcements/upload` | 媒体上传（图片→WebP / 视频→MP4），返回插入用 URL |
| PUT | `/announcements/reorder` | 拖拽排序 `{ids: [...]}` |

### 7.3 邀请码

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/invite-codes` | 列表 |
| POST | `/invite-codes/generate` | 批量生成 `{count, max_uses, expires_days, note}` |
| PUT | `/invite-codes/<code_id>` | 编辑 |
| DELETE | `/invite-codes/<code_id>` | 删除 |
| POST | `/invite-codes/batch-delete` | 批量删除 |
| PUT | `/invite-codes/config` | 注册限制开关与提示文字 |

### 7.4 维护 / 更新 / 日志 / 备份

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/maintenance` | 维护模式状态 / 开关与公告 |
| GET | `/update/check` | 比对 GitHub Release 最新版本 |
| POST | `/update/apply` | 下载安装更新（更新期间全站进入升级页） |
| GET | `/banned-log` | 封禁/删除日志 |
| GET | `/export` | 导出 ZIP 备份（数据库 + secret_key + uploads + 规范书） |
| POST | `/import` | 从 ZIP 备份恢复（含路径穿越防护） |

---

## 8. 公开接口 `/api/public/`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/announcements` | 按当前用户组可见的公告列表 | 无 |
| GET | `/ann-media/<name>` | 公告媒体文件 | 无 |
| GET | `/banned-log` | 封号记录（透明化） | 无 |
| GET | `/maintenance` | 维护状态与公告 | 无 |
| GET | `/update-status` | 当前版本与升级进度 | 无 |
| GET | `/invite-status` | 邀请码限制开关与提示 | 无 |
