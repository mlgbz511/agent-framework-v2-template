#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent-framework-v2 可视化工程白皮书生成器（零第三方依赖）
直接读取仓库源码（AGENTS.md / rules / skills / check_governance.py / scripts / git HEAD）
动态构建单文件离线 HTML（现代编辑室双主题 + 右侧动态三级目录 + 渲染版 AGENTS.md）。

用法:
  python scripts/build_whitepaper.py \
    --repo "<path>/..." \
    --out "docs/agent-framework-v2-whitepaper.html"
"""

import argparse
import ast
import datetime
import html
import os
import re
import subprocess
import sys


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def render_inline_md(s: str) -> str:
    """Escape HTML and render inline **bold** and `code`."""
    parts = re.split(r"(`[^`]+`)", s)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) >= 2:
            out.append(f"<code>{html.escape(p[1:-1])}</code>")
        else:
            esc = html.escape(p)
            esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
            out.append(esc)
    return "".join(out)


def render_markdown_to_html(md_text: str) -> str:
    """Lightweight zero-dep Markdown -> HTML renderer for AGENTS.md."""
    lines = md_text.splitlines()
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Headings
        hm = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if hm:
            lvl = len(hm.group(1))
            tag = f"h{min(lvl + 2, 6)}"  # map # -> h3, ## -> h4, ### -> h5 inside viewer
            out.append(f'<div class="md-h md-h{lvl}">{render_inline_md(hm.group(2))}</div>')
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            q_lines = []
            while i < n and lines[i].strip().startswith(">"):
                q_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            out.append(f'<blockquote class="md-quote">{render_inline_md(" ".join(q_lines))}</blockquote>')
            continue

        # Table (| ... |)
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            headers = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip header + separator
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            ths = "".join(f"<th>{render_inline_md(h)}</th>" for h in headers)
            trs = "".join(
                "<tr>" + "".join(f"<td>{render_inline_md(c)}</td>" for c in r) + "</tr>"
                for r in rows
            )
            out.append(
                f'<div class="table-scroll md-table"><table><thead><tr>{ths}</tr></thead>'
                f'<tbody>{trs}</tbody></table></div>'
            )
            continue

        # Unordered list
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                item_txt = re.sub(r"^\s*[-*]\s+", "", lines[i]).strip()
                items.append(f"<li>{render_inline_md(item_txt)}</li>")
                i += 1
            out.append('<ul class="md-list">' + "".join(items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                item_txt = re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip()
                items.append(f"<li>{render_inline_md(item_txt)}</li>")
                i += 1
            out.append('<ol class="md-list">' + "".join(items) + "</ol>")
            continue

        # Paragraph
        p_lines = []
        while i < n and lines[i].strip() and not re.match(r"^(#{1,4}\s|>|\||[-*]\s|\d+\.\s)", lines[i].strip()):
            p_lines.append(lines[i].strip())
            i += 1
        out.append(f'<p class="md-p">{render_inline_md(" ".join(p_lines))}</p>')

    return "\n".join(out)


def collect_repo_data(repo_dir: str) -> dict:
    rules_dir = os.path.join(repo_dir, ".agents", "rules")
    skills_dir = os.path.join(repo_dir, ".agents", "skills")
    checker_path = os.path.join(repo_dir, ".agents", "scripts", "check_governance.py")
    agents_md_path = os.path.join(repo_dir, "AGENTS.md")

    agents_md_text = ""
    agents_md_bytes = 0
    if os.path.isfile(agents_md_path):
        with open(agents_md_path, encoding="utf-8", errors="replace") as f:
            agents_md_text = f.read()
        agents_md_bytes = os.path.getsize(agents_md_path)

    rules = []
    if os.path.isdir(rules_dir):
        for fn in sorted(os.listdir(rules_dir)):
            if not fn.endswith(".md"):
                continue
            with open(os.path.join(rules_dir, fn), encoding="utf-8", errors="replace") as f:
                meta = parse_frontmatter(f.read())
            rules.append({
                "file": fn,
                "scope": meta.get("scope", "—"),
                "enforcement": meta.get("enforcement", "none"),
                "trigger": meta.get("trigger", "—"),
            })

    skills = []
    if os.path.isdir(skills_dir):
        for d in sorted(os.listdir(skills_dir)):
            full = os.path.join(skills_dir, d)
            if os.path.isdir(full) and os.path.exists(os.path.join(full, "SKILL.md")):
                skills.append(d)

    checks = []
    if os.path.isfile(checker_path):
        with open(checker_path, encoding="utf-8", errors="replace") as f:
            chk_src = f.read()
        checks = sorted(set(re.findall(r'add\("[^"]+",\s*"([A-Z_]+)"', chk_src)))

    scripts = []
    for sub in (".agents/scripts", "scripts"):
        d = os.path.join(repo_dir, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".py"):
                continue
            full = os.path.join(d, fn)
            with open(full, encoding="utf-8", errors="replace") as f:
                src = f.read()
            try:
                doc = ast.get_docstring(ast.parse(src)) or ""
            except Exception:
                doc = ""
            first = doc.strip().splitlines()[0] if doc.strip() else "—"
            scripts.append({"path": f"{sub}/{fn}", "summary": first})

    commit_sha = "local"
    try:
        out = subprocess.check_output(
            ["git", "-C", repo_dir, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            commit_sha = out
    except Exception:
        pass

    return {
        "agents_md_text": agents_md_text,
        "agents_md_bytes": agents_md_bytes,
        "rules": rules,
        "skills": skills,
        "checks": checks,
        "scripts": scripts,
        "commit_sha": commit_sha,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def categorize_skills(skills: list) -> dict:
    gov_keys = {"governance-init", "init", "init-agent", "init-gitvault", "task-modes"}
    ui_keys = {
        "claude-design",
        "accessibility-audit", "ai-slop-check", "component-extract",
        "design-system-extract", "frontend-aesthetic-direction",
        "generate-variations", "hierarchy-rhythm-review",
        "interaction-states-pass", "make-a-deck", "make-a-prototype",
        "make-tweakable", "polish-pass", "visual-architect", "wireframe",
    }
    groups = {"治理与初始化": [], "UI 与设计系统": [], "工程、知识与技能维护": []}
    for s in skills:
        if s in gov_keys:
            groups["治理与初始化"].append(s)
        elif s in ui_keys:
            groups["UI 与设计系统"].append(s)
        else:
            groups["工程、知识与技能维护"].append(s)
    return groups


def render_html(data: dict) -> str:
    rules_rows = []
    for r in data["rules"]:
        enf = r["enforcement"]
        is_hook = enf == "hook"
        badge_cls = "tag-gate" if is_hook else "tag-soft"
        badge_lbl = "hook · 强制门禁" if is_hook else f"{html.escape(enf)} · 指令自律"
        rules_rows.append(
            f'<tr>'
            f'<td><code>{html.escape(r["file"])}</code></td>'
            f'<td>{html.escape(r["scope"])}</td>'
            f'<td>{html.escape(r["trigger"])}</td>'
            f'<td><span class="tag {badge_cls}">{badge_lbl}</span></td>'
            f'</tr>'
        )
    rules_tbody = "\n                  ".join(rules_rows)

    scripts_rows = []
    for sc in data["scripts"]:
        domain = "治理门禁 / 审计" if sc["path"].startswith(".agents/") else "冷启动 / 构建分发"
        scripts_rows.append(
            f'<tr>'
            f'<td><code>{html.escape(sc["path"])}</code></td>'
            f'<td>{domain}</td>'
            f'<td>{html.escape(sc["summary"])}</td>'
            f'</tr>'
        )
    scripts_tbody = "\n                  ".join(scripts_rows)

    checks_html = "\n          ".join(
        f'<span class="check-item"><i class="dot"></i>{html.escape(c)}</span>'
        for c in data["checks"]
    )

    skill_groups = categorize_skills(data["skills"])
    skills_cols = []
    for gname, items in skill_groups.items():
        if not items:
            continue
        tags = "\n                ".join(f'<span class="skill-pill">{html.escape(s)}</span>' for s in items)
        skills_cols.append(
            f'<div class="skill-col">\n'
            f'              <h4>{html.escape(gname)} <span class="count">{len(items)}</span></h4>\n'
            f'              <div class="skill-list">\n                {tags}\n              </div>\n'
            f'            </div>'
        )
    skills_grid = "\n            ".join(skills_cols)

    hook_count = sum(1 for r in data["rules"] if r["enforcement"] == "hook")
    rules_count = len(data["rules"])
    skills_count = len(data["skills"])
    checks_count = len(data["checks"])
    scripts_count = len(data["scripts"])
    sha = html.escape(data["commit_sha"])
    gen_at = html.escape(data["generated_at"])

    agents_bytes = data["agents_md_bytes"]
    agents_lines = len(data["agents_md_text"].splitlines())
    budget_pct = min(100.0, (agents_bytes / 65536.0) * 100.0) if agents_bytes else 0.0
    agents_escaped = html.escape(data["agents_md_text"])
    agents_rendered = render_markdown_to_html(data["agents_md_text"])

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>agent-framework-v2 — 治理架构工程白皮书</title>
  <style>
    :root,
    [data-theme="light"] {{
      --bg-page: #FAF9F6;
      --bg-surface: #F3F1EC;
      --bg-elevated: #FFFFFF;
      --bg-code: #F1EFEA;
      --border-hairline: #E2DFD7;
      --border-strong: #C9C4B8;
      --ink-primary: #141413;
      --ink-secondary: #52504B;
      --ink-muted: #78756E;
      --accent-primary: #B85032;
      --accent-secondary: #1D4ED8;
      --sem-gate: #1F6F4A;
      --sem-soft: #9A5B13;
      --sem-break: #B93829;
      --gate-bg: rgba(31, 111, 74, 0.08);
      --soft-bg: rgba(154, 91, 19, 0.08);
      --break-bg: rgba(185, 56, 41, 0.08);
      --svg-bg: #F6F4EF;
      --svg-node: #FFFFFF;
      --svg-stroke: #D5D0C5;
    }}

    [data-theme="dark"] {{
      --bg-page: #121316;
      --bg-surface: #191B20;
      --bg-elevated: #1E2026;
      --bg-code: #16181D;
      --border-hairline: #2A2D35;
      --border-strong: #3E434F;
      --ink-primary: #ECEAE4;
      --ink-secondary: #B8B5AD;
      --ink-muted: #9A968E;
      --accent-primary: #D98A73;
      --accent-secondary: #7AA2F7;
      --sem-gate: #73B895;
      --sem-soft: #E0AF68;
      --sem-break: #E07A70;
      --gate-bg: rgba(74, 222, 128, 0.10);
      --soft-bg: rgba(251, 191, 36, 0.10);
      --break-bg: rgba(248, 113, 113, 0.10);
      --svg-bg: #15171C;
      --svg-node: #1D2027;
      --svg-stroke: #323642;
    }}

    :root {{
      --font-serif: "Newsreader", "Source Serif 4", "Noto Serif SC", "Songti SC", Georgia, serif;
      --font-sans: system-ui, -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      --font-mono: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
    }}

    /* Hide all scrollbars cleanly while preserving wheel/trackpad scrolling */
    * {{
      box-sizing: border-box;
      scrollbar-width: none;
      -ms-overflow-style: none;
    }}
    *::-webkit-scrollbar {{
      display: none;
      width: 0;
      height: 0;
    }}

    html {{
      scroll-behavior: smooth;
      background: var(--bg-page);
      color: var(--ink-primary);
      font-family: var(--font-sans);
      font-size: 16px;
      line-height: 1.72;
      -webkit-font-smoothing: antialiased;
      transition: background-color 180ms ease, color 180ms ease;
    }}

    body {{ margin: 0; padding: 0; }}

    #progress-bar {{
      position: fixed;
      top: 0;
      left: 0;
      width: 0%;
      height: 2px;
      background: var(--accent-primary);
      z-index: 1000;
      transition: width 80ms linear;
    }}

    .masthead {{
      position: sticky;
      top: 0;
      z-index: 900;
      background: var(--bg-page);
      border-bottom: 1px solid var(--border-hairline);
      padding: 12px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}

    .masthead-left {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-secondary);
    }}

    .masthead-brand {{
      font-weight: 600;
      color: var(--ink-primary);
      letter-spacing: 0.02em;
    }}

    .masthead-rev {{
      padding: 2px 8px;
      background: var(--bg-surface);
      border: 1px solid var(--border-hairline);
      border-radius: 3px;
      color: var(--ink-muted);
    }}

    .masthead-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .btn-ghost {{
      appearance: none;
      background: transparent;
      border: 1px solid var(--border-hairline);
      color: var(--ink-secondary);
      border-radius: 4px;
      padding: 6px 12px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      cursor: pointer;
      transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
    }}

    .btn-ghost:hover {{
      background: var(--bg-surface);
      color: var(--ink-primary);
      border-color: var(--border-strong);
    }}

    .btn-ghost.active {{
      background: var(--bg-surface);
      color: var(--accent-primary);
      border-color: var(--accent-primary);
    }}

    .btn-ghost:active {{ transform: translateY(1px); }}
    .btn-ghost:focus-visible {{
      outline: 2px solid var(--accent-primary);
      outline-offset: 2px;
    }}

    .mobile-toc-btn {{ display: none; }}

    /* Right-TOC Editorial Shell */
    .shell {{
      max-width: 1300px;
      margin: 0 auto;
      padding: 48px 32px 96px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 300px;
      gap: 56px;
    }}

    .article {{ min-width: 0; }}
    .prose {{ max-width: 68ch; }}
    .wide {{ max-width: 920px; margin: 32px 0; }}

    /* Right Sticky Auto-Expanding 3-Level TOC */
    .toc {{
      position: sticky;
      top: 72px;
      align-self: start;
      max-height: calc(100vh - 96px);
      overflow-y: auto;
      padding-left: 16px;
    }}

    .toc-caption {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--ink-muted);
      margin-bottom: 14px;
    }}

    .toc-groups {{
      list-style: none;
      margin: 0;
      padding: 0;
      border-left: 1px solid var(--border-hairline);
    }}

    .toc-group {{
      margin-bottom: 2px;
    }}

    .toc-sublist {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: none;
    }}

    /* Expand sub-items ONLY when group is active (scrolled to) OR hovered */
    .toc-group.is-open .toc-sublist,
    .toc-group:hover .toc-sublist {{
      display: block;
    }}

    .toc-link {{
      display: flex;
      align-items: baseline;
      gap: 8px;
      padding: 6px 12px;
      margin-left: -1px;
      border-left: 2px solid transparent;
      text-decoration: none;
      color: var(--ink-secondary);
      transition: color 150ms ease, border-color 150ms ease;
    }}

    .toc-link.lvl-1 {{
      font-size: 15px;
      font-weight: 600;
      line-height: 1.45;
      color: var(--ink-primary);
    }}

    .toc-link.lvl-2 {{
      font-size: 15px;
      line-height: 1.4;
      padding: 4px 12px 4px 24px;
      color: var(--ink-secondary);
    }}

    .toc-link.lvl-3 {{
      font-size: 13.5px;
      line-height: 1.35;
      padding: 3px 12px 3px 38px;
      color: var(--ink-muted);
    }}

    .toc-link:hover {{ color: var(--ink-primary); }}
    .toc-link:focus-visible {{
      outline: 2px solid var(--accent-primary);
      outline-offset: 2px;
    }}

    .toc-link.active {{
      color: var(--accent-primary);
      border-left-color: var(--accent-primary);
      font-weight: 600;
    }}

    .toc-num {{
      font-family: var(--font-mono);
      font-size: 14.5px;
      color: var(--ink-muted);
      flex-shrink: 0;
    }}

    .toc-link.active .toc-num {{ color: var(--accent-primary); }}

    .toc-footnote {{
      margin-top: 24px;
      padding-top: 14px;
      border-top: 1px solid var(--border-hairline);
      font-family: var(--font-mono);
      font-size: 14.5px;
      color: var(--ink-muted);
      line-height: 1.65;
    }}

    /* Hero */
    .hero {{
      padding-bottom: 40px;
      border-bottom: 1px solid var(--border-hairline);
      margin-bottom: 56px;
    }}

    .hero-kicker {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent-primary);
      margin-bottom: 12px;
    }}

    .hero h1 {{
      font-family: var(--font-serif);
      font-size: clamp(32px, 4.2vw, 44px);
      font-weight: 600;
      line-height: 1.18;
      letter-spacing: -0.015em;
      margin: 0 0 20px;
      max-width: 24ch;
      color: var(--ink-primary);
    }}

    .hero-standfirst {{
      font-size: 18px;
      line-height: 1.65;
      color: var(--ink-secondary);
      max-width: 62ch;
      margin: 0 0 32px;
    }}

    .stat-strip {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border-top: 1px solid var(--border-hairline);
      border-bottom: 1px solid var(--border-hairline);
      max-width: 920px;
    }}

    .stat-cell {{ padding: 16px 20px 16px 0; }}
    .stat-cell + .stat-cell {{
      padding-left: 20px;
      border-left: 1px solid var(--border-hairline);
    }}

    .stat-num {{
      font-family: var(--font-serif);
      font-size: 28px;
      font-weight: 600;
      line-height: 1.15;
      color: var(--ink-primary);
      margin-bottom: 4px;
    }}

    .stat-label {{
      font-size: 14.5px;
      font-weight: 500;
      color: var(--ink-secondary);
    }}

    .stat-note {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-muted);
      margin-top: 2px;
    }}

    section {{
      margin-bottom: 72px;
      scroll-margin-top: 72px;
    }}

    .sec-num {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--accent-primary);
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }}

    h2 {{
      font-family: var(--font-serif);
      font-size: 28px;
      font-weight: 600;
      line-height: 1.28;
      margin: 0 0 20px;
      max-width: 30ch;
      color: var(--ink-primary);
      scroll-margin-top: 72px;
    }}

    h3 {{
      font-size: 19px;
      font-weight: 600;
      margin: 36px 0 12px;
      color: var(--ink-primary);
      max-width: 68ch;
      scroll-margin-top: 72px;
    }}

    h4 {{
      font-size: 15px;
      font-weight: 600;
      margin: 20px 0 8px;
      color: var(--ink-secondary);
      font-family: var(--font-mono);
      max-width: 68ch;
      scroll-margin-top: 72px;
    }}

    p {{ margin: 0 0 16px; }}

    code {{
      font-family: var(--font-mono);
      font-size: 0.86em;
      background: var(--bg-code);
      padding: 2px 6px;
      border-radius: 3px;
      color: var(--ink-primary);
      word-break: break-word;
    }}

    .note-block {{
      max-width: 68ch;
      margin: 24px 0;
      padding: 16px 20px;
      background: var(--bg-surface);
      border-left: 3px solid var(--accent-primary);
    }}

    .note-block.warn {{ border-left-color: var(--sem-soft); }}

    .note-title {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--accent-primary);
      margin-bottom: 6px;
    }}

    .note-block.warn .note-title {{ color: var(--sem-soft); }}
    .note-block p:last-child {{ margin-bottom: 0; }}

    .plate {{
      background: var(--svg-bg);
      border: 1px solid var(--border-hairline);
      border-radius: 4px;
    }}

    .plate-head {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 18px;
      border-bottom: 1px solid var(--border-hairline);
      background: var(--bg-surface);
    }}

    .plate-caption {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-secondary);
    }}

    .seg-group {{ display: flex; flex-wrap: wrap; gap: 4px; }}

    .seg-btn {{
      appearance: none;
      background: transparent;
      border: 1px solid transparent;
      color: var(--ink-secondary);
      padding: 4px 10px;
      border-radius: 3px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      cursor: pointer;
      transition: all 140ms ease;
    }}

    .seg-btn:hover {{
      color: var(--ink-primary);
      background: var(--bg-page);
    }}

    .seg-btn.active {{
      color: var(--accent-primary);
      background: var(--bg-elevated);
      border-color: var(--border-hairline);
      font-weight: 600;
    }}

    .plate-body {{
      padding: 20px;
      overflow-x: auto;
    }}

    .plate-body svg {{
      display: block;
      width: 100%;
      min-width: 720px;
      height: auto;
    }}

    .layer-node {{ transition: opacity 180ms ease; }}
    .layer-node.dimmed {{ opacity: 0.2; }}

    .tabs-panel {{
      max-width: 920px;
      margin: 28px 0;
      border: 1px solid var(--border-hairline);
      border-radius: 4px;
      background: var(--bg-page);
    }}

    .tabs-nav {{
      display: flex;
      flex-wrap: wrap;
      border-bottom: 1px solid var(--border-hairline);
      background: var(--bg-surface);
      padding: 0 12px;
      gap: 4px;
    }}

    .tab-btn {{
      appearance: none;
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      padding: 12px 14px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-secondary);
      cursor: pointer;
      transition: color 150ms ease, border-color 150ms ease;
    }}

    .tab-btn:hover {{ color: var(--ink-primary); }}
    .tab-btn.active {{
      color: var(--accent-primary);
      border-bottom-color: var(--accent-primary);
      font-weight: 600;
    }}

    .tab-pane {{ display: none; padding: 18px 20px; }}
    .tab-pane.active {{ display: block; }}

    .tag {{
      display: inline-block;
      font-family: var(--font-mono);
      font-size: 13.5px;
      padding: 2px 8px;
      border-radius: 3px;
      white-space: nowrap;
    }}

    .tag-gate {{ background: var(--gate-bg); color: var(--sem-gate); }}
    .tag-soft {{ background: var(--soft-bg); color: var(--sem-soft); }}
    .tag-break {{ background: var(--break-bg); color: var(--sem-break); }}

    .checks-wrap {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      max-width: 920px;
      margin: 20px 0 24px;
    }}

    .check-item {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      padding: 4px 10px;
      background: var(--bg-surface);
      border: 1px solid var(--border-hairline);
      border-radius: 3px;
      color: var(--ink-primary);
    }}

    .check-item .dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--sem-gate);
    }}

    .table-scroll {{
      overflow-x: auto;
      border-top: 1px solid var(--border-strong);
      border-bottom: 1px solid var(--border-strong);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 15px;
      text-align: left;
    }}

    th {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--ink-secondary);
      padding: 11px 12px;
      border-bottom: 1px solid var(--border-hairline);
      background: var(--bg-surface);
      white-space: nowrap;
    }}

    td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border-hairline);
      vertical-align: top;
    }}

    tr:last-child td {{ border-bottom: none; }}

    details.drawer {{
      max-width: 920px;
      margin: 16px 0;
      border-top: 1px solid var(--border-hairline);
      border-bottom: 1px solid var(--border-hairline);
    }}

    details.drawer summary {{
      padding: 14px 4px;
      cursor: pointer;
      font-weight: 600;
      font-size: 15px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      list-style: none;
      color: var(--ink-primary);
    }}

    details.drawer summary::-webkit-details-marker {{ display: none; }}
    details.drawer summary::after {{
      content: "+ 展开";
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--accent-primary);
      font-weight: 500;
    }}
    details.drawer[open] summary::after {{
      content: "- 收起";
      color: var(--ink-muted);
    }}

    .drawer-inner {{ padding: 4px 0 20px; }}

    .skill-cols {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 24px;
    }}

    .skill-col h4 {{
      margin: 0 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border-hairline);
      font-size: 15px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      color: var(--ink-primary);
      font-family: var(--font-sans);
    }}

    .skill-col .count {{
      font-family: var(--font-mono);
      color: var(--ink-muted);
      font-weight: 400;
    }}

    .skill-list {{ display: flex; flex-wrap: wrap; gap: 6px; }}

    .skill-pill {{
      font-family: var(--font-mono);
      font-size: 13.5px;
      padding: 2px 8px;
      background: var(--bg-surface);
      border: 1px solid var(--border-hairline);
      border-radius: 3px;
      color: var(--ink-secondary);
    }}

    .scenario-item {{
      max-width: 68ch;
      padding: 20px 0;
      border-bottom: 1px solid var(--border-hairline);
    }}
    .scenario-item:last-of-type {{ border-bottom: none; }}
    .scenario-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 8px 0 12px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-muted);
    }}

    /* AGENTS.md Budget & Rendered Markdown Viewer */
    .budget-bar {{
      max-width: 920px;
      margin: 16px 0 24px;
      padding: 14px 18px;
      background: var(--bg-surface);
      border: 1px solid var(--border-hairline);
      border-radius: 4px;
    }}
    .budget-top {{
      display: flex;
      justify-content: space-between;
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-secondary);
      margin-bottom: 8px;
    }}
    .budget-track {{
      height: 8px;
      background: var(--border-hairline);
      border-radius: 4px;
      overflow: hidden;
    }}
    .budget-fill {{
      height: 100%;
      background: var(--sem-gate);
    }}

    .source-viewer {{
      max-width: 920px;
      border: 1px solid var(--border-hairline);
      border-radius: 4px;
      background: var(--bg-elevated);
      overflow: hidden;
    }}
    .source-head {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 10px 18px;
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border-hairline);
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-secondary);
    }}
    .source-body {{
      max-height: 540px;
      overflow-y: auto;
      padding: 24px 28px;
    }}
    .source-body.expanded {{
      max-height: none;
    }}

    /* Rendered Markdown Styles inside AGENTS.md Viewer */
    .md-rendered .md-h1 {{
      font-family: var(--font-serif);
      font-size: 24px;
      font-weight: 600;
      margin: 0 0 14px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border-hairline);
      color: var(--ink-primary);
    }}
    .md-rendered .md-h2 {{
      font-family: var(--font-serif);
      font-size: 19px;
      font-weight: 600;
      margin: 26px 0 10px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--border-hairline);
      color: var(--accent-primary);
    }}
    .md-rendered .md-h3 {{
      font-size: 15px;
      font-weight: 600;
      margin: 18px 0 8px;
      color: var(--ink-primary);
    }}
    .md-rendered .md-quote {{
      margin: 12px 0 18px;
      padding: 10px 16px;
      background: var(--bg-surface);
      border-left: 3px solid var(--accent-secondary);
      font-size: 15px;
      color: var(--ink-secondary);
    }}
    .md-rendered .md-p {{
      font-size: 15.5px;
      margin: 0 0 12px;
      color: var(--ink-primary);
    }}
    .md-rendered .md-list {{
      margin: 0 0 14px;
      padding-left: 22px;
      font-size: 15.5px;
    }}
    .md-rendered .md-list li {{
      margin-bottom: 6px;
    }}
    .md-rendered .md-table {{
      margin: 14px 0 18px;
    }}
    .md-rendered .md-table table {{
      font-size: 14.5px;
    }}

    .raw-pre {{
      display: none;
      margin: 0;
      padding: 0;
      font-family: var(--font-mono);
      font-size: 15px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
      color: var(--ink-primary);
    }}

    .source-viewer.show-raw .md-rendered {{ display: none; }}
    .source-viewer.show-raw .raw-pre {{ display: block; }}

    footer {{
      max-width: 920px;
      margin-top: 72px;
      padding-top: 24px;
      border-top: 1px solid var(--border-hairline);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      font-family: var(--font-mono);
      font-size: 13.5px;
      color: var(--ink-muted);
    }}

    @media (max-width: 1024px) {{
      .masthead {{ padding: 12px 20px; }}
      .mobile-toc-btn {{ display: inline-block; }}
      .shell {{
        grid-template-columns: 1fr;
        padding: 32px 20px 64px;
        gap: 0;
      }}
      .toc {{
        display: none;
        position: fixed;
        top: 53px;
        left: 0;
        right: 0;
        bottom: 0;
        max-height: none;
        background: var(--bg-page);
        z-index: 850;
        padding: 24px 20px;
      }}
      .toc.open {{ display: block; }}
      .toc-group .toc-sublist {{ display: block; }}
      .stat-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .stat-cell:nth-child(3) {{ padding-left: 0; border-left: none; border-top: 1px solid var(--border-hairline); }}
      .stat-cell:nth-child(4) {{ border-top: 1px solid var(--border-hairline); }}
      .skill-cols {{ grid-template-columns: 1fr; }}
    }}

    @media (max-width: 520px) {{
      .stat-strip {{ grid-template-columns: 1fr; }}
      .stat-cell + .stat-cell {{ padding-left: 0; border-left: none; border-top: 1px solid var(--border-hairline); }}
    }}
  </style>
</head>
<body>
  <div id="progress-bar"></div>

  <header class="masthead">
    <div class="masthead-left">
      <span class="masthead-brand">agent-framework-v2</span>
      <span class="masthead-rev">rev {sha}</span>
    </div>
    <div class="masthead-actions">
      <button class="btn-ghost" id="theme-toggle" type="button" aria-label="切换明暗主题">深色模式</button>
      <button class="btn-ghost mobile-toc-btn" id="mobile-toc-toggle" type="button" aria-expanded="false">目录</button>
    </div>
  </header>

  <div class="shell">
    <main class="article">
      <header class="hero">
        <div class="hero-kicker">Architecture Whitepaper · Full Technical Deep-Dive</div>
        <h1>面向 Agent 工作区的分层治理架构</h1>
        <p class="hero-standfirst">
          大多数工作区规则只是“放在仓库里的 Markdown 文本”。本文基于 <code>mlgbz511/agent-framework-v2</code> 源码与自检脚本实时构建，完整展开 8 层运行时载体、13 条已知断点、{scripts_count} 个脚本调用拓扑、6 大实战使用场景与渲染版 <code>AGENTS.md</code> 全文。
        </p>

        <div class="stat-strip">
          <div class="stat-cell">
            <div class="stat-num">8 层 / 13 断点</div>
            <div class="stat-label">运行时治理栈</div>
            <div class="stat-note">asar 取证 + 拦截层审计</div>
          </div>
          <div class="stat-cell">
            <div class="stat-num">{checks_count} 类 / 4 类</div>
            <div class="stat-label">静态检查 / 审批收据</div>
            <div class="stat-note">checker + approval_gate</div>
          </div>
          <div class="stat-cell">
            <div class="stat-num">{rules_count} / {skills_count}</div>
            <div class="stat-label">专项规则 / 自动技能</div>
            <div class="stat-note">仅 {hook_count} 条规则具备 hook 强制</div>
          </div>
          <div class="stat-cell">
            <div class="stat-num">{scripts_count} 个脚本</div>
            <div class="stat-label">自动化治理工具链</div>
            <div class="stat-note">AGENTS.md 占 {agents_bytes:,} B</div>
          </div>
        </div>
      </header>

      <!-- 00 -->
      <section id="sec-0">
        <div class="sec-num">00 // CORE THESIS</div>
        <h2 id="h-sec-0" data-toc-level="1" data-toc-num="00" data-toc-label="为什么文档规则会失效">为什么“文档规则”在运行时经常失效</h2>
        <div class="prose">
          <p>
            团队习惯在仓库里堆砌大量 <code>rules/</code>、<code>modes/</code> 与配置文件，默认 Agent 会自动读取并遵守它们。<code>agent-framework-v2</code> 通过对 DSH 运行时（asar）的源码取证得出一个反直觉结论：<strong>工作区里看起来存在的文件，绝大多数在运行时根本不会被自动注入。</strong>
          </p>
          <h3 id="h-0-native-channels" data-toc-level="2" data-toc-label="两条原生注入通道">真正生效的两条原生通道</h3>
          <p>
            真正进入上下文的只有两条原生通道：一是由 <code>dsh-agent-instructions</code> 按目录层级注入的 <code>AGENTS.md</code> / <code>CLAUDE.md</code> 指令链；二是由 <code>skill-filesystem</code> 扫描 6 个文件系统根后渲染进 System Prompt 的 <code>SKILL.md</code>。至于 <code>.agents/rules/*</code> 与工作区 <code>.agents/mcp_config.json</code>，消费者不会自动读取它们。
          </p>
          <div class="note-block">
            <div class="note-title">设计第一原则：不以文档宣称代替机制强制</div>
            <p>
              框架将所有约束严格区分为<strong>确定性门禁（Deterministic Gate）</strong>与<strong>指令层自律（Instruction-level）</strong>。未接入 Hook、MCP 网关或静态检查脚本的条款，都在架构图与评测台账中诚实标注为“已知缺口”。
            </p>
          </div>
        </div>
      </section>

      <!-- 01 -->
      <section id="sec-1">
        <div class="sec-num">01 // RUNTIME STACK &amp; BREAKPOINTS</div>
        <h2 id="h-sec-1" data-toc-level="1" data-toc-num="01" data-toc-label="8 层运行时与 13 条断点">8 层运行时加载真相与 13 条已知断点</h2>
        <div class="prose">
          <p>
            从会话启动到工具落盘，请求依次穿过 8 个逻辑层级。在 L3 指令链中，系统先读用户全局，再沿项目根（最近 <code>.git</code> 祖先）逐级向下加载；单链预算 <strong>65,536 B</strong>，两链合计 <strong>131,072 B</strong>，单源文件上限 <strong>1,048,576 B</strong>，超限时整份丢弃更宽泛的上层文件。
          </p>
        </div>

        <h3 id="h-1-diagram" data-toc-level="2" data-toc-label="8 层架构流转图">8 层架构与拦截边界图解</h3>
        <div class="wide">
          <div class="plate">
            <div class="plate-head">
              <span class="plate-caption">FIG 1.0 · 8 层运行时栈与拦截边界</span>
              <div class="seg-group" role="group" aria-label="层级过滤">
                <button class="seg-btn active" data-filter="all" type="button">全部 8 层</button>
                <button class="seg-btn" data-filter="hard" type="button">确定性控制</button>
                <button class="seg-btn" data-filter="soft" type="button">上下文注入</button>
                <button class="seg-btn" data-filter="break" type="button">已知断点</button>
              </div>
            </div>
            <div class="plate-body">
              <svg viewBox="0 0 960 440" xmlns="http://www.w3.org/2000/svg" aria-label="8层治理架构流转图">
                <defs>
                  <marker id="arr-ink" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent-secondary)"/>
                  </marker>
                  <marker id="arr-gate" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--sem-gate)"/>
                  </marker>
                </defs>

                <text x="20" y="24" fill="var(--ink-muted)" font-size="14.5" font-weight="bold">CONTEXT &amp; DISCOVERY (L1 - L5)</text>
                <text x="504" y="24" fill="var(--ink-muted)" font-size="14.5" font-weight="bold">EXECUTION &amp; GATEWAY (L6 - L8)</text>
                <line x1="478" y1="12" x2="478" y2="424" stroke="var(--border-hairline)" stroke-dasharray="4 4"/>

                <g class="layer-node" data-kind="soft">
                  <rect x="20" y="40" width="434" height="60" rx="4" fill="var(--svg-node)" stroke="var(--svg-stroke)"/>
                  <text x="36" y="62" fill="var(--accent-secondary)" font-size="14.5" font-weight="bold">L1 · Runtime Baseline</text>
                  <text x="36" y="82" fill="var(--ink-primary)" font-size="14.5">dsh-base bundle → System Prompt</text>
                </g>

                <g class="layer-node" data-kind="soft break">
                  <rect x="20" y="114" width="434" height="68" rx="4" fill="var(--svg-node)" stroke="var(--svg-stroke)"/>
                  <text x="36" y="136" fill="var(--accent-secondary)" font-size="14.5" font-weight="bold">L2 · Skill Catalog (rank 100~600)</text>
                  <text x="36" y="156" fill="var(--ink-primary)" font-size="14.5">仅认 SKILL.md + frontmatter (发现深度 1)</text>
                  <text x="36" y="172" fill="var(--sem-break)" font-size="14">断点: rank 500 (~/.agents/skills) 本机缺位</text>
                </g>

                <g class="layer-node" data-kind="soft break">
                  <rect x="20" y="196" width="434" height="68" rx="4" fill="var(--svg-node)" stroke="var(--sem-soft)"/>
                  <text x="36" y="218" fill="var(--sem-soft)" font-size="14.5" font-weight="bold">L3 · Instruction Chain (131,072 B)</text>
                  <text x="36" y="238" fill="var(--ink-primary)" font-size="14.5">AGENTS.md / CLAUDE.md 注入 user message</text>
                  <text x="36" y="254" fill="var(--sem-break)" font-size="14">断点: 不读 .agents/rules/* · 用户级 AGENTS.md 常缺失</text>
                </g>

                <g class="layer-node" data-kind="soft">
                  <rect x="20" y="278" width="434" height="60" rx="4" fill="var(--svg-node)" stroke="var(--svg-stroke)"/>
                  <text x="36" y="300" fill="var(--ink-secondary)" font-size="14.5" font-weight="bold">L4 · Memory Layer (非原生)</text>
                  <text x="36" y="320" fill="var(--ink-primary)" font-size="14.5">dsh-mnemon 独立存储 (MEMORY.md / USER.md)</text>
                </g>

                <g class="layer-node" data-kind="soft break">
                  <rect x="20" y="352" width="434" height="68" rx="4" fill="var(--svg-node)" stroke="var(--svg-stroke)"/>
                  <text x="36" y="374" fill="var(--ink-secondary)" font-size="14.5" font-weight="bold">L5 · Plugins &amp; Cordis Patch</text>
                  <text x="36" y="394" fill="var(--ink-primary)" font-size="14.5">profile bundles + cordis.patch.yml</text>
                  <text x="36" y="410" fill="var(--sem-break)" font-size="14">断点: 工作区 .agents/mcp_config.json 无注册即为死配置</text>
                </g>

                <path d="M 454 230 L 488 230 L 488 76 L 502 76" fill="none" stroke="var(--accent-secondary)" stroke-width="1.5" marker-end="url(#arr-ink)"/>

                <g class="layer-node" data-kind="hard">
                  <rect x="506" y="40" width="434" height="72" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                  <text x="522" y="64" fill="var(--sem-gate)" font-size="14.5" font-weight="bold">L6 · Tool Sandbox</text>
                  <text x="522" y="86" fill="var(--ink-primary)" font-size="14.5">每次工具调用应用 permission presets</text>
                </g>

                <path d="M 723 112 L 723 140" fill="none" stroke="var(--sem-gate)" stroke-width="1.5" marker-end="url(#arr-gate)"/>

                <g class="layer-node" data-kind="hard break">
                  <rect x="506" y="144" width="434" height="92" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                  <text x="522" y="168" fill="var(--sem-gate)" font-size="14.5" font-weight="bold">L7 · Third-Party Interceptors</text>
                  <text x="522" y="190" fill="var(--ink-primary)" font-size="14.5">cc-safety-net 拦截裸 git commit / push / rebase</text>
                  <text x="522" y="208" fill="var(--ink-primary)" font-size="14.5">本地 .githooks/pre-commit &amp; commit-msg</text>
                  <text x="522" y="226" fill="var(--sem-break)" font-size="14">断点: cc-safety-net 仅覆盖 ops_bash 字面 token</text>
                </g>

                <path d="M 723 236 L 723 266" fill="none" stroke="var(--sem-gate)" stroke-width="1.5" marker-end="url(#arr-gate)"/>

                <g class="layer-node" data-kind="hard break">
                  <rect x="506" y="270" width="434" height="150" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)" stroke-width="1.4"/>
                  <text x="522" y="294" fill="var(--sem-gate)" font-size="14.5" font-weight="bold">L8 · Git Write Entry &amp; DPAPI Vault</text>
                  <text x="522" y="316" fill="var(--ink-primary)" font-size="14.5">唯一写入口: git-vault MCP (vault_commit_push)</text>
                  <text x="522" y="336" fill="var(--ink-primary)" font-size="14.5">前置审计: compliance_guard + checker + approval_gate</text>
                  <text x="522" y="356" fill="var(--ink-primary)" font-size="14.5">认证管道: Windows DPAPI → stdin/stdout 传递 token</text>
                  <text x="522" y="380" fill="var(--sem-break)" font-size="14">断点: audit_pre_commit 扫全树且无视 .gitignore</text>
                  <text x="522" y="398" fill="var(--sem-soft)" font-size="14">边界: 同 Windows 用户进程可解密 DPAPI</text>
                </g>
              </svg>
            </div>
          </div>
        </div>

        <h3 id="h-1-evidence" data-toc-level="2" data-toc-label="取证、Rank 与断点明细">源码取证、Rank 裁决与断点清单</h3>
        <div class="tabs-panel" data-tabs="sec1-tabs">
          <div class="tabs-nav" role="tablist">
            <button class="tab-btn active" role="tab" data-tab="t-layers" type="button">8 层载体与源码证据</button>
            <button class="tab-btn" role="tab" data-tab="t-ranks" type="button">6 级技能根 Rank 裁决</button>
            <button class="tab-btn" role="tab" data-tab="t-breaks" type="button">13 条已知断点清单</button>
          </div>

          <div class="tab-pane active" id="t-layers">
            <div class="table-scroll">
              <table>
                <thead>
                  <tr><th>#</th><th>层级</th><th>载体</th><th>注入 / 执行通道</th><th>取证坐标</th></tr>
                </thead>
                <tbody>
                  <tr><td>1</td><td>基线</td><td>dsh-base bundle</td><td>System Prompt</td><td><code>${{DSH_HOME}}/profiles/&lt;profile&gt;/package.json</code></td></tr>
                  <tr><td>2</td><td>技能目录</td><td>6 个技能根</td><td><code>dsh-tool-skill</code> 渲染</td><td><code>asar:2526620-2526805</code></td></tr>
                  <tr><td>3</td><td>指令链</td><td>AGENTS.md / CLAUDE.md</td><td><code>dsh-agent-instructions</code> 注入 user message</td><td><code>asar:344347-344352</code></td></tr>
                  <tr><td>4</td><td>记忆层</td><td>MEMORY.md / USER.md</td><td><code>dsh-mnemon</code> 插件（非原生）</td><td>asar 零命中</td></tr>
                  <tr><td>5</td><td>插件层</td><td>bundles + cordis.patch.yml</td><td>Cordis YAML</td><td><code>cordis.patch.yml</code></td></tr>
                  <tr><td>6</td><td>工具沙箱</td><td>permission presets</td><td>每次工具调用校验</td><td><code>cordis.patch.yml:38-52</code></td></tr>
                  <tr><td>7</td><td>第三方拦截</td><td>cc-safety-net / gitconfig</td><td>hook / 进程配置</td><td><code>global-deny/rulebook.json</code></td></tr>
                  <tr><td>8</td><td>Git 写入口</td><td>git-vault MCP + DPAPI</td><td>MCP 工具 + credential helper</td><td><code>vault_commit_push</code> / <code>vault_git_*</code></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="tab-pane" id="t-ranks">
            <div class="prose" style="margin-bottom: 12px; font-size: 15px;">
              裁决规则：<strong>最近 scope 胜</strong>；同层按 rank 升序先到先得。发现深度固定为 1，仅识别 <code>&lt;root&gt;/&lt;name&gt;/SKILL.md</code> 与 <code>&lt;root&gt;/&lt;name&gt;.md</code>。
            </div>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr><th>Rank</th><th>技能根路径</th><th>作用域与本机实测状态</th></tr>
                </thead>
                <tbody>
                  <tr><td><code>100</code></td><td><code>&lt;project-root&gt;/.dsh/skills</code></td><td>项目私有最高优先级（本仓未启用）</td></tr>
                  <tr><td><code>200</code></td><td><code>&lt;project-root&gt;/.agents/skills</code></td><td>项目共享，<strong>本仓实际承载载体</strong>（{skills_count} 个技能）</td></tr>
                  <tr><td><code>250</code></td><td>runtime provider</td><td>非文件系统根，运行时内存注册注入</td></tr>
                  <tr><td><code>300</code></td><td>custom dirs</td><td>用户配置自定义目录</td></tr>
                  <tr><td><code>400</code></td><td><code>${{DSH_HOME}}/skills</code></td><td>用户级，常为中央库符号链接（本机存在）</td></tr>
                  <tr><td><code>500</code></td><td><code>~/.agents/skills</code></td><td><span class="tag tag-break">断点</span> 用户级共享，本机目录缺失不生效</td></tr>
                  <tr><td><code>600</code></td><td>bundled</td><td>随安装包分发内置技能</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="tab-pane" id="t-breaks">
            <div class="table-scroll">
              <table>
                <thead>
                  <tr><th>#</th><th>断点描述</th><th>实际影响 / 缓解方式</th></tr>
                </thead>
                <tbody>
                  <tr><td>1</td><td>用户级 <code>AGENTS.md</code> 常缺失</td><td>跨项目全局偏好无载体</td></tr>
                  <tr><td>2</td><td>工作区 <code>.agents/mcp_config.json</code> 未被插件加载</td><td>若无 Cordis 注册即为死配置；checker 禁真实凭据入库</td></tr>
                  <tr><td>3</td><td>安全插件规则集为空 = 纯审计</td><td>必须显式配置 <code>global-deny/rulebook.json</code></td></tr>
                  <tr><td>4</td><td>合规守卫只拦 MCP 路径</td><td>裸 git 靠 <code>cc-safety-net</code> + <code>.githooks</code> 双重兜底</td></tr>
                  <tr><td>5</td><td>技能中央库只部署少量符号链接</td><td>Windows 符号链接权限受限，改用复制安装</td></tr>
                  <tr><td>6</td><td>中央库重名条目导致部署不确定</td><td>按 rank 先到先得，须保持命名唯一</td></tr>
                  <tr><td>7</td><td>状态库同构重复（双份 accounts）</td><td>需人工核对避免状态漂移</td></tr>
                  <tr><td>8</td><td>代理端口与实际 egress 错配</td><td>曾导致 11455 TLS 失败，本仓移除仓级代理改直连</td></tr>
                  <tr><td>9</td><td>明文凭据散落在配置与运行时文件</td><td>移出至 <code>_quarantine/</code> 并收紧本机 ACL</td></tr>
                  <tr><td>10</td><td>空壳目录与 <code>.bak</code> 堆积</td><td>checker <code>STRUCTURE</code> 巡检清理</td></tr>
                  <tr><td>11</td><td>技能 rank 500（<code>~/.agents/skills</code>）目录缺失</td><td>用户级共享技能不生效，以 rank 400 / 200 承载</td></tr>
                  <tr><td>12</td><td><code>audit_pre_commit</code> 扫整棵树且无视 <code>.gitignore</code></td><td>被 git 忽略的大文件同样阻断推送</td></tr>
                  <tr><td>13</td><td>凭据与 &gt;50 MB 大文件必须移出仓库根</td><td>统一外置到同级隔离区 <code>_quarantine/</code></td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <!-- 02 -->
      <section id="sec-2">
        <div class="sec-num">02 // RULES, GATES &amp; SCRIPT TOPOLOGY</div>
        <h2 id="h-sec-2" data-toc-level="1" data-toc-num="02" data-toc-label="规则体系、门禁与脚本拓扑">规则体系、门禁阈值与 {scripts_count} 个脚本调用拓扑</h2>
        <div class="prose">
          <p>
            v2 架构将分散的 <code>modes/</code> 合并为自动发现技能 <code>task-modes</code>，收敛出 <strong>{rules_count} 条专项规则</strong>与 <strong>{skills_count} 个技能</strong>。<code>check_governance.py --strict</code> 执行 {checks_count} 类静态检查，任一阻塞项即返回非零退出码。
          </p>
        </div>

        <h3 id="h-2-checks" data-toc-level="2" data-toc-label="19 类静态检查项">{checks_count} 类静态检查项</h3>
        <div class="checks-wrap" aria-label="静态门禁检查列表">
          {checks_html}
        </div>

        <h3 id="h-2-topology" data-toc-level="2" data-toc-label="核心脚本调用拓扑">核心脚本调用拓扑（FIG 2.0）</h3>
        <div class="wide">
          <div class="plate">
            <div class="plate-head">
              <span class="plate-caption">FIG 2.0 · 核心脚本调用拓扑（冷启动 / 提交门禁 / 分发同步）</span>
            </div>
            <div class="plate-body">
              <svg viewBox="0 0 1080 326" xmlns="http://www.w3.org/2000/svg" aria-label="脚本调用拓扑图">
                <defs>
                  <marker id="sc-arr-b" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent-secondary)"/>
                  </marker>
                  <marker id="sc-arr-g" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--sem-gate)"/>
                  </marker>
                  <marker id="sc-arr-p" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent-primary)"/>
                  </marker>
                </defs>

                <text x="16" y="26" fill="var(--accent-secondary)" font-size="13" font-weight="bold">LANE A · 工作区冷启动与外部核验</text>
                <rect x="16" y="38" width="248" height="60" rx="4" fill="var(--svg-node)" stroke="var(--accent-secondary)"/>
                <text x="30" y="62" fill="var(--accent-secondary)" font-size="14" font-weight="bold">bootstrap_workspace.py</text>
                <text x="30" y="84" fill="var(--ink-secondary)" font-size="12.5">闭包复制 + 探测 vault + git-mode</text>

                <path d="M 264 68 L 296 68" fill="none" stroke="var(--accent-secondary)" stroke-width="1.4" marker-end="url(#sc-arr-b)"/>

                <rect x="300" y="38" width="244" height="60" rx="4" fill="var(--svg-node)" stroke="var(--accent-secondary)"/>
                <text x="314" y="62" fill="var(--accent-secondary)" font-size="14" font-weight="bold">verify_governance.py</text>
                <text x="314" y="84" fill="var(--ink-secondary)" font-size="12.5">核验 hooks / 外部工具 / 占位符</text>

                <path d="M 544 68 L 576 68" fill="none" stroke="var(--accent-secondary)" stroke-width="1.4" marker-end="url(#sc-arr-b)"/>

                <rect x="580" y="38" width="240" height="60" rx="4" fill="var(--svg-node)" stroke="var(--svg-stroke)"/>
                <text x="594" y="62" fill="var(--ink-primary)" font-size="14" font-weight="bold">fetch_vault.py</text>
                <text x="594" y="84" fill="var(--ink-secondary)" font-size="12.5">拉取 vault.pyz + SHA256 校验</text>

                <rect x="840" y="38" width="224" height="60" rx="4" fill="var(--svg-node)" stroke="var(--svg-stroke)"/>
                <text x="854" y="62" fill="var(--ink-primary)" font-size="14" font-weight="bold">probe_confined.py</text>
                <text x="854" y="84" fill="var(--ink-secondary)" font-size="12.5">沙箱写权限探针取证</text>

                <text x="16" y="134" fill="var(--sem-gate)" font-size="13" font-weight="bold">LANE B · 提交前同源双门禁（本地 Hook &amp; git-vault 共用）</text>
                <rect x="16" y="146" width="216" height="62" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="30" y="170" fill="var(--sem-gate)" font-size="14" font-weight="bold">.githooks/pre-commit</text>
                <text x="30" y="192" fill="var(--ink-secondary)" font-size="12.5">本地 hook / vault 同源触发</text>

                <path d="M 232 166 L 272 166" fill="none" stroke="var(--sem-gate)" stroke-width="1.4" marker-end="url(#sc-arr-g)"/>
                <path d="M 232 188 L 272 188" fill="none" stroke="var(--sem-gate)" stroke-width="1.4" marker-end="url(#sc-arr-g)"/>

                <rect x="276" y="146" width="256" height="62" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="290" y="170" fill="var(--sem-gate)" font-size="14" font-weight="bold">check_governance.py</text>
                <text x="290" y="192" fill="var(--ink-secondary)" font-size="12.5">{checks_count} 类静态扫描（含 PAYLOAD）</text>

                <rect x="552" y="146" width="238" height="62" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="566" y="170" fill="var(--sem-gate)" font-size="14" font-weight="bold">approval_gate.py</text>
                <text x="566" y="192" fill="var(--ink-secondary)" font-size="12.5">4 类高风险改动校验收据</text>

                <path d="M 790 177 L 836 177" fill="none" stroke="var(--sem-gate)" stroke-width="1.4" marker-end="url(#sc-arr-g)"/>

                <rect x="840" y="146" width="224" height="62" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="854" y="170" fill="var(--sem-gate)" font-size="14" font-weight="bold">.githooks/commit-msg</text>
                <text x="854" y="192" fill="var(--ink-secondary)" font-size="12.5">Rule 14 §3 提交格式校验</text>

                <text x="16" y="244" fill="var(--accent-primary)" font-size="13" font-weight="bold">LANE C · 技能载荷打包、白皮书同步与公开导出</text>
                <rect x="16" y="256" width="248" height="60" rx="4" fill="var(--svg-node)" stroke="var(--accent-primary)"/>
                <text x="30" y="280" fill="var(--accent-primary)" font-size="14" font-weight="bold">build_skill_payload.py</text>
                <text x="30" y="302" fill="var(--ink-secondary)" font-size="12.5">生成 assets + MANIFEST</text>

                <path d="M 264 286 L 296 286" fill="none" stroke="var(--accent-primary)" stroke-width="1.4" marker-end="url(#sc-arr-p)"/>

                <rect x="300" y="256" width="244" height="60" rx="4" fill="var(--svg-node)" stroke="var(--accent-primary)"/>
                <text x="314" y="280" fill="var(--accent-primary)" font-size="14" font-weight="bold">package_skill / install</text>
                <text x="314" y="302" fill="var(--ink-secondary)" font-size="12.5">打 tar.gz 包 &amp; 部署全局技能根</text>

                <path d="M 544 286 L 576 286" fill="none" stroke="var(--accent-primary)" stroke-width="1.4" marker-end="url(#sc-arr-p)"/>

                <rect x="580" y="256" width="240" height="60" rx="4" fill="var(--svg-node)" stroke="var(--accent-primary)"/>
                <text x="594" y="280" fill="var(--accent-primary)" font-size="14" font-weight="bold">export_public.py</text>
                <text x="594" y="302" fill="var(--ink-secondary)" font-size="12.5">白名单快照 + 路径脱敏</text>

                <rect x="840" y="256" width="224" height="60" rx="4" fill="var(--svg-node)" stroke="var(--accent-primary)"/>
                <text x="854" y="280" fill="var(--accent-primary)" font-size="14" font-weight="bold">build_whitepaper.py</text>
                <text x="854" y="302" fill="var(--ink-secondary)" font-size="12.5">解析源码重建本文档</text>
              </svg>
            </div>
          </div>
        </div>

        <h3 id="h-2-approval" data-toc-level="2" data-toc-label="approval_gate 收据契约"><code>approval_gate.py</code> 四类受控变更与收据契约</h3>
        <div class="prose">
          <p>
            当暂存区命中以下任一条件时，<code>approval_gate.py</code> 拦截提交，要求在 <code>.agents/approvals/*.md</code> 同次暂存包含 6 个必填字段（<code>category</code>、<code>targets</code>、<code>impact</code>、<code>rollback</code>、<code>approver</code>、<code>date</code>）的审批收据：
          </p>
        </div>

        <div class="wide">
          <div class="table-scroll">
            <table>
              <thead>
                <tr><th>收据类别 (category)</th><th>触发阈值 / 受保护路径</th><th>门禁行为</th></tr>
              </thead>
              <tbody>
                <tr><td><code>deletion</code></td><td>单次提交删除文件数 <strong>≥ 2</strong></td><td>缺收据则 <code>pre-commit</code> 阻断</td></tr>
                <tr><td><code>protected-change</code></td><td>改动 <code>AGENTS.md</code>、<code>.agents/rules/</code>、<code>check_governance.py</code>、<code>approval_gate.py</code>、<code>.githooks/</code></td><td>缺收据则阻断</td></tr>
                <tr><td><code>dependency</code></td><td>改动 <code>requirements.txt</code>、<code>package.json</code>、<code>package-lock.json</code>、<code>pnpm-lock.yaml</code>、<code>pyproject.toml</code>、<code>poetry.lock</code></td><td>缺收据则阻断</td></tr>
                <tr><td><code>gate-change</code></td><td>改动 <code>.githooks/</code>、<code>check_governance.py</code>、<code>approval_gate.py</code> 或登记 <code>git-mode</code> 备案例外</td><td>缺收据则阻断</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <h3 id="h-2-inventories" data-toc-level="2" data-toc-label="规则、脚本与技能清单">规则、脚本与技能全量清单</h3>
        <details class="drawer">
          <summary>专项规则全景矩阵（共 {rules_count} 条 · 自动同步自 .agents/rules/）</summary>
          <div class="drawer-inner">
            <div class="table-scroll">
              <table>
                <thead>
                  <tr><th>规则文件</th><th>权威职责 (scope)</th><th>触发场景 (trigger)</th><th>强制级别</th></tr>
                </thead>
                <tbody>
                  {rules_tbody}
                </tbody>
              </table>
            </div>
          </div>
        </details>

        <details class="drawer">
          <summary>全量 Python 治理脚本清单（共 {scripts_count} 个 · 自动同步自源码）</summary>
          <div class="drawer-inner">
            <div class="table-scroll">
              <table>
                <thead>
                  <tr><th>脚本路径</th><th>所属域</th><th>核心职责</th></tr>
                </thead>
                <tbody>
                  {scripts_tbody}
                </tbody>
              </table>
            </div>
          </div>
        </details>

        <details class="drawer">
          <summary>自动发现技能目录（共 {skills_count} 个 · 自动同步自 .agents/skills/）</summary>
          <div class="drawer-inner">
            <div class="skill-cols">
              {skills_grid}
            </div>
          </div>
        </details>
      </section>

      <!-- 03 -->
      <section id="sec-3">
        <div class="sec-num">03 // GIT STATE MACHINE &amp; CREDENTIALS</div>
        <h2 id="h-sec-3" data-toc-level="1" data-toc-num="03" data-toc-label="Git 状态机与 DPAPI 边界">Git 写入口、<code>git-mode</code> 状态机与 DPAPI 凭据边界</h2>
        <div class="prose">
          <p>
            全仓 {rules_count} 条规则中，仅 <code>14-git-workflow.md</code> 具备 <code>enforcement: hook</code>。只读 Git 命令直接放行；写操作必须经由 <strong>git-vault MCP</strong> 网关。初始化时 <code>bootstrap_workspace.py</code> 探测 <code>GIT_VAULT_API</code>（<code>127.0.0.1:8765</code>）并将决策写入 <code>.agents/git-mode.json</code>。
          </p>
        </div>

        <h3 id="h-3-flow" data-toc-level="2" data-toc-label="写入口与状态机流转">写入口分流与双门禁流转（FIG 3.0）</h3>
        <div class="wide">
          <div class="plate">
            <div class="plate-head">
              <span class="plate-caption">FIG 3.0 · Git 写入口分流、git-mode 状态机与 DPAPI 管道</span>
            </div>
            <div class="plate-body">
              <svg viewBox="0 0 1080 340" xmlns="http://www.w3.org/2000/svg" aria-label="Git 双门禁与状态机流转图">
                <defs>
                  <marker id="g-arr-b" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent-secondary)"/>
                  </marker>
                  <marker id="g-arr-g" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--sem-gate)"/>
                  </marker>
                  <marker id="g-arr-r" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--sem-break)"/>
                  </marker>
                </defs>

                <rect x="16" y="126" width="166" height="68" rx="4" fill="var(--svg-node)" stroke="var(--accent-secondary)"/>
                <text x="99" y="156" fill="var(--accent-secondary)" font-size="14" font-weight="bold" text-anchor="middle">Agent Git Intent</text>
                <text x="99" y="178" fill="var(--ink-secondary)" font-size="12.5" text-anchor="middle">只读 / 写操作分流</text>

                <path d="M 182 142 L 246 58" fill="none" stroke="var(--accent-secondary)" stroke-width="1.4" marker-end="url(#g-arr-b)"/>
                <rect x="250" y="22" width="268" height="62" rx="4" fill="var(--svg-node)" stroke="var(--svg-stroke)"/>
                <text x="266" y="48" fill="var(--ink-primary)" font-size="14" font-weight="bold">Read-Only Git</text>
                <text x="266" y="70" fill="var(--ink-secondary)" font-size="12.5">status / diff / log 直接放行</text>

                <path d="M 182 178 L 246 254" fill="none" stroke="var(--sem-break)" stroke-width="1.4" marker-end="url(#g-arr-r)"/>
                <rect x="250" y="218" width="268" height="102" rx="4" fill="var(--svg-node)" stroke="var(--sem-break)"/>
                <text x="266" y="242" fill="var(--sem-break)" font-size="14" font-weight="bold">裸写 / git-mode 例外态</text>
                <text x="266" y="264" fill="var(--ink-primary)" font-size="12.5">cc-safety-net 拒绝裸写</text>
                <text x="266" y="286" fill="var(--ink-muted)" font-size="12">registered-exception (30d 过期)</text>
                <text x="266" y="308" fill="var(--sem-break)" font-size="12">vault 在线时 checker 直接 BLOCK</text>

                <path d="M 182 160 L 246 160" fill="none" stroke="var(--sem-gate)" stroke-width="1.5" marker-end="url(#g-arr-g)"/>
                <rect x="250" y="112" width="268" height="88" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="266" y="138" fill="var(--sem-gate)" font-size="14" font-weight="bold">git-vault MCP (mode: vault)</text>
                <text x="266" y="162" fill="var(--ink-primary)" font-size="12.5">vault_commit_push / vault_git_*</text>
                <text x="266" y="184" fill="var(--ink-muted)" font-size="12">127.0.0.1:8765 · mcp_audit.log</text>

                <path d="M 518 156 L 560 156" fill="none" stroke="var(--sem-gate)" stroke-width="1.5" marker-end="url(#g-arr-g)"/>
                <rect x="564" y="88" width="268" height="136" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="580" y="114" fill="var(--sem-gate)" font-size="14" font-weight="bold">双门禁同源校验</text>
                <text x="580" y="140" fill="var(--ink-primary)" font-size="12.5">1. compliance_guard 全树扫描</text>
                <text x="580" y="160" fill="var(--ink-muted)" font-size="12">(无视 .gitignore · 禁 &gt;50MB)</text>
                <text x="580" y="186" fill="var(--ink-primary)" font-size="12.5">2. .githooks/pre-commit</text>
                <text x="580" y="206" fill="var(--ink-muted)" font-size="12">checker + approval + commit-msg</text>

                <path d="M 832 156 L 866 156" fill="none" stroke="var(--sem-gate)" stroke-width="1.5" marker-end="url(#g-arr-g)"/>
                <rect x="870" y="96" width="194" height="120" rx="4" fill="var(--svg-node)" stroke="var(--accent-secondary)"/>
                <text x="886" y="124" fill="var(--accent-secondary)" font-size="14" font-weight="bold">DPAPI 管道推送</text>
                <text x="886" y="150" fill="var(--ink-primary)" font-size="12.5">stdin/stdout 传 token</text>
                <text x="886" y="172" fill="var(--ink-muted)" font-size="12">不落 argv / URL</text>
                <text x="886" y="196" fill="var(--sem-gate)" font-size="12">GitHub / Gitee / GitLab</text>
              </svg>
            </div>
          </div>
        </div>

        <h3 id="h-3-dpapi" data-toc-level="2" data-toc-label="合规守卫与 DPAPI 物理边界">合规守卫与 DPAPI 物理边界</h3>
        <div class="prose">
          <div class="note-block warn">
            <div class="note-title">工程诚实性标注：全树扫描与 DPAPI 物理边界</div>
            <p>
              <code>audit_pre_commit</code> 扫描整个工作树且<strong>无视 <code>.gitignore</code></strong>：超过 Gitee 50 MB 限额的大文件或明文凭据必须移出到仓库外的同级隔离区 <code>_quarantine/</code>。此外，Windows DPAPI 由当前用户加密，同用户进程仍可解密；强物理隔离需以独立服务账户运行网关。
            </p>
          </div>
        </div>
      </section>

      <!-- 04 -->
      <section id="sec-4">
        <div class="sec-num">04 // COOPERATION &amp; EVALS</div>
        <h2 id="h-sec-4" data-toc-level="1" data-toc-num="04" data-toc-label="双 Agent 协同与评测边界">双 Agent 协同与行为评测边界</h2>
        <div class="prose">
          <p>
            Rule 15 定义了基于 Agent HUD 会话互发的六种双窗口协作短码，并以<strong>令牌环写锁</strong>避免并发写冲突。同一报错连续 2 次修复未通过时熔断转入 <code>DIAGNOSE</code>；上下文水位达到或超过 <strong>70%</strong> 时强制原子提交并写进度账本后换新会话。
          </p>
        </div>

        <h3 id="h-4-matrix" data-toc-level="2" data-toc-label="6 种协同短码矩阵">6 种协同短码矩阵</h3>
        <div class="wide">
          <div class="table-scroll">
            <table>
              <thead>
                <tr><th>短码</th><th>协同模式</th><th>当前窗口</th><th>对方窗口</th></tr>
              </thead>
              <tbody>
                <tr><td><code>#mc</code></td><td>MAKER-CHECKER</td><td>CODER（编码 + 提交）</td><td>AUDITOR（只读盲审）</td></tr>
                <tr><td><code>#ae</code></td><td>ARCH-EDITOR</td><td>ARCHITECT（只读定稿）</td><td>EDITOR（按稿落盘）</td></tr>
                <tr><td><code>#tdd</code></td><td>TDD</td><td>TESTER（独占 <code>tests/</code>）</td><td>IMPLEMENTER（写业务源码）</td></tr>
                <tr><td><code>#ss</code></td><td>SCOUT-STRIKER</td><td>SCOUT（压缩坐标）</td><td>STRIKER（干净会话改码）</td></tr>
                <tr><td><code>#fix</code></td><td>DIAGNOSE</td><td>STUCK（停手冻结）</td><td>DIAGNOSTICIAN（盲测排障）</td></tr>
                <tr><td><code>#co</code></td><td>交互选单</td><td colspan="2">输出模式选单并标注推荐项，等待数字确认后再启动</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- 05 -->
      <section id="sec-5">
        <div class="sec-num">05 // DISTRIBUTION &amp; SYNC</div>
        <h2 id="h-sec-5" data-toc-level="1" data-toc-num="05" data-toc-label="公开仓分发与同步流水线">公开仓分发与白皮书同步流水线</h2>
        <div class="prose">
          <p>
            私有事实源通过 <code>build_skill_payload.py</code>（生成 <code>assets/MANIFEST.sha256</code>）与 <code>export_public.py</code>（白名单 + 路径脱敏 + STUB）输出干净快照，经 GitHub Actions 追加式同步至公开仓 <code>agent-framework-v2-template</code>。本文档通过零依赖脚本 <code>build_whitepaper.py</code> 直接解析仓库源码，支持本地与 CI 自动同步。
          </p>
        </div>

        <div class="wide">
          <div class="plate">
            <div class="plate-head">
              <span class="plate-caption">FIG 4.0 · 私有事实源 → 公开模板仓与白皮书自动同步</span>
            </div>
            <div class="plate-body">
              <svg viewBox="0 0 880 310" xmlns="http://www.w3.org/2000/svg" aria-label="公开仓分发与白皮书同步流水线">
                <defs>
                  <marker id="d-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--accent-primary)"/>
                  </marker>
                </defs>

                <!-- Row 1: 3 steps -->
                <rect x="16" y="16" width="256" height="124" rx="4" fill="var(--svg-node)" stroke="var(--accent-secondary)"/>
                <text x="34" y="46" fill="var(--accent-secondary)" font-size="16" font-weight="bold">1. 私有事实源</text>
                <text x="34" y="74" fill="var(--ink-primary)" font-size="15.5">AGENTS + rules 01-{rules_count}</text>
                <text x="34" y="98" fill="var(--ink-secondary)" font-size="15">{skills_count} 技能 · {checks_count} 项检查</text>
                <text x="34" y="122" fill="var(--ink-muted)" font-size="14">HEAD: {sha}</text>

                <path d="M 272 78 L 308 78" fill="none" stroke="var(--accent-primary)" stroke-width="1.6" marker-end="url(#d-arr)"/>

                <rect x="312" y="16" width="256" height="124" rx="4" fill="var(--svg-node)" stroke="var(--accent-primary)"/>
                <text x="330" y="46" fill="var(--accent-primary)" font-size="16" font-weight="bold">2. 构建与导出</text>
                <text x="330" y="74" fill="var(--ink-primary)" font-size="15.5">build_whitepaper.py</text>
                <text x="330" y="98" fill="var(--ink-primary)" font-size="15.5">export_public.py</text>
                <text x="330" y="122" fill="var(--ink-muted)" font-size="14.5">白名单 + 脱敏 + 同步</text>

                <path d="M 568 78 L 604 78" fill="none" stroke="var(--accent-primary)" stroke-width="1.6" marker-end="url(#d-arr)"/>

                <rect x="608" y="16" width="256" height="124" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="626" y="46" fill="var(--sem-gate)" font-size="16" font-weight="bold">3. CI 阻断自检</text>
                <text x="626" y="74" fill="var(--ink-primary)" font-size="15.5">checker --strict</text>
                <text x="626" y="98" fill="var(--ink-primary)" font-size="15.5">机器串 grep = 0</text>
                <text x="626" y="122" fill="var(--sem-break)" font-size="14.5">失败自动建 Issue</text>

                <!-- Connector Row 1 -> Row 2 -->
                <path d="M 736 140 L 736 156 L 288 156 L 288 170" fill="none" stroke="var(--accent-primary)" stroke-width="1.6" marker-end="url(#d-arr)"/>

                <!-- Row 2: 2 steps centered -->
                <rect x="160" y="174" width="256" height="120" rx="4" fill="var(--svg-node)" stroke="var(--accent-secondary)"/>
                <text x="178" y="204" fill="var(--accent-secondary)" font-size="16" font-weight="bold">4. 公开模板仓</text>
                <text x="178" y="232" fill="var(--ink-primary)" font-size="15.5">追加 rsync --delete</text>
                <text x="178" y="256" fill="var(--ink-secondary)" font-size="15">main 禁强推 / 禁删</text>
                <text x="178" y="280" fill="var(--ink-muted)" font-size="14">VERSION + skills 包</text>

                <path d="M 416 234 L 460 234" fill="none" stroke="var(--accent-primary)" stroke-width="1.6" marker-end="url(#d-arr)"/>

                <rect x="464" y="174" width="256" height="120" rx="4" fill="var(--svg-node)" stroke="var(--sem-gate)"/>
                <text x="482" y="204" fill="var(--sem-gate)" font-size="16" font-weight="bold">5. 目标工作区</text>
                <text x="482" y="232" fill="var(--ink-primary)" font-size="15.5">bootstrap_workspace</text>
                <text x="482" y="256" fill="var(--ink-primary)" font-size="15.5">verify_governance</text>
                <text x="482" y="280" fill="var(--ink-muted)" font-size="14.5">幂等冷启动</text>
              </svg>
            </div>
          </div>
        </div>
      </section>

      <!-- 06: Practical Scenarios -->
      <section id="sec-6">
        <div class="sec-num">06 // PRACTICAL SCENARIOS</div>
        <h2 id="h-sec-6" data-toc-level="1" data-toc-num="06" data-toc-label="实战使用场景（6 大工作流）">实战使用场景：从冷启动到多 Agent 协同</h2>
        <div class="prose">
          <p>
            本框架并非只服务于软件编码。依据 <code>AGENTS.md §2</code> 的任务模式路由，不同工作类型会加载截然不同的规则与工具链，严禁把开发流程机械套用到写作或调研任务上。
          </p>

          <div class="scenario-item">
            <h3 id="h-6-bootstrap" data-toc-level="2" data-toc-label="场景 1：新工作区冷启动建制">场景 1：新工作区冷启动建制</h3>
            <div class="scenario-meta">
              <span>触发：/governance-init 或 bootstrap_workspace.py</span>
              <span>门禁：verify_governance.py</span>
            </div>
            <h4 id="h-6-bootstrap-step" data-toc-level="3" data-toc-label="执行链路与状态核验">执行链路与状态核验</h4>
            <p>
              当把一个全新仓库纳入治理时，运行 <code>bootstrap_workspace.py --target &lt;dir&gt; --apply</code>。脚本会自动收集 <code>AGENTS.md</code> 与 rules 的引用闭包、探测 <code>git-vault</code> 在线状态写入 <code>.agents/git-mode.json</code>、生成带占位的 <code>PROJECT_ENV.md</code>，并只复制 <code>approvals/README.md</code> 而不会带入源仓历史收据。随后运行 <code>verify_governance.py --require-external --print-remedies</code> 核验本机 hooks 与环境变量是否真正就位。
            </p>
          </div>

          <div class="scenario-item">
            <h3 id="h-6-dev" data-toc-level="2" data-toc-label="场景 2：软件开发与高风险提交">场景 2：软件开发与高风险变更提交</h3>
            <div class="scenario-meta">
              <span>触发：task-modes §DEVELOPMENT</span>
              <span>规则：01–04, 05, 14</span>
            </div>
            <h4 id="h-6-dev-step" data-toc-level="3" data-toc-label="计划、收据与双门禁落盘">计划、收据与双门禁落盘</h4>
            <p>
              涉及多模块重构、契约修改或依赖变更时，先按规则 02 制定前置计划；提交时若命中删除 ≥ 2 文件或受保护路径，<code>approval_gate.py</code> 强制要求在 <code>.agents/approvals/</code> 同次提交审批收据。最终通过 <code>vault_commit_push</code> 经由 <code>compliance_guard</code> 与 <code>.githooks</code> 双门禁完成三端推送。
            </p>
          </div>

          <div class="scenario-item">
            <h3 id="h-6-coop" data-toc-level="2" data-toc-label="场景 3：双 Agent 协同与长会话交接">场景 3：双 Agent 协同与长会话交接</h3>
            <div class="scenario-meta">
              <span>触发：#mc / #tdd / #fix / #co</span>
              <span>规则：07, 08, 15</span>
            </div>
            <h4 id="h-6-coop-step" data-toc-level="3" data-toc-label="写锁流转与 70% 水位熔断">写锁流转与 70% 水位熔断</h4>
            <p>
              在支持 Agent HUD 的双窗口环境下，编码窗口与盲审窗口通过令牌环写锁互斥编辑源码；同一报错连续两次未修通时，立即冻结转入 <code>#fix</code> 盲测诊断，只发最小复现命令与 3–5 行原始报错。当会话上下文水位接近 70% 时，先原子提交，再将现场写入规则 07 进度账本并开启新会话。
            </p>
          </div>

          <div class="scenario-item">
            <h3 id="h-6-nondve" data-toc-level="2" data-toc-label="场景 4：非开发任务（文档/调研/创作）">场景 4：非开发任务（文档、调研与创意写作）</h3>
            <div class="scenario-meta">
              <span>触发：task-modes §DOCUMENTS / RESEARCH / CREATIVE</span>
              <span>原则：按需加载，零过度建制</span>
            </div>
            <h4 id="h-6-nondve-step" data-toc-level="3" data-toc-label="跳过代码门禁的轻量闭环">跳过代码门禁的轻量闭环</h4>
            <p>
              对于一次性调研报告、公文写作或小说创作，Agent 按 <code>AGENTS.md §2</code> 路由至对应的 <code>task-modes</code> 分支，不强制读取软件工程规则 01–04，也不强行初始化完整目录建制，仅按 §3 通用执行闭环完成事实核验与交付。
            </p>
          </div>

          <div class="scenario-item">
            <h3 id="h-6-quarantine" data-toc-level="2" data-toc-label="场景 5：大文件与凭据隔离排障">场景 5：大文件与明文凭据隔离排障</h3>
            <div class="scenario-meta">
              <span>触发：audit_pre_commit 或 SECRETS 阻断</span>
              <span>位置：_quarantine/</span>
            </div>
            <h4 id="h-6-quarantine-step" data-toc-level="3" data-toc-label="移出仓库根与原路还原">移出仓库根与原路还原</h4>
            <p>
              当仓库内残留超过 50 MB 的二进制包或明文配置文件（即使已写入 <code>.gitignore</code>）时，<code>audit_pre_commit</code> 会阻断推送。标准做法是保留相对路径形状将其移至仓库同级外部目录 <code>_quarantine/</code>，确保 <code>git add -A</code> 与全树合规扫描均不会触及，需要运行时再原路调回或脱敏。
            </p>
          </div>

          <div class="scenario-item">
            <h3 id="h-6-export" data-toc-level="2" data-toc-label="场景 6：规则迭代与公开仓同步">场景 6：规则迭代与公开模板仓同步</h3>
            <div class="scenario-meta">
              <span>触发：push main / tag v*</span>
              <span>脚本：build_skill_payload + export_public</span>
            </div>
            <h4 id="h-6-export-step" data-toc-level="3" data-toc-label="Payload 哈希校验与脱敏发布">Payload 哈希校验与脱敏发布</h4>
            <p>
              在私有仓修改规则或技能后，先运行 <code>build_skill_payload.py</code> 刷新 <code>assets/MANIFEST.sha256</code>，通过 <code>check_governance.py --strict</code> 后推送至 <code>main</code>；GitHub Actions 自动执行白名单导出、机器串 grep 断言、凭据扫描，并以追加式 commit 同步到公开仓 <code>agent-framework-v2-template</code>。
            </p>
          </div>
        </div>
      </section>

      <!-- 07: Rendered AGENTS.md Viewer -->
      <section id="sec-7">
        <div class="sec-num">07 // RAW ENTRYPOINT (RENDERED)</div>
        <h2 id="h-sec-7" data-toc-level="1" data-toc-num="07" data-toc-label="原始入口 AGENTS.md 全文">原始入口：<code>AGENTS.md</code> 全文检视</h2>
        <div class="prose">
          <p>
            作为 L3 指令链的唯一项目根入口，<code>AGENTS.md</code> 是每次会话都会被原生注入上下文的“工作地图”。下方默认以排版后的 Markdown 视图呈现，支持一键切换查看原始源码或复制全文。
          </p>
        </div>

        <h3 id="h-7-budget" data-toc-level="2" data-toc-label="指令链字节预算占比">指令链字节预算占用实测</h3>
        <div class="budget-bar">
          <div class="budget-top">
            <span>当前 <code>AGENTS.md</code> 体积：{agents_bytes:,} Bytes（{agents_lines} 行）</span>
            <span>占单链 65,536 B 上限：{budget_pct:.1f}%</span>
          </div>
          <div class="budget-track">
            <div class="budget-fill" style="width: {budget_pct:.1f}%;"></div>
          </div>
        </div>

        <h3 id="h-7-source" data-toc-level="2" data-toc-label="AGENTS.md 渲染视图与源码"><code>AGENTS.md</code> 全文（实时同步自 rev {sha}）</h3>
        <div class="source-viewer" id="agents-viewer">
          <div class="source-head">
            <span>AGENTS.md</span>
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
              <button class="btn-ghost" id="toggle-agents-mode" type="button">查看源码</button>
              <button class="btn-ghost" id="toggle-agents-expand" type="button">展开全文</button>
              <button class="btn-ghost copy-btn" type="button" data-copy-target="agents-raw-code">复制原文</button>
            </div>
          </div>
          <div class="source-body" id="agents-source-body">
            <div class="md-rendered">{agents_rendered}</div>
            <pre class="raw-pre"><code id="agents-raw-code">{agents_escaped}</code></pre>
          </div>
        </div>
      </section>

      <footer>
        <span>agent-framework-v2 · 治理架构工程白皮书</span>
        <span>rev {sha} · 生成于 {gen_at}</span>
      </footer>
    </main>

    <!-- Right Sticky Auto-Expanding 3-Level TOC -->
    <aside class="toc" id="toc">
      <div class="toc-caption">On This Page</div>
      <nav aria-label="白皮书三级目录">
        <ul class="toc-groups" id="toc-groups"></ul>
      </nav>
      <div class="toc-footnote">
        <div>构建基线: {sha}</div>
        <div>生成时间: {gen_at}</div>
        <div>脚本数: {scripts_count} 个工具</div>
      </div>
    </aside>
  </div>

  <script>
    (function () {{
      // 1. Theme toggle
      const root = document.documentElement;
      const themeBtn = document.getElementById('theme-toggle');
      const saved = localStorage.getItem('afv2-theme');
      if (saved === 'dark' || saved === 'light') {{
        root.setAttribute('data-theme', saved);
      }}
      function syncThemeLabel() {{
        const isDark = root.getAttribute('data-theme') === 'dark';
        themeBtn.textContent = isDark ? '暖纸浅色' : '深色模式';
      }}
      syncThemeLabel();
      themeBtn.addEventListener('click', () => {{
        const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        localStorage.setItem('afv2-theme', next);
        syncThemeLabel();
      }});

      // 2. Build grouped 3-level Right TOC (sub-items collapse by default, open on scroll or hover)
      const tocGroupsEl = document.getElementById('toc-groups');
      const headings = Array.from(document.querySelectorAll('[data-toc-level][id]'));
      const tocEntries = [];
      let currentGroupLi = null;
      let currentSubUl = null;

      headings.forEach((h) => {{
        const lvl = h.getAttribute('data-toc-level');
        const label = h.getAttribute('data-toc-label') || h.textContent.trim();
        const num = h.getAttribute('data-toc-num');

        const a = document.createElement('a');
        a.className = 'toc-link lvl-' + lvl;
        a.href = '#' + h.id;
        if (num) {{
          const span = document.createElement('span');
          span.className = 'toc-num';
          span.textContent = num;
          a.appendChild(span);
        }}
        const txt = document.createElement('span');
        txt.textContent = label;
        a.appendChild(txt);

        if (lvl === '1') {{
          currentGroupLi = document.createElement('li');
          currentGroupLi.className = 'toc-group';
          currentGroupLi.appendChild(a);
          currentSubUl = document.createElement('ul');
          currentSubUl.className = 'toc-sublist';
          currentGroupLi.appendChild(currentSubUl);
          tocGroupsEl.appendChild(currentGroupLi);
        }} else if (currentSubUl) {{
          const subLi = document.createElement('li');
          subLi.appendChild(a);
          currentSubUl.appendChild(subLi);
        }}

        tocEntries.push({{ el: h, link: a, group: currentGroupLi }});
      }});

      // 3. Scroll progress & auto-expanding 3-level scrollspy
      const bar = document.getElementById('progress-bar');
      function updateScroll() {{
        const doc = document.documentElement;
        const top = window.scrollY || doc.scrollTop;
        const max = doc.scrollHeight - doc.clientHeight;
        bar.style.width = (max > 0 ? Math.min(100, (top / max) * 100) : 0).toFixed(2) + '%';

        let current = tocEntries[0];
        const offset = 120;
        for (let i = 0; i < tocEntries.length; i++) {{
          if (tocEntries[i].el.getBoundingClientRect().top <= offset) {{
            current = tocEntries[i];
          }} else {{
            break;
          }}
        }}
        tocEntries.forEach((item) => {{
          item.link.classList.toggle('active', item === current);
          if (item.group) {{
            item.group.classList.toggle('is-open', item.group === current.group);
          }}
        }});
      }}
      window.addEventListener('scroll', updateScroll, {{ passive: true }});
      updateScroll();

      // 4. Mobile TOC drawer
      const toc = document.getElementById('toc');
      const mobBtn = document.getElementById('mobile-toc-toggle');
      mobBtn.addEventListener('click', () => {{
        const open = toc.classList.toggle('open');
        mobBtn.setAttribute('aria-expanded', String(open));
      }});
      tocEntries.forEach((item) => item.link.addEventListener('click', () => {{
        toc.classList.remove('open');
        mobBtn.setAttribute('aria-expanded', 'false');
      }}));

      // 5. Layer filter
      const segBtns = Array.from(document.querySelectorAll('.seg-btn'));
      const nodes = Array.from(document.querySelectorAll('.layer-node'));
      segBtns.forEach((btn) => {{
        btn.addEventListener('click', () => {{
          segBtns.forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          const f = btn.getAttribute('data-filter');
          nodes.forEach((n) => {{
            if (f === 'all') n.classList.remove('dimmed');
            else n.classList.toggle('dimmed', !(n.getAttribute('data-kind') || '').split(/\\s+/).includes(f));
          }});
        }});
      }});

      // 6. Tabbed panels
      document.querySelectorAll('.tabs-panel').forEach((panel) => {{
        const btns = Array.from(panel.querySelectorAll('.tab-btn'));
        const panes = Array.from(panel.querySelectorAll('.tab-pane'));
        btns.forEach((btn) => {{
          btn.addEventListener('click', () => {{
            const target = btn.getAttribute('data-tab');
            btns.forEach((b) => b.classList.toggle('active', b === btn));
            panes.forEach((p) => p.classList.toggle('active', p.id === target));
          }});
        }});
      }});

      // 7. AGENTS.md rendered/raw & expand toggles
      const viewer = document.getElementById('agents-viewer');
      const modeBtn = document.getElementById('toggle-agents-mode');
      const expandBtn = document.getElementById('toggle-agents-expand');
      const sourceBody = document.getElementById('agents-source-body');

      if (modeBtn && viewer) {{
        modeBtn.addEventListener('click', () => {{
          const isRaw = viewer.classList.toggle('show-raw');
          modeBtn.textContent = isRaw ? '渲染视图' : '查看源码';
          modeBtn.classList.toggle('active', isRaw);
        }});
      }}
      if (expandBtn && sourceBody) {{
        expandBtn.addEventListener('click', () => {{
          const expanded = sourceBody.classList.toggle('expanded');
          expandBtn.textContent = expanded ? '收起预览' : '展开全文';
        }});
      }}

      // 8. Copy buttons
      document.querySelectorAll('.copy-btn').forEach((btn) => {{
        btn.addEventListener('click', async () => {{
          const targetId = btn.getAttribute('data-copy-target');
          const text = targetId
            ? (document.getElementById(targetId)?.textContent || '')
            : (btn.getAttribute('data-copy') || '');
          try {{
            await navigator.clipboard.writeText(text);
            const orig = btn.textContent;
            btn.textContent = '已复制';
            setTimeout(() => {{ btn.textContent = orig; }}, 1500);
          }} catch (_) {{}}
        }});
      }});
    }})();
  </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Build agent-framework-v2 HTML whitepaper from repo source.")
    parser.add_argument("--repo", default=".", help="Path to agent-framework-v2 repo")
    parser.add_argument("--out", default="docs/index.html", help="Output HTML file path")
    args = parser.parse_args()

    if not os.path.isdir(args.repo):
        print(f"ERROR: repo directory not found: {args.repo}", file=sys.stderr)
        sys.exit(1)

    data = collect_repo_data(args.repo)
    html_out = render_html(data)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(
        f"Built {args.out} | rev={data['commit_sha']} | "
        f"agents_bytes={data['agents_md_bytes']} | rules={len(data['rules'])} | "
        f"skills={len(data['skills'])} | checks={len(data['checks'])} | scripts={len(data['scripts'])}"
    )


if __name__ == "__main__":
    main()
