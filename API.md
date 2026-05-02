# Miniread (极读) API 文档 v1.0

> 本文档适用于 Miniread 阅读管理平台的所有 API 端点。

---

## 基础信息

### 响应格式

所有 API 统一返回 JSON：

```json
{ "code": 200, "message": "OK", "data": { ... } }
```

错误时：

```json
{ "code": 401, "message": "未登录或会话已过期", "data": null }
```

### 状态码

| code | 含义 |
|------|------|
| 200  | 成功 |
| 400  | 请求参数错误 |
| 401  | 未认证 / Token 无效 |
| 403  | 权限不足 / 账号被封禁 |
| 404  | 资源不存在 |
| 409  | 资源冲突（如用户名已存在） |
| 500  | 服务器内部错误 |
| 501  | 服务器维护中 |
| 503  | 服务不可用 / 升级中 |

### 认证方式

- **Session Cookie**: 登录后自动设置 `miniread_session` Cookie，浏览器自动携带
- **Authorization Header**: `Authorization: Bearer <session_token>`（API 调用推荐）

---

## 1. 用户认证 `/api/auth/`

### 1.1 检查管理员是否存在

```http
GET /api/auth/check-admin
```

无需认证。

**响应：**
```json
{ "code": 200, "data": { "hasAdmin": false } }
```

### 1.2 管理员首次注册

```http
POST /api/auth/admin-register
Content-Type: application/json

{ "username": "admin", "password": "mypassword" }
```

无需认证。仅限无管理员时可用。

**响应：**
```json
{ "code": 200, "data": { "sessionId": "abc...", "username": "admin", "role": "admin", "message": "管理员注册成功" } }
```

### 1.3 用户登录

```http
POST /api/auth/login
Content-Type: application/json

{ "username": "myuser", "password": "mypassword", "remember": true }
```

无需认证。`remember` 可选（true=30天，false=1天）。

**响应：**
```json
{ "code": 200, "data": { "sessionId": "abc...", "username": "myuser", "role": "user" } }
```

设置 Cookie: `miniread_session`

### 1.4 用户注册

```http
POST /api/auth/register
Content-Type: application/json

{ "username": "myuser", "password": "mypassword", "inviteCode": "A1B2C3D4" }
```

无需认证。`inviteCode` 在邀请码系统开启时必填。
限制：用户名 ≥4 字符，密码 ≥4 字符。

**响应：**
```json
{ "code": 200, "data": { "message": "注册成功" } }
```

### 1.5 检查登录状态

```http
GET /api/auth/check
```

无需认证。

**响应（已登录）：**
```json
{ "code": 200, "data": { "authenticated": true, "username": "admin", "role": "admin", "userId": 1 } }
```

**响应（未登录）：**
```json
{ "code": 200, "data": { "authenticated": false } }
```

### 1.6 登出

```http
POST /api/auth/logout
```

无需认证。

**响应：**
```json
{ "code": 200, "data": { "message": "已登出" } }
```

### 1.7 修改密码

```http
POST /api/auth/change-password
Content-Type: application/json

{ "oldPassword": "old1234", "newPassword": "new5678" }
```

**需要认证**。新密码 ≥4 字符。

### 1.8 修改用户名

```http
POST /api/auth/change-username
Content-Type: application/json

{ "username": "newname" }
```

**需要认证**。新用户名 ≥4 字符。

---

## 2. 书籍管理 `/api/books/`

所有端点 **需要认证**。

### 2.1 获取书架

```http
GET /api/books
```

**响应：**
```json
{ "code": 200, "data": [
  { "id": 1, "title": "三体", "author": "刘慈欣", "format": "epub",
    "file_size": 524288, "file_size_formatted": "512.0 KB",
    "source": "local", "last_read_percent": 35.5,
    "total_chapters": 36, "created_at": 1714000000 }
]}
```

### 2.2 上传书籍

```http
POST /api/books/upload
Content-Type: multipart/form-data

file: <binary>
```

支持格式：txt, epub, pdf, mobi, azw3, fb2, html, md, docx, rtf, djvu 等。

**响应：**
```json
{ "code": 200, "data": { "id": 1, "title": "三体", "format": "epub", "file_size": 524288, "message": "上传成功" } }
```

### 2.3 获取书籍详情

```http
GET /api/books/{id}
```

### 2.4 更新书籍信息

```http
PUT /api/books/{id}
Content-Type: application/json

{ "title": "新书名", "author": "新作者" }
```

### 2.5 删除书籍

```http
DELETE /api/books/{id}
```

### 2.6 获取目录

```http
GET /api/books/{id}/toc
```

**响应：**
```json
{ "code": 200, "data": [
  { "title": "第一章", "index": 0, "position": 0 },
  { "title": "第二章", "index": 1, "position": 0.05 }
]}
```

### 2.7 获取章节内容

```http
GET /api/books/{id}/content?chapter=0
```

| 参数 | 必填 | 说明 |
|------|------|------|
| chapter | 否 | 章节索引（从 0 开始），默认 0 |

**响应：**
```json
{ "code": 200, "data": {
  "chapterIndex": 0, "chapterTitle": "第一章",
  "totalChapters": 36, "content": "<p>...</p>",
  "prevChapter": null, "nextChapter": 1
}}
```

### 2.8 下载原始文件

```http
GET /api/books/{id}/download
```

返回二进制文件流。

---

## 3. 阅读功能 `/api/reading/`

所有端点 **需要认证**。

### 3.1 获取阅读设置

```http
GET /api/reading/{bookId}/settings
```

### 3.2 更新阅读设置

```http
PUT /api/reading/{bookId}/settings
Content-Type: application/json

{ "font_size": 18, "background_color": "#F5F0E8",
  "text_color": "#333", "line_spacing": 1.8,
  "paragraph_spacing": 1.2, "font_family": "serif",
  "page_width": "800px" }
```

### 3.3 保存阅读进度

```http
PUT /api/reading/{bookId}/position
Content-Type: application/json

{ "position": 0.35, "chapter": "第三章" }
```

### 3.4 获取书签列表

```http
GET /api/reading/{bookId}/bookmarks
```

### 3.5 添加书签

```http
POST /api/reading/{bookId}/bookmarks
Content-Type: application/json

{ "chapter": "第三章", "position": 0.45, "note": "" }
```

### 3.6 删除书签

```http
DELETE /api/reading/{bookId}/bookmarks/{bookmarkId}
```

### 3.7 获取高亮/收藏

```http
GET /api/reading/{bookId}/highlights
```

### 3.8 添加高亮

```http
POST /api/reading/{bookId}/highlights
Content-Type: application/json

{ "text": "给岁月以文明", "chapter": "第三章",
  "position": 0.3, "color": "#FFFF00", "note": "" }
```

### 3.9 删除高亮

```http
DELETE /api/reading/{bookId}/highlights/{highlightId}
```

---

## 4. SoNovel 下载集成 `/api/download/`

所有端点 **需要认证**。

### 4.1 获取服务器配置

```http
GET /api/download/config
```

**响应：**
```json
{ "code": 200, "data": { "serverUrl": "http://...", "apiToken": "sonovel_..." } }
```

### 4.2 更新服务器配置

```http
PUT /api/download/config
Content-Type: application/json

{ "serverUrl": "http://your-server:7765", "apiToken": "sonovel_xxxxx" }
```

### 4.3 搜索书籍

```http
GET /api/download/search?kw=三体
```

| 参数 | 必填 | 说明 |
|------|------|------|
| kw | 是 | 搜索关键词（书名或作者） |

**响应：**
```json
{ "code": 200, "data": [
  { "sourceId": 1, "sourceName": "起点中文网", "url": "https://...",
    "bookName": "三体", "author": "刘慈欣",
    "latestChapter": "第一百章", "intro": "..." }
]}
```

### 4.4 开始下载

```http
POST /api/download/fetch
Content-Type: application/json

{ "url": "https://...", "format": "epub",
  "bookName": "三体", "author": "刘慈欣",
  "sourceName": "起点中文网" }
```

**响应：**
```json
{ "code": 200, "data": { "taskId": 1, "message": "下载任务已创建" } }
```

### 4.5 下载任务列表

```http
GET /api/download/tasks
```

**响应：**
```json
{ "code": 200, "data": [
  { "id": 1, "book_name": "三体", "format": "epub",
    "status": "downloading", "progress": 45, "total_chapters": 100 }
]}
```

### 4.6 删除任务

```http
DELETE /api/download/tasks/{taskId}
```

### 4.7 SSE 下载进度

```http
GET /api/download/progress
```

返回 Server-Sent Events 流：

```
data: {"type":"connected","message":"SSE连接已建立"}
data: {"type":"download-complete","taskId":1,"bookName":"三体","message":"下载完成"}
data: {"type":"download-error","taskId":1,"error":"..."}
```

---

## 5. 管理员 API `/api/admin/`

所有端点 **需要管理员权限**。

### 5.1 用户列表

```http
GET /api/admin/users
```

### 5.2 封禁用户

```http
POST /api/admin/users/ban
Content-Type: application/json

{ "userId": 2, "action": "ban" }
```

`action`: `ban`（封禁，IP封锁5天）或 `unban`（解封）。

### 5.3 永久删除用户

```http
POST /api/admin/users/delete
Content-Type: application/json

{ "userId": 2, "reason": "违规行为" }
```

### 5.4 公告管理

```http
GET    /api/admin/announcements           # 列表
POST   /api/admin/announcements           # 创建
PUT    /api/admin/announcements/{id}      # 更新
DELETE /api/admin/announcements/{id}      # 删除
PUT    /api/admin/announcements/reorder   # 排序
```

**创建/更新请求体：**
```json
{ "content": "## 公告标题\n内容...", "visibility": "all",
  "showDismiss": true, "pinned": false, "active": true }
```

### 5.5 邀请码管理

```http
GET    /api/admin/invite-codes                     # 列表
POST   /api/admin/invite-codes/generate             # 批量生成
PUT    /api/admin/invite-codes/{id}                 # 更新单个
DELETE /api/admin/invite-codes/{id}                 # 删除单个
POST   /api/admin/invite-codes/batch-delete         # 批量删除
PUT    /api/admin/invite-codes/config               # 系统设置
```

**批量生成请求体：**
```json
{ "count": 10, "maxUses": 1, "expiresInDays": 30, "note": "测试用" }
```

**系统设置请求体：**
```json
{ "enabled": true, "prompt": "需要邀请码才能注册" }
```

### 5.6 维护模式

```http
GET /api/admin/maintenance
PUT /api/admin/maintenance
```

**请求体：**
```json
{ "mode": true, "content": "## 维护公告\n网站维护中..." }
```

### 5.7 版本更新

```http
GET  /api/admin/update/check      # 检查更新（对比GitHub Release）
POST /api/admin/update/apply      # 执行更新（自动下载+替换+重启）
```

### 5.8 封禁日志

```http
GET /api/admin/banned-log
```

---

## 6. 公开 API `/api/public/`

无需认证。

### 6.1 公开公告

```http
GET /api/public/announcements
```

返回所有 `active=1` 的公告。

### 6.2 封号记录

```http
GET /api/public/banned-log?limit=5
```

| 参数 | 默认 | 说明 |
|------|------|------|
| limit | 5 | 返回条数 |

### 6.3 维护状态

```http
GET /api/public/maintenance
```

**响应：**
```json
{ "code": 200, "data": { "maintenance": false, "content": "" } }
```

### 6.4 更新状态

```http
GET /api/public/update-status
```

**响应：**
```json
{ "code": 200, "data": { "updating": true, "progress": 50, "message": "正在解压..." } }
```

### 6.5 邀请码状态

```http
GET /api/public/invite-status
```

**响应：**
```json
{ "code": 200, "data": { "enabled": false, "prompt": "" } }
```

---

## 7. 调用示例

### cURL

```bash
# 检查管理员
curl http://localhost:7766/api/auth/check-admin

# 管理员注册
curl -X POST http://localhost:7766/api/auth/admin-register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 登录
curl -X POST http://localhost:7766/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123","remember":true}'

# 获取书架（需带Cookie）
curl http://localhost:7766/api/books \
  -H "Cookie: miniread_session=abc..."

# 搜索书籍（SoNovel）
curl "http://localhost:7766/api/download/search?kw=三体" \
  -H "Cookie: miniread_session=abc..."
```

### Python

```python
import requests

BASE = "http://localhost:7766"
s = requests.Session()

# 管理员注册
s.post(f"{BASE}/api/auth/admin-register",
       json={"username": "admin", "password": "admin123"})

# 获取书架
r = s.get(f"{BASE}/api/books")
print(r.json())

# 上传书籍
with open("book.epub", "rb") as f:
    r = s.post(f"{BASE}/api/books/upload", files={"file": f})
print(r.json())

# 获取章节
r = s.get(f"{BASE}/api/books/1/content?chapter=0")
print(r.json()["data"]["content"])
```

### JavaScript (fetch)

```javascript
// 登录
fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'same-origin',
  body: JSON.stringify({ username: 'admin', password: 'admin123' })
}).then(r => r.json()).then(d => console.log(d));

// 获取书架
fetch('/api/books', { credentials: 'same-origin' })
  .then(r => r.json())
  .then(d => console.log(d.data));
```
