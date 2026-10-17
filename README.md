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
- 中英文首页与完整静态分类页，无需 JavaScript 也可浏览
- 每页独立标题、摘要、canonical、语言对应链接与站点地图

目录内容来自上游项目的中英文 README，两个语言版本分别保存，保留各自的分类、排序、说明、费用和介绍链接。快照日期与来源提交记录在 `site/data.json` 的 `meta` 中，页面日期随数据更新；使用下方脚本按需同步上游。

## 同步上游条目

需要 Python 3.9+，无第三方依赖。在仓库根目录运行：

```bash
python3 scripts/sync_upstream.py
```

脚本先确定上游 `main` 的提交，再从该提交读取两份 README，更新 `site/data.json` 和页面的快照日期。不会把两个语言版本强行合并，也不会把缺失费用猜成免费；新增、修改、移除和分类调整均以上游为准。说明中的额外参考链接也会保留在详情中。

已有上游本地仓库时，可指定要同步的引用：

```bash
git -C ../Awesome-AITools fetch origin
python3 scripts/sync_upstream.py --source ../Awesome-AITools --ref origin/main
```

验证快照与指定源一致（不写文件）：

```bash
python3 scripts/sync_upstream.py --source ../Awesome-AITools --ref origin/main --check
python3 -m unittest discover -s scripts -p 'test_*.py'
node --check site/app.js
```

提交这次数据更新后，现有 Pages 工作流即可发布。脚本遇到无法解析的条目会报错，避免静默漏掉工具；同步命令本身不提交、不推送，也不设置定时任务。

## 发布

1. 将本仓库文件上传至 `ikaijua/Awesome-AITools-Site` 的 `main` 分支。
2. 在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
3. 进入 **Actions → Deploy GitHub Pages → Run workflow** 运行发布，或向 `main` 推送新提交。
4. 工作流成功后，在 Settings → Pages 或工作流的 `github-pages` 环境中查看实际地址。

工作流使用 Python 标准库将 `site/` 与目录数据生成到 `dist/`，再上传 `dist/` 至 GitHub Pages。生成后的文件全部是 HTML、CSS、JavaScript、JSON 和图片，无需服务器或 Node 构建依赖。README、脚本和源模板不会发布。

## 本地预览

```bash
python3 scripts/build_site.py
python3 -m http.server 8000 --directory dist
```

打开 http://localhost:8000 。首页、分类页与资源之间使用相对路径，可在本地根路径和 GitHub Pages 项目子路径访问。`site/index.html` 是构建模板，请预览生成后的 `dist/`。

## 搜索引擎与页面结构

- 中文首页：`/`；英文首页：`/en/`。
- 分类页：`/zh/categories/<slug>/`、`/en/categories/<slug>/`。分类页直接包含该语言全部工具说明与链接，不依赖点击或执行 JavaScript。
- 首页预先渲染首批工具与完整分类导航；JavaScript 为首页补充搜索、费用筛选、收藏与弹窗。
- 每页有独立标题、摘要、canonical 和可用语言的双向 hreflang；仅中文存在的分类不会指向不存在的英文页面。
- `sitemap.xml` 自动列出全部页面；生成日期不冒充内容更新日期，未设置不可靠的 `lastmod`。
- 分类页使用真实内容的面包屑结构化数据，首页标注 WebSite；不添加虚构评分或排名保证。

本地构建默认公开网址在 `site.config.json`。Actions 使用 `actions/configure-pages` 返回的实际 Pages 网址覆盖它，因此适配项目子路径和已配置的自定义域名。也可手动指定：

```bash
python3 scripts/build_site.py --base-url https://ikaijua.github.io/Awesome-AITools-Site/
python3 -m unittest discover -s scripts -p 'test_*.py'
```

### 提交 Google Search Console

部署成功后，在 [Google Search Console](https://search.google.com/search-console/) 中添加网址前缀资源 `https://ikaijua.github.io/Awesome-AITools-Site/` 并验证所有权。验证可使用 Google 提供的 HTML 文件（放入 `site/`，构建时会复制到发布目录），或将验证 meta 标签加入 `site/index.html` 的 `<head>`。

提交 `https://ikaijua.github.io/Awesome-AITools-Site/sitemap.xml`，再用“网址检查”查看首页和分类页的实际抓取结果。所有权验证和提交需在站长自己的 Google 账号完成，代码修改不代表已提交或已被收录。

`robots.txt` 仅在域名根路径有效。GitHub Pages 项目子路径中的 `robots.txt` 不会控制该网站，所以默认构建不生成它；缺少该文件不表示禁止抓取。若部署在独立域名根路径，构建器会生成允许抓取并指向站点地图的 `robots.txt`。

## 内容与许可

工具目录来自 [ikaijua/Awesome-AITools](https://github.com/ikaijua/Awesome-AITools)，由 ikaijua 与贡献者维护，遵循 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本项目将列表改编为可搜索的网页并保留来源及许可链接。工具功能、费用与介绍属于上游收录内容，当前状态请以工具官网为准。
