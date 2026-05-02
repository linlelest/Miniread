# SoNovel Web 配置教程

本搜索服务依赖另一项开源搜书服务 **[SoNovel Web](https://github.com/linlelest/so-novel-web)**。

---

## 普通用户

1. 访问 **[SoNovel Web 公共服务（暂时没有，敬请期待）](baidu.com)** 并注册登录
2. 在网页右上角点击「🔑 获取 Token」创建 API Token
3. 复制 Token，回到极读「下书」页面 → 右上角「服务器设置」
4. 将服务器地址填入第一栏，将 Token 填入第二栏，保存

![配置截图](/sonovel教程1.png)

> ⚠️ 注意：公共服务有使用次数限制，为节省公共资源，**试用后请使用高级用户方法自行部署**。

---

## 高级用户（推荐）

访问 **[SoNovel Web 仓库](https://github.com/linlelest/so-novel-web)** 手动部署：

### 对于Linux用户，可使用：

```bash
# 一键部署 (Debian/Ubuntu)
curl -sSL https://raw.githubusercontent.com/linlelest/so-novel-web/main/deploy.sh | sudo bash
```

### 对于Windows用户：
请访问[releases页面](https://github.com/linlelest/so-novel-web/releases)下载压缩包，解压安装使用。


部署后访问 `http://你的服务器IP:7765`，领取 Token 后填入极读即可。**个人使用无需服务器**，本地电脑部署即可。

---

## 相关链接

- [SoNovel Web GitHub](https://github.com/linlelest/so-novel-web)
- [Miniread GitHub](https://github.com/linlelest/Miniread)
