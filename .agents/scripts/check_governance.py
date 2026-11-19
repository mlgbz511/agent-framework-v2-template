#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""治理自检（v2）：索引覆盖 / 单一权威 / 孤儿文件 / 凭据 / 死引用 / 伪 frontmatter /
技能元数据 / 结构 / 文档声明。用法：python .agents/scripts/check_governance.py [--strict]
退出码 0 = 无 BLOCK（--strict 时 WARN 也算失败）；1 = 存在 BLOCK。"""
import datetime, hashlib, io, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STRICT = "--strict" in sys.argv
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".tmp", ".cache"}
BIN_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".ico", ".woff", ".woff2")
BT = chr(96)
issues = []

def add(level, kind, msg):
    issues.append((level, "%s: %s" % (kind, msg)))

def read(rel):
    with io.open(os.path.join(ROOT, rel), "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def walk(rel_base=""):
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, rel_base)):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            yield os.path.relpath(full, ROOT).replace(os.sep, "/")

agents = read("AGENTS.md")
rule_files = sorted(f for f in os.listdir(os.path.join(ROOT, ".agents/rules")) if f.endswith(".md"))
rules_text = {f: read(".agents/rules/" + f) for f in rule_files}
skill_md = [p for p in walk(".agents/skills") if p.endswith("/SKILL.md")]

# 1. INDEX_COVERAGE: AGENTS.md 必须逐条显式列出每个规则文件
for f in rule_files:
    if ".agents/rules/" + f not in agents:
        add("BLOCK", "INDEX_COVERAGE", ".agents/rules/%s 未在 AGENTS.md 索引中显式列出" % f)
for m in re.finditer(r"\.agents/rules/([0-9A-Za-z\-]+\.md)", agents):
    if not os.path.exists(os.path.join(ROOT, ".agents/rules", m.group(1))):
        add("BLOCK", "DEAD_REF", "AGENTS.md 引用不存在的 .agents/rules/%s" % m.group(1))

# 2. DUP_NORM: 同一规范只允许在权威文件中定义，其他文件必须写成引用
TOPICS = [
    ("依赖准入", "04-reuse-and-supply-chain.md", r"依赖.{0,24}(准入|核对|审查|筛查)"),
    ("最小差异", "01-architecture-and-modularity.md", r"(最小(必要|有效)变更|外科手术式)"),
    ("防作弊", "02-contract-and-testing.md", r"(不得|禁止|严禁).{0,28}(删|跳过|关闭|削弱).{0,12}(断言|测试|检查)"),
    ("重试上限", "04-reuse-and-supply-chain.md", r"重试上限"),
    ("技能安装门禁", "13-skill-lifecycle-and-adaptation.md", r"(技能|Skill).{0,16}(安装|引入|接驳).{0,10}(门禁|审查|批准)"),
]
CORPUS = [("AGENTS.md", agents)]
CORPUS += [(".agents/rules/" + f, t) for f, t in rules_text.items()]
CORPUS += [(p, read(p)) for p in skill_md]
REF_MARK = re.compile(r"(唯一权威|以.{0,8}为准|见规则|见 0[0-9]|不重复定义|不另行定义|不重复维护|遵循|引用)")
for topic, owner, pat in TOPICS:
    dup = []
    for rel, text in CORPUS:
        if rel == owner or rel.endswith("/" + owner):
            continue
        for line in text.splitlines():
            if ".agents/rules/" in line:
                continue
            if re.search(pat, line) and not REF_MARK.search(line):
                dup.append(rel)
                break
    if dup:
        add("BLOCK", "DUP_NORM", "「%s」权威=%s，但 %s 仍在重复定义" % (topic, owner, sorted(set(dup))))

# 3. ORPHAN: docs/**、.agents/**（含 scripts/templates/drafts）与 scripts/** 必须有引用
ref_text = agents + "\n" + "\n".join(rules_text.values())
EXEMPT_NAME = {"README.md", "requirements.txt", "check_governance.py"}
for rel in list(walk(".agents")) + list(walk("docs")) + list(walk("scripts")):
    if rel.startswith(".agents/skills/"):
        continue
    if os.path.basename(rel) in EXEMPT_NAME:
        continue
    parts = rel.split("/")
    if any("/".join(parts[:i]) + "/" in ref_text for i in range(1, len(parts))) or rel in ref_text:
        continue
    add("WARN", "ORPHAN", "%s 零引用（AGENTS.md 与 rules 均未提及）" % rel)

# 4. SECRETS: 递归扫描治理面全部文本文件
SECRET = re.compile(
    r"(sk-[A-Za-z0-9_\-]{16,}|ntn_[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_\-]{16,}"
    r"|xox[bp]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY"
    r"|access_token=[A-Za-z0-9]{16,})")
for base in (".agents", "docs", "scripts"):
    for p in walk(base):
        if p.endswith(BIN_EXT) or os.path.basename(p) == "requirements.txt":
            continue
        try:
            text = read(p)
        except OSError:
            continue
        if SECRET.search(text):
            add("BLOCK", "SECRETS", "%s 含疑似明文凭据" % p)
if os.path.exists(os.path.join(ROOT, ".agents/mcp_config.json")):
    add("BLOCK", "SECRETS", ".agents/mcp_config.json 不应存在于工作区（真实配置应在隔离区）")

# 5. DEAD_REF: 反引号内含目录的 path[:line] 必须存在；行号不得越界（裸文件名按同目录引用处理，不校验）
TICK_RE = re.compile(BT + r"([^" + BT + r"\n]{3,120})" + BT)
SCAN_FILES = [("AGENTS.md", agents)] + [(".agents/rules/" + f, t) for f, t in rules_text.items()]
SCAN_FILES += [(p, read(p)) for p in skill_md]
GOV_DOCS = ("docs/governance-map.md", "docs/environment-todo.md", "docs/deploy.md",
            "docs/prereqs.md", "PROJECT_ENV.md", "docs/audits/p1-eval-plan.md")
for _d in GOV_DOCS:
    if os.path.exists(os.path.join(ROOT, _d)):
        SCAN_FILES.append((_d, read(_d)))
SCAN_FILES += [(p, read(p)) for p in walk("docs/audits/evals") if p.endswith(".md")]
MISSING_OK = {"docs/PROGRESS.md", "docs/DECISIONS.md", "docs/PROJECT_ENV.md", "docs/task_plan.md",
               ".agents/git-mode.json",
               ".agents/mcp_config.json", "DESIGN.md", "docs/DESIGN.md"}
EXTERNAL_PREFIX = ("core/", "_quarantine/", "dsh/", "E:/", "C:/")
seen_refs = set()
for src, text in SCAN_FILES:
    for m in TICK_RE.finditer(text):
        tok = m.group(1).strip()
        tm = re.match(r"^([A-Za-z0-9_\-\./]+\.(?:md|py|json|txt|sh|yml|yaml))(?:[:#](\d+))?$", tok)
        if not tm:
            continue
        rel, ln = tm.group(1), tm.group(2)
        if ".local." in rel or rel.startswith(("http", "~", "/", "$")):
            continue
        if "/" not in rel or rel in MISSING_OK or rel.startswith(EXTERNAL_PREFIX):
            continue
        key = (src, rel)
        if key in seen_refs:
            continue
        seen_refs.add(key)
        fp = os.path.join(ROOT, rel)
        if not os.path.exists(fp):
            level = "BLOCK" if rel.startswith((".agents/", "docs/", "scripts/")) else "WARN"
            add(level, "DEAD_REF", "%s 引用不存在的 %s" % (src, rel))
            continue
        if ln and rel.endswith(".md"):
            n = len(read(rel).splitlines())
            if int(ln) > n:
                add("WARN", "DEAD_REF", "%s 引用 %s:%s 超出文件行数(%d)" % (src, rel, ln, n))

# 6. FRONTMATTER: rules 不得含无消费者的伪元数据
for f, t in rules_text.items():
    body = t.lstrip("\ufeff\n \t")
    if body.startswith("---") and body.count("---") >= 2:
        head = body.split("---", 2)[1]
        if re.search(r"^\s*(globs|always_on|alwaysOn|applyTo)\s*:", head, re.M):
            add("BLOCK", "FRONTMATTER", "rules/%s 仍含 globs/always_on 伪元数据" % f)

# 6b. RULE_META: 规则 frontmatter 四字段（scope/trigger/enforcement/version）
META_KEYS = ("scope", "trigger", "enforcement", "version")
ENF_EVIDENCE = {
    "hook": ("checker", "pre-commit", "commit-msg"),
    "checker": ("checker", "check_governance"),
    "interceptor": ("cc-safety", "git-vault"),
    "none": (),
}
META_MAX = 80

def split_meta(text):
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None, ""
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    return None, ""

for f, t in rules_text.items():
    head_lines, body = split_meta(t)
    if head_lines is None:
        add("BLOCK", "RULE_META", "rules/%s 首行缺 frontmatter（--- 开头且闭合）" % f)
        continue
    meta, broken = {}, False
    for ln in head_lines:
        if not ln.strip():
            add("BLOCK", "RULE_META", "rules/%s frontmatter 含空行" % f)
            broken = True
            break
        if ":" not in ln:
            add("BLOCK", "RULE_META", "rules/%s frontmatter 行缺冒号：%s" % (f, ln.strip()[:40]))
            broken = True
            break
        k, v = ln.split(":", 1)
        k = k.strip()
        if k in meta:
            add("BLOCK", "RULE_META", "rules/%s frontmatter 字段重复：%s" % (f, k))
            broken = True
            break
        if k not in META_KEYS:
            add("BLOCK", "RULE_META", "rules/%s frontmatter 非法字段：%s" % (f, k))
            broken = True
            break
        meta[k] = v.strip()
    if broken:
        continue
    miss = [k for k in META_KEYS if k not in meta]
    if miss:
        add("BLOCK", "RULE_META", "rules/%s frontmatter 缺字段：%s" % (f, ",".join(miss)))
        continue
    for k in ("scope", "trigger"):
        v = meta[k]
        if not v:
            add("BLOCK", "RULE_META", "rules/%s 的 %s 为空" % (f, k))
        elif len(v) > META_MAX:
            add("BLOCK", "RULE_META", "rules/%s 的 %s 超 %d 字符（%d）" % (f, k, META_MAX, len(v)))
    enf = meta["enforcement"]
    if enf not in ENF_EVIDENCE:
        add("BLOCK", "RULE_META", "rules/%s enforcement=%s 非枚举（hook|checker|interceptor|none）" % (f, enf or "空"))
    elif ENF_EVIDENCE[enf] and not any(tok in body for tok in ENF_EVIDENCE[enf]):
        add("BLOCK", "RULE_META", "rules/%s enforcement=%s 但正文无对应证据（需含 %s 之一）"
            % (f, enf, "|".join(ENF_EVIDENCE[enf])))
    if not re.fullmatch(r"[1-9][0-9]*", meta["version"]):
        add("BLOCK", "RULE_META", "rules/%s version 非正整数：%s" % (f, meta["version"] or "空"))

# 6c. INDEX_TRIGGER: AGENTS.md §5 每条规则索引行必须带「读当」
for i, ln in enumerate(agents.splitlines(), 1):
    if not ln.lstrip().startswith("- ") or ".agents/rules/" not in ln:
        continue
    if "读当" not in ln:
        add("BLOCK", "INDEX_TRIGGER", "AGENTS.md:%d 规则索引行缺「读当」触发词" % i)

# 7. SKILL_META: 技能 frontmatter 与 DSH 目录渲染契约
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DESC_MAX = 500
for p in skill_md:
    text = read(p).lstrip("\ufeff\n \t")
    dirname = p.split("/")[-2]
    if not text.startswith("---") or text.count("---") < 2:
        add("BLOCK", "SKILL_META", "%s 缺 frontmatter" % p)
        continue
    head = text.split("---", 2)[1]
    nm = re.search(r"^name:\s*(.+)$", head, re.M)
    dm = re.search(r"^description:\s*(.+)$", head, re.M)
    if not nm:
        add("BLOCK", "SKILL_META", "%s 缺 name" % p)
    else:
        name = nm.group(1).strip().strip("'\"")
        if name != dirname:
            add("BLOCK", "SKILL_META", "%s name=%s 与目录名不一致" % (p, name))
        if not NAME_RE.match(name):
            add("BLOCK", "SKILL_META", "%s name 不符合 kebab-case" % p)
    if not dm:
        add("BLOCK", "SKILL_META", "%s 缺 description" % p)
    else:
        desc = dm.group(1).strip().strip("'\"")
        if len(desc) > DESC_MAX:
            add("BLOCK", "SKILL_META", "%s description %d 字符 > DSH 上限 %d，目录中会被截断"
                % (p, len(desc), DESC_MAX))
        if len(desc) < 20:
            add("WARN", "SKILL_META", "%s description 过短，路由效果差" % p)

# 8. STRUCTURE
if os.path.isdir(os.path.join(ROOT, ".agents/modes")):
    add("WARN", "STRUCTURE", ".agents/modes/ 仍存在（应已迁移至 skills/task-modes）")
if not os.path.exists(os.path.join(ROOT, ".agents/skills/task-modes/SKILL.md")):
    add("BLOCK", "STRUCTURE", "skills/task-modes/SKILL.md 缺失")
nums = [int(f[:2]) for f in rule_files if re.match(r"^\d\d-", f)]
if nums and nums != list(range(1, len(nums) + 1)):
    add("WARN", "STRUCTURE", "rules 编号不连续：%s" % nums)

# 9. CLAIMS: 关键运行时数字必须与实现一致
CLAIMS = [
    ("docs/governance-map.md", "65536", "指令链每链预算"),
    ("docs/governance-map.md", "131072", "两链合计预算"),
    ("AGENTS.md", "commit-msg", "提交信息钩子已接入"),
]
cache = {}
for rel, needle, what in CLAIMS:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        add("BLOCK", "CLAIMS", "%s 缺失（%s 需要该文件）" % (rel, what))
        continue
    if rel not in cache:
        cache[rel] = read(rel)
    if "STATUS: PLACEHOLDER" in cache[rel]:
        continue
    if needle not in cache[rel]:
        add("BLOCK", "CLAIMS", "%s 缺「%s」(%s 与实现不符)" % (rel, needle, what))

# 10. GIT_ENTRY: 规则 14 存在且 AGENTS 与规则同时声明唯一写入口
R14 = ".agents/rules/14-git-workflow.md"
if not os.path.exists(os.path.join(ROOT, R14)):
    add("BLOCK", "GIT_ENTRY", "%s 缺失（Git 写入口无权威定义）" % R14)
else:
    r14 = read(R14)
    if "git-vault" not in r14 or "唯一写入口" not in r14:
        add("BLOCK", "GIT_ENTRY", "%s 未声明 git-vault 为唯一写入口" % R14)
    if "git-vault" not in agents or "规则 14" not in agents:
        add("BLOCK", "GIT_ENTRY", "AGENTS.md 未把 git 写操作指向规则 14")

# 10b. CRED_ENTRY: 规则 14 必须声明凭据唯一来源，AGENTS 必须引用
if os.path.exists(os.path.join(ROOT, R14)):
    r14t = read(R14)
    if "凭据唯一来源" not in r14t:
        add("BLOCK", "CRED_ENTRY", "%s 缺§9「凭据唯一来源」" % R14)
    if "vault_proxy_api" not in r14t:
        add("BLOCK", "CRED_ENTRY", "%s 未声明经 vault_proxy_api 使用外部密钥" % R14)
if "规则 14 §9" not in agents:
    add("BLOCK", "CRED_ENTRY", "AGENTS.md 未引用规则 14 §9（凭据来源）")

# 11. REGISTRY: 托管仓库清单的每条路径必须存在或显式标记
REG = os.environ.get("GIT_VAULT_REGISTRY", "<path>/...")
if not os.path.exists(REG):
    pass  # 仓外工具未安装时静默跳过；缺失由 verify --require-external 报告
else:
    try:
        reg = json.load(io.open(REG, "r", encoding="utf-8"))
    except Exception as e:
        reg = {}
        add("WARN", "REGISTRY", "托管仓库清单无法解析：%s" % e)
    bad = []
    for entry in reg.get("managed_repos", []):
        p = entry.get("path", "")
        if not p or entry.get("is_archived") or entry.get("is_quarantined"):
            continue
        if not os.path.exists(p):
            bad.append(p)
    if bad:
        add("BLOCK", "REGISTRY", "托管清单 %d 条路径失效：%s" % (len(bad), bad[:4]))

# 12. FORCE_DENY: cc-safety-net 规则集不得为空（裸写拦截层）
CCR = os.environ.get("CC_SAFETY_RULE", os.path.expanduser("~/.cc-safety-net/rules/rule.json"))
if not os.path.exists(CCR):
    pass  # 拦截层未安装时静默跳过；由 verify --require-external 报告
else:
    try:
        ccr = json.load(io.open(CCR, "r", encoding="utf-8"))
    except Exception as e:
        ccr = {}
        add("WARN", "FORCE_DENY", "cc-safety-net 规则无法解析：%s" % e)
    if not ccr.get("rules"):
        add("WARN", "FORCE_DENY", "cc-safety-net rules 为空：Agent 裸写通道未被拦截")

# 12b. EVAL_STATUS: 行为评测状态文件格式与新鲜度
EVAL_DIR = "docs/audits/evals"
EVAL_KEYS = ("last_run", "E1", "E2", "E3", "recorded_by")
EVAL_VALS = ("确定性拦截", "指令层自律", "未通过", "未执行")
if not os.path.exists(os.path.join(ROOT, EVAL_DIR, "README.md")):
    add("BLOCK", "EVAL_STATUS", "docs/audits/evals/README.md 缺失")
if not os.path.exists(os.path.join(ROOT, EVAL_DIR, "status.md")):
    add("BLOCK", "EVAL_STATUS", "docs/audits/evals/status.md 缺失")
else:
    eval_fields = {}
    for ln in read(EVAL_DIR + "/status.md").splitlines():
        m = re.match(r"^(last_run|E1|E2|E3|recorded_by)\s*:\s*(.+?)\s*$", ln)
        if m:
            eval_fields[m.group(1)] = m.group(2)
    eval_miss = [k for k in EVAL_KEYS if k not in eval_fields]
    if eval_miss:
        add("BLOCK", "EVAL_STATUS", "status.md 缺字段：%s" % ",".join(eval_miss))
    for k in ("E1", "E2", "E3"):
        if k in eval_fields and eval_fields[k] not in EVAL_VALS:
            add("BLOCK", "EVAL_STATUS", "status.md 的 %s 取值非法：%s" % (k, eval_fields[k]))
    if "last_run" in eval_fields and eval_fields.get("recorded_by") != "template":
        try:
            _d = datetime.date.fromisoformat(eval_fields["last_run"])
            if (datetime.date.today() - _d).days > 180:
                add("WARN", "EVAL_STATUS", "评测记录超过 180 天未更新（last_run=%s）" % eval_fields["last_run"])
        except ValueError:
            add("BLOCK", "EVAL_STATUS", "status.md 的 last_run 非 ISO 日期：%s" % eval_fields["last_run"])

# 12b. GIT_MODE: 唯一写入口模式；备案态要求收据、期限，且 vault 在线时禁止使用
def _vault_online(timeout=1.5):
    import urllib.request
    try:
        url = os.environ.get("GIT_VAULT_API", "http://127.0.0.1:8765") + "/api/status"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 0) < 300
    except Exception:
        return False

GM_PATH = os.path.join(ROOT, ".agents/git-mode.json")
if os.path.exists(GM_PATH):
    try:
        gm = json.load(io.open(GM_PATH, "r", encoding="utf-8"))
    except Exception as e:
        add("BLOCK", "GIT_MODE", "git-mode.json 无法解析：%s" % e)
        gm = {}
    gmode = gm.get("mode")
    if gmode == "registered-exception":
        if _vault_online():
            add("BLOCK", "GIT_MODE", "vault 在线却处于 registered-exception：执行 init --git-mode vault")
        rec = gm.get("receipt") or ""
        if not rec or not os.path.exists(os.path.join(ROOT, rec)):
            add("BLOCK", "GIT_MODE", "备案缺收据：%s" % (rec or "(空)"))
        expires = gm.get("expires_at") or ""
        if expires:
            try:
                if datetime.date.today() > datetime.datetime.strptime(expires, "%Y-%m-%d").date():
                    add("BLOCK", "GIT_MODE", "备案已过期（%s）：复核或安装 vault" % expires)
            except ValueError:
                add("BLOCK", "GIT_MODE", "备案 expires_at 非法：%s" % expires)
    elif gmode == "vault":
        if not _vault_online():
            add("WARN", "GIT_MODE", "vault 离线：提交将失败；或按规则 14 §1.1 备案")
    elif gmode == "vault-missing":
        add("WARN", "GIT_MODE", "未安装 vault：运行 /init-gitvault，或按规则 14 §1.1 备案")
    elif gmode:
        add("WARN", "GIT_MODE", "未知 mode=%s" % gmode)

# 13. HOOK_PARITY: 网关提交路径必须调用仓内 checker
ENGINE = os.environ.get("GIT_VAULT_ENGINE", "<path>/...")
for hp in (".githooks/pre-commit", ".githooks/commit-msg"):
    if not os.path.exists(os.path.join(ROOT, hp)):
        add("BLOCK", "HOOK_PARITY", "%s 缺失（提交门禁不完整）" % hp)
if os.path.exists(os.path.join(ROOT, ".githooks/pre-commit")) and "approval_gate.py" not in read(".githooks/pre-commit"):
    add("BLOCK", "HOOK_PARITY", "pre-commit 未调用 approval_gate.py（审批收据门禁缺失）")
if not os.path.exists(ENGINE):
    pass  # git-vault 未安装时静默跳过；由 verify --require-external 报告
else:
    gate_files = [ENGINE, os.path.join(os.path.dirname(ENGINE), "compliance_guard.py")]
    gate_text = ""
    for gf in gate_files:
        if os.path.exists(gf):
            with io.open(gf, "r", encoding="utf-8", errors="replace") as _f:
                gate_text += _f.read()
    if "check_governance.py" not in gate_text:
        add("BLOCK", "HOOK_PARITY", "git-vault 提交路径未调用仓内 checker（双门禁不一致）")

# 15. SKILL_PAYLOAD: 技能自带 payload 必须与仓内文件一致（防漂移）
PAYLOAD_DIR = os.path.join(ROOT, ".agents/skills/governance-init/assets")
PAYLOAD_MAN = os.path.join(PAYLOAD_DIR, "MANIFEST.sha256")
if os.path.isdir(PAYLOAD_DIR):
    if not os.path.exists(PAYLOAD_MAN):
        add("BLOCK", "SKILL_PAYLOAD", "assets/MANIFEST.sha256 缺失：运行 python scripts/build_skill_payload.py")
    else:
        drift = []
        for line in read(os.path.join(".agents/skills/governance-init/assets", "MANIFEST.sha256")).splitlines():
            parts = line.split("  ", 1)
            if len(parts) != 2:
                continue
            want, rel = parts
            for path in (os.path.join(PAYLOAD_DIR, rel), os.path.join(ROOT, rel)):
                if not os.path.exists(path):
                    drift.append(rel + "(missing)")
                    break
                h = hashlib.sha256()
                with io.open(path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        h.update(chunk)
                if h.hexdigest() != want:
                    drift.append(rel)
                    break
        if drift:
            add("BLOCK", "SKILL_PAYLOAD", "技能 payload 与仓内不一致 %d 个：%s（重跑 build_skill_payload）"
                % (len(drift), drift[:3]))

blocks = [m for lv, m in issues if lv == "BLOCK" or STRICT]
for lv, m in issues:
    print("[%s] %s" % (lv, m))
if blocks:
    print("FAILED: %d issue(s)" % len(blocks))
    sys.exit(1)
print("OK: governance checks passed (%d warnings)" % len([1 for lv, _ in issues if lv == "WARN"]))