#!/usr/bin/env python3
"""Build static bilingual pages for GitHub Pages; Python standard library only."""

import argparse
from collections import defaultdict
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/ikaijua/Awesome-AITools"
HOMES = {"zh": "", "en": "en/"}
LANG_CODES = {"zh": "zh-CN", "en": "en"}

# Stable shared slugs let corresponding category pages link to each other.
CATEGORIES = [
    ("ai-assistants", "AI 助手与专有模型", "AI Assistants & Proprietary Models"),
    ("decision-models", "决策模型", "Decision Models"),
    ("open-source-llms", "开源大语言模型", "Open Source LLMs"),
    ("llm-leaderboards", "大语言模型排行榜", "LLM Leaderboard"),
    ("ai-agents", "AI Agent", "AI Agent"),
    ("agent-skills", "Agent Skills", "Agent Skills"),
    ("ai-news", "AI 新闻与资讯", "AI News & Information"),
    ("ai-coding", "AI Coding", "AI Coding"),
    ("ai-security", "AI 安全与逆向工程", "AI Security & Reverse Engineering"),
    ("llm-applications", "通用 LLM 应用", "General LLM Applications"),
    ("office-cli-mcp", "办公协作 CLI / MCP", "Office Collaboration CLI / MCP"),
    ("ai-finance", "AI 金融与量化投资", "AI Finance & Quant Investment"),
    ("image-ui-design", "AI 图像创作与 UI 设计", "AI Image Creation and UI Design"),
    ("ai-video", "AI 视频创作", "Video Creation"),
    ("ai-infrastructure", "AI基础设施平台", "AI Infrastructure Platform"),
    ("gpu-programming", "GPU 编程", "GPU Programming"),
    ("llm-prompts", "LLM Prompts", "LLM Prompts"),
    ("llm-training", "大语言模型训练与评估平台", "LLM training platform"),
    ("llm-inference", "LLM 推理与部署", "LLM Inference & Deployment"),
    ("reading", "阅读", None),
    ("writing", "写作", "Writing"),
    ("translation", "翻译工具", "Translation"),
    ("speech-recognition", "语音识别与字幕", "Speech Recognition & Subtitles"),
    ("text-to-speech", "语音合成（TTS）", "Text to Speech (TTS)"),
    ("voice-cloning", "声音克隆与变声", "Voice Cloning & Conversion"),
    ("speech-processing", "语音处理与翻译", "Speech Processing & Translation"),
    ("music-sound-effects", "AI 生成音乐与音效", "AI Music & Sound Effects"),
    ("academic-research", "学术科研", "Academic research"),
    ("ocr", "OCR 图像识别", "OCR"),
    ("video-summary", "视频内容总结", "Video Content Summary"),
    ("ai-detection", "AI 检测器", "AI Detection"),
    ("humanoid-robots", "人形机器人", "Humanoid Robots"),
    ("embodied-ai", "具身智能与仿真", "Embodied AI & Simulation"),
]

INTROS = {
    "ai-assistants": ("比较日常问答、研究、写作和多模态助手。选择时关注可用地区、当前模型、免费额度，以及与现有工作应用的连接能力。", "Compare assistants for everyday questions, research, writing, and multimodal tasks. Check regional access, available models, free allowances, and integrations with your existing apps."),
    "ai-coding": ("查找代码补全、仓库理解、自动审查和开发任务执行工具。选择时关注编辑器支持、代码访问方式、模型选择，以及项目能否提供可靠的测试与构建检查。", "Explore code completion, repository understanding, review, and development agents. Compare editor support, code access, model choices, and the tests available in your project."),
    "ai-agents": ("查找能执行多步任务的 AI 智能体及其运行框架。试用前确认可连接的应用、部署方式、执行权限和任务费用，涉及重要操作时保留人工确认。", "Find AI agents and frameworks for multi-step work. Before adopting one, check its integrations, deployment options, execution permissions, and task costs."),
    "image-ui-design": ("探索图像生成、编辑和界面设计工具。根据素材来源、编辑能力、商业使用条件与费用选择；生成结果仍需核对文字、细节和使用许可。", "Explore image generation, editing, and UI design tools. Compare editing controls, source materials, commercial-use terms, and pricing; check generated text and visual details before publishing."),
    "decision-models": ("了解用于路由、选择和评分的决策模型。比较输出类型、概率含义、延迟与调用费用，并用自己的任务验证判断是否可靠。", "Explore decision models for routing, selection, and scoring. Compare output types, probability semantics, latency, and API costs, then validate decisions on your own tasks."),
    "open-source-llms": ("查找可下载权重或自行部署的语言模型。开放权重不代表许可相同；使用前确认商业条款、硬件要求、推理引擎和实际任务表现。", "Find language models with downloadable weights or self-hosting options. Check commercial terms, hardware requirements, inference support, and performance on your own workload."),
}


def relative(target, current):
    """Relative links work at localhost, a Pages subpath, or a custom domain."""
    result = posixpath.relpath(target or ".", current or ".")
    return "./" if result == "." else result + "/"


def replace_content(page, element_id, value):
    pattern = rf'(<([a-z][a-z0-9]*)\b[^>]*\bid="{re.escape(element_id)}"[^>]*>).*?(</\2>)'
    result, count = re.subn(pattern, lambda m: m[1] + value + m[3], page, flags=re.S)
    if count != 1:
        raise ValueError(f"Expected one element #{element_id}, got {count}")
    return result


def script_json(value):
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")


def category_routes(data):
    known = {lang: {row[i]: row[0] for row in CATEGORIES if row[i]} for i, lang in ((1, "zh"), (2, "en"))}
    routes = {}
    for lang in HOMES:
        routes[lang] = {}
        for name in dict.fromkeys(t["category"] for t in data[lang]):
            # New upstream categories remain navigable without guessing translations.
            slug = known[lang].get(name, "category-" + sha256(name.encode()).hexdigest()[:12])
            routes[lang][name] = f"{lang}/categories/{slug}/"
    return routes


def head(title, description, path, alternates, base, breadcrumb=None):
    canonical = base + path
    lines = [f'<link rel="canonical" href="{escape(canonical)}">']
    for lang, target in alternates.items():
        lines.append(f'<link rel="alternate" hreflang="{LANG_CODES[lang]}" href="{escape(base + target)}">')
    default = alternates.get("zh", next(iter(alternates.values())))
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{escape(base + default)}">')
    for key, value in {"og:type": "website", "og:site_name": "Awesome AI Tools", "og:title": title, "og:description": description, "og:url": canonical}.items():
        lines.append(f'<meta property="{key}" content="{escape(value)}">')
    lines.append('<meta name="twitter:card" content="summary">')
    schema = {"@context": "https://schema.org", "@type": "WebSite", "name": "Awesome AI Tools", "url": base}
    if breadcrumb:
        schema = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i, "name": name, "item": base + target} for i, (name, target) in enumerate(breadcrumb, 1)]}
    lines.append(f'<script type="application/ld+json">{script_json(schema)}</script>')
    return "\n".join(lines)


def category_navigation(data, routes, lang, current, active=""):
    counts = defaultdict(int)
    for tool in data[lang]:
        counts[tool["category"]] += 1
    all_label = "全部工具" if lang == "zh" else "All tools"
    result = [f'<a class="category-button" href="{relative(HOMES[lang], current)}#directory"><span>{all_label}</span><span>{len(data[lang])}</span></a>']
    for name, count in counts.items():
        selected = ' active' if name == active else ''
        aria = ' aria-current="page"' if selected else ''
        result.append(f'<a class="category-button{selected}"{aria} href="{relative(routes[lang][name], current)}"><span>{escape(name)}</span><span>{count}</span></a>')
    return "\n".join(result)


def card(tool, lang, index=None):
    zh = lang == "zh"
    title = escape(tool["name"])
    fee = escape(tool["fee"] or ("未标明" if zh else "Unspecified"))
    description = escape(tool["description"])
    category = escape(tool["category"])
    featured = (" · 精选" if zh else " · Featured") if tool["featured"] else ""
    icon = escape(next((c.upper() for c in tool["name"] if c.isalnum()), "✳"))
    top = f'<span class="tool-icon" aria-hidden="true">{icon}</span><h3>{title}</h3>'
    if index is not None:
        top += f'<button class="favorite" data-save="{index}" aria-label="{escape(("收藏 " if zh else "Save ") + tool["name"])}" aria-pressed="false">♡</button>'
        bottom = f'<button class="detail-button" data-detail="{index}">{"详情" if zh else "Details"}</button><a class="visit" href="{escape(tool["links"][0]["url"])}" target="_blank" rel="noopener">{"访问" if zh else "Visit"} ↗</a>'
        extra = ""
    else:
        bottom = "".join(f'<a href="{escape(link["url"])}" target="_blank" rel="noopener">{escape(link["label"])} ↗</a>' for link in tool["links"])
        if tool["more"]:
            bottom += f'<a href="{escape(tool["more"])}" target="_blank" rel="noopener">{"详细介绍" if zh else "Read more"} ↗</a>'
        extra = " static-card"
    return f'<article class="card{extra}"><div class="card-top">{top}</div><div class="card-category">{category}{featured}</div><p class="card-desc">{description}</p><div class="card-bottom"><span class="fee">{fee}</span>{bottom}</div></article>'


def homepage(data, labels, routes, lang, base, template):
    zh = lang == "zh"
    index = 0 if zh else 1
    current = HOMES[lang]
    title = "Awesome AI Tools｜AI 工具导航与开源项目精选" if zh else "Awesome AI Tools | Curated AI Tools & Open Source Projects"
    description = (f"探索 {len(data[lang])} 个社区收录的 AI 工具与开源项目，涵盖 AI 助手、编程、图像、视频和语音。按分类、用途与费用查找工具，查看官网和详细介绍。" if zh else f"Explore {len(data[lang])} community-curated AI tools and open-source projects for chat, coding, images, video, and audio. Browse categories, pricing, official sites, and guides.")
    page = template.replace('lang="zh-CN"', f'lang="{LANG_CODES[lang]}"', 1)
    page = re.sub(r'<title>.*?</title>', f'<title>{escape(title)}</title>', page)
    page = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{escape(description)}">', page)
    for key, pair in labels.items():
        page = replace_content(page, key, pair[index])
    for key, value in {"toolcount": str(len(data[lang])), "catcount": str(len(routes[lang])), "currentCategory": "全部工具" if zh else "All tools", "resultCount": f'{len(data[lang])} 件工具' if zh else f'{len(data[lang])} tools', "categoryList": category_navigation(data, routes, lang, current), "cards": "\n".join(card(t, lang, i) for i, t in enumerate(data[lang][:24]))}.items():
        page = replace_content(page, key, value)
    other = "en" if zh else "zh"
    page = replace_content(page, "language", "English" if zh else "中文")
    page = re.sub(r'(<a id="language" href=")[^"]*', lambda m: m[1] + relative(HOMES[other], current), page)
    if not zh:
        page = page.replace('data-i18n="explore">工具目录', 'data-i18n="explore">Directory').replace('data-i18n="news">AI 周刊 ↗', 'data-i18n="news">AI News ↗')
        page = page.replace('placeholder="搜索工具、功能或关键词…" aria-label="搜索工具"', 'placeholder="Search tools, features, or keywords…" aria-label="Search tools"')
        page = replace_content(page, "favoritesOnly", "♡ Saved tools")
        for key, value in {"all": "All pricing", "free": "Free", "mixed": "Free / Paid", "paid": "Paid", "unknown": "Unspecified"}.items():
            page = re.sub(rf'(<button data-filter="{key}"[^>]*>)[^<]*', lambda m: m[1] + value, page)
        page = page.replace('aria-label="关闭"', 'aria-label="Close"')
        page = page.replace('可直接浏览分类与工具链接；搜索和收藏需要 JavaScript。 Browse categories and tool links below; search and saved tools require JavaScript.', 'Browse categories and tool links below; search and saved tools require JavaScript.')
    else:
        page = page.replace('可直接浏览分类与工具链接；搜索和收藏需要 JavaScript。 Browse categories and tool links below; search and saved tools require JavaScript.', '可直接浏览分类与工具链接；搜索和收藏需要 JavaScript。')
    news_label = "AI news" if zh else "ai‑news‑en"
    from urllib.parse import quote
    page = re.sub(r'(href=")[^"]*("[^>]*data-i18n="news")', lambda m: m[1] + REPO + '/discussions?discussions_q=' + quote('is:open label:"' + news_label + '"') + m[2], page)
    if not zh:
        page = page.replace('CONTRIBUTING-CN.md', 'CONTRIBUTING.md')
    prefix = relative("", current)
    for asset in ("style.css", "app.js", "assets/"):
        page = page.replace(f'="{asset}', f'="{prefix}{asset}')
    payload = {"data": prefix + "data.json", "homes": {key: relative(value, current) for key, value in HOMES.items()}, "categories": {key: {name: relative(path, current) for name, path in group.items()} for key, group in routes.items()}}
    page = page.replace('<!-- SITE_PAYLOAD -->', f'<script id="site-labels" type="application/json">{script_json(labels)}</script><script id="site-routes" type="application/json">{script_json(payload)}</script>')
    page = page.replace('<!-- SEO_HEAD -->', head(title, description, current, HOMES, base))
    # The generated links make language navigation available with JavaScript disabled.
    return page


def category_page(data, routes, lang, name, path, base):
    zh = lang == "zh"
    tools = [tool for tool in data[lang] if tool["category"] == name]
    slug = path.rstrip('/').split('/')[-1]
    display = "AI 编程工具" if zh and name == "AI Coding" else name
    title = f"{display}：工具目录与费用说明 | Awesome AI Tools" if zh else f"{display}: Tools, Features & Pricing | Awesome AI Tools"
    description = f"浏览 {len(tools)} 个{display}相关工具，查看用途、费用、官网及介绍链接。由 Awesome-AITools 社区维护。" if zh else f"Browse {len(tools)} tools in {display}, with descriptions, pricing, official links, and guides from the Awesome-AITools community."
    intro = INTROS.get(slug, ("根据任务目标、部署方式和费用比较工具。以下说明来自社区维护的目录；开始使用前，请核对工具官网的可用范围、最新功能和条款。", "Compare tools by task, deployment options, and cost. Descriptions come from the community directory; check official sites for current availability, features, and terms."))[0 if zh else 1]
    alternates = {lang: path}
    for other, categories in routes.items():
        match = next((target for target in categories.values() if target.rstrip('/').split('/')[-1] == slug), None)
        if match:
            alternates[other] = match
    other = "en" if zh else "zh"
    language_link = f'<a href="{relative(alternates[other], path)}" hreflang="{LANG_CODES[other]}">{"English" if zh else "中文"}</a>' if other in alternates else ''
    home = relative(HOMES[lang], path)
    assets = relative("", path)
    return f'''<!doctype html>
<html lang="{LANG_CODES[lang]}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><meta name="description" content="{escape(description)}">
{head(title, description, path, alternates, base, [("工具目录" if zh else "Directory", HOMES[lang]), (display, path)])}
<link rel="stylesheet" href="{assets}style.css?v=static-directory-v1"></head><body class="category-page">
<header><a class="brand" href="{home}"><span class="mark">✳</span> Awesome AI Tools</a><nav><a href="{home}#directory">{"搜索工具" if zh else "Search tools"}</a>{language_link}<a href="{REPO}" target="_blank" rel="noopener">GitHub ↗</a></nav></header>
<main><section class="category-intro"><nav class="breadcrumbs" aria-label="{"当前位置" if zh else "Breadcrumb"}"><a href="{home}">{"工具目录" if zh else "Directory"}</a><span aria-hidden="true"> / </span><span aria-current="page">{escape(display)}</span></nav>
<h1>{escape(display)}</h1><p>{escape(intro)}</p><p class="category-meta">{len(tools)} {"个工具 · 内容快照：" if zh else "tools · Directory snapshot: "}{data['meta']['updatedAt']}</p></section>
<section class="directory static-directory"><aside><h2 class="aside-title">{"浏览分类" if zh else "Browse categories"}</h2><nav aria-label="{"工具分类" if zh else "Tool categories"}">{category_navigation(data, routes, lang, path, name)}</nav></aside><div class="results"><div class="cards">{''.join(card(tool, lang) for tool in tools)}</div>
<p class="data-note">{"功能、费用与使用条款请以工具官网为准。" if zh else "Check official sites for current features, pricing, and terms."}</p><a class="subtle" href="{home}#directory">{"返回完整目录与搜索 →" if zh else "Search the full directory →"}</a></div></section></main>
<footer><a class="brand" href="{home}">Awesome AI Tools</a><p>{"目录来源：" if zh else "Directory source: "}<a href="{REPO}">Awesome-AITools</a> · <a href="{REPO}/blob/main/LICENSE">CC BY 4.0</a></p><a href="#">{"回到顶部 ↑" if zh else "Back to top ↑"}</a></footer></body></html>'''


def build(output, base):
    parsed = urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("--base-url must be an absolute HTTP(S) URL without query or fragment")
    base = base.rstrip('/') + '/'
    source = ROOT / "site"
    output = output.resolve()
    # Only replace this builder's dedicated output folder, never a source directory.
    if output.name != "dist" or source.resolve() in [output, *output.parents]:
        raise ValueError("Output must be a dedicated folder named dist outside site/")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for entry in source.iterdir():
        if entry.name in {"index.html", "labels.json"}:
            continue
        if entry.is_dir():
            shutil.copytree(entry, output / entry.name)
        else:
            shutil.copy2(entry, output / entry.name)
    data = json.loads((source / "data.json").read_text(encoding="utf-8"))
    labels = json.loads((source / "labels.json").read_text(encoding="utf-8"))
    labels["dataNote"] = [f"内容来自项目 README · 收录快照：{data['meta']['updatedAt'].replace('-', '.')} · 功能与费用请以工具官网为准", f"Source: project README · Snapshot: {data['meta']['updatedAt']} · Check official sites for current features and pricing"]
    routes = category_routes(data)
    template = (source / "index.html").read_text(encoding="utf-8")
    pages = {}
    for lang, path in HOMES.items():
        pages[path] = homepage(data, labels, routes, lang, base, template)
    for lang, group in routes.items():
        for name, path in group.items():
            if path in pages:
                raise ValueError(f"Duplicate page path: {path}")
            pages[path] = category_page(data, routes, lang, name, path, base)
    for path, body in pages.items():
        destination = output / path / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body, encoding="utf-8")
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    sitemap = ET.Element(ns + "urlset")
    for path in pages:
        ET.SubElement(ET.SubElement(sitemap, ns + "url"), ns + "loc").text = base + path
    # Omit lastmod rather than invent a page-change date from a data snapshot timestamp.
    ET.ElementTree(sitemap).write(output / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    (output / ".nojekyll").touch()
    if parsed.path in {"", "/"}:
        (output / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    return {"base_url": base, "pages": len(pages), "categories": {lang: len(group) for lang, group in routes.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=json.loads((ROOT / "site.config.json").read_text())["url"])
    args = parser.parse_args()
    print(json.dumps(build(ROOT / "dist", args.base_url), ensure_ascii=False))


if __name__ == "__main__":
    main()
