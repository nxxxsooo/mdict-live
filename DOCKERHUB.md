# MdictLive

> A modern web reader for MDict dictionaries with React 19 SPA, dark mode, and faithful dictionary rendering.
>
> 基于 React 19 的现代 MDict 词典 Web 阅读器，支持暗色模式和忠实词典渲染。

> **📦 Formerly `flask-mdict`.** Both `tardivo/mdict-live` and `tardivo/flask-mdict` receive identical updates.
>
> **📦 原名 `flask-mdict`。** `tardivo/mdict-live` 和 `tardivo/flask-mdict` 两个仓库同步更新。

[GitHub Repository](https://github.com/nxxxsooo/mdict-live) | [Landing Page](https://mjshao.fun/mdict-live) | [Author](https://mjshao.fun)

## Features / 功能

- **React 19 SPA**: Fast, responsive, and modern interface. / 快速、响应式的现代界面。
- **Dark Mode / 暗色模式**: Built-in dark theme (`Ctrl+Shift+D`). / 内置暗色主题。
- **Sidebar / 侧边栏**: Manage dictionaries and navigate easily. / 管理词典，便捷导航。
- **Wordbook / 生词本**: Save words to your favorites. / 收藏生词，随时复习。
- **Word Frequency / 词频**: COCA/BNC ranking integration. / 集成 COCA/BNC 词频数据。
- **Faithful Rendering / 忠实渲染**: Sandboxed iframe preserves original dictionary CSS/JS. / 沙箱 iframe 保留词典原始排版。
- **LZO Support**: Native support for LZO-compressed `.mdx` files. / 原生支持 LZO 压缩词典。
- **Multi-Arch / 多架构**: `linux/amd64` and `linux/arm64`. / 支持 AMD64 和 ARM64 (Apple Silicon)。

## Quick Start / 快速开始

**Bash (Mac/Linux)**
```bash
docker run -d \
  --name mdict-live \
  -p 5248:5248 \
  -v $(pwd)/library:/app/content \
  tardivo/mdict-live:latest
```

**PowerShell (Windows)**
```powershell
docker run -d `
  --name mdict-live `
  -p 5248:5248 `
  -v ${PWD}/library:/app/content `
  tardivo/mdict-live:latest
```

## Docker Compose

```yaml
version: '3.8'
services:
  mdict-live:
    image: tardivo/mdict-live:latest
    container_name: mdict-live
    restart: unless-stopped
    ports:
      - "5248:5248"
    volumes:
      - ./library:/app/content
      - ./config:/config
```

## Volumes / 卷挂载

| Path / 路径 | Description / 说明 |
|---|---|
| `/app/content` | **Required / 必需**. Place `.mdx` and `.mdd` files here. / 放置词典文件。 |
| `/config` | Optional / 可选. Persistent config and database. / 持久化配置和数据库。 |

## Unraid

Use the XML template `mdict-live.xml` from the [GitHub repository](https://github.com/nxxxsooo/mdict-live/blob/main/mdict-live.xml). Place it in `/boot/config/plugins/dockerman/templates-user/` and import via Docker tab.

使用 [GitHub 仓库](https://github.com/nxxxsooo/mdict-live/blob/main/mdict-live.xml) 中的 XML 模板，放入 `/boot/config/plugins/dockerman/templates-user/` 后在 Docker 标签页导入。
