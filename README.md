# Awesome-AITools Pages

[Awesome-AITools](https://github.com/ikaijua/Awesome-AITools) 项目的独立静态导航网站。

目标仓库：`ikaijua/Awesome-AITools-Site`

启用 GitHub Pages 后的默认地址：https://ikaijua.github.io/Awesome-AITools-Site/

## 功能

- 中文默认，支持切换英文
- 按分类浏览、关键词搜索和费用筛选
- 收藏工具（保存在当前浏览器）
- 完整说明弹窗、官网与 GitHub Discussions 链接
- 手机和电脑自适应布局

目录内容来自上游项目的中英文 README，收录快照为 2026-10-06。两个语言版本分别保存，当前为中文 260 条、英文 245 条；本版本不自动同步上游。

## 发布

1. 将本仓库文件上传至 `ikaijua/Awesome-AITools-Site` 的 `main` 分支。
2. 在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
3. 进入 **Actions → Deploy GitHub Pages → Run workflow** 运行发布，或向 `main` 推送新提交。
4. 工作流成功后，在 Settings → Pages 或工作流的 `github-pages` 环境中查看实际地址。

只有 `site/` 中的静态文件会发布，不包含 README、工作流或 Sites 的托管配置。

## 本地预览

```bash
python3 -m http.server 8000 --directory site
```

打开 http://localhost:8000 。此站点使用相对资源路径，可直接部署到 GitHub Pages 项目子路径，无需 Node 构建或第三方依赖。

## 内容与许可

工具目录来自 [ikaijua/Awesome-AITools](https://github.com/ikaijua/Awesome-AITools)，由 ikaijua 与贡献者维护，遵循 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本项目将列表改编为可搜索的网页并保留来源及许可链接。工具功能、费用与介绍属于上游收录内容，当前状态请以工具官网为准。
