#!/usr/bin/env python3
"""
omo-model-set: Interactive TUI for configuring oh-my-openagent model settings.
Models are validated against those available in opencode.json.
"""
import curses
import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

# ─── Config paths ────────────────────────────────────────────────────────────
OPENCODE_JSON = Path.home() / ".config/opencode/opencode.json"
_CFG_DIR      = Path.home() / ".config/opencode"

# Plugin config file resolution priority (matches oh-my-openagent's own logic):
#   1. oh-my-openagent.json   (canonical)
#   2. oh-my-openagent.jsonc  (canonical, jsonc)
#   3. oh-my-opencode.json    (legacy)
#   4. oh-my-opencode.jsonc   (legacy, jsonc)
_OMO_CANDIDATES = [
    _CFG_DIR / "oh-my-openagent.json",
    _CFG_DIR / "oh-my-openagent.jsonc",
    _CFG_DIR / "oh-my-opencode.json",
    _CFG_DIR / "oh-my-opencode.jsonc",
]


def resolve_omo_path() -> Path:
    """Return the first existing config file, or the canonical default for creation."""
    for p in _OMO_CANDIDATES:
        if p.exists():
            return p
    return _OMO_CANDIDATES[0]          # oh-my-openagent.json

# ─── Agent / Category metadata ───────────────────────────────────────────────
# desc:        简短角色说明
# traits:      核心能力需求标签
# recommended: 按优先级排列的推荐模型 (provider/model)
# variant_rec: 推荐 variant，None 表示不设
INFO = {
    "agents": {
        "sisyphus": {
            "desc": "主编排器：任务规划、委派分发、驱动全流程至完成，激进并行执行",
            "traits": ["高智能", "长上下文", "多轮规划", "并行调度"],
            "recommended": [
                "kiro/claude-opus-4-6-1m",
                "bytecat-claude-real/claude-opus-4-6",
                "kiro/claude-opus-4-6",
                "kiro/claude-opus-4-6-1m-thinking",
            ],
            "variant_rec": "max",
        },
        "hephaestus": {
            "desc": "自主深度执行者：探索代码库、端到端实现，无需手把手引导",
            "traits": ["强代码能力", "自主执行", "深度探索", "工程实践"],
            "recommended": [
                "kiro/nova-swe",
                "msicu-codex/gpt-5.4",
                "kiro/qwen3-coder-480b",
                "volcengine/ark-code-latest",
                "kiro/gpt-oss-120b",
            ],
            "variant_rec": "xhigh",
        },
        "oracle": {
            "desc": "只读高IQ顾问：架构决策、复杂调试，提供深度洞察，不写代码",
            "traits": ["最强推理", "架构思维", "只读分析", "深度洞察"],
            "recommended": [
                "kiro/claude-opus-4-6-thinking",
                "kiro/claude-opus-4-5-thinking",
                "kiro/claude-opus-4-6",
                "msicu-codex/gpt-5.4",
            ],
            "variant_rec": "xhigh",
        },
        "prometheus": {
            "desc": "战略规划师：访谈模式澄清需求，构建详细执行计划，从不写代码",
            "traits": ["深度思考", "结构化规划", "需求澄清", "策略制定"],
            "recommended": [
                "kiro/claude-opus-4-6-thinking",
                "bytecat-claude-real/claude-opus-4-6",
                "kiro/claude-opus-4-6",
                "kiro/claude-sonnet-4-6-thinking",
            ],
            "variant_rec": "max",
        },
        "metis": {
            "desc": "间隙分析器：在计划最终化前发现遗漏和盲点，防患于未然",
            "traits": ["细致分析", "风险识别", "批判思维", "查漏补缺"],
            "recommended": [
                "kiro/claude-opus-4-6",
                "kiro/claude-sonnet-4-6-thinking",
                "bytecat-claude-real/claude-opus-4-6",
                "kiro/claude-opus-4-6-thinking",
            ],
            "variant_rec": "max",
        },
        "momus": {
            "desc": "代码注释验证器：确保注释规范、准确、生产就绪，提升代码可读性",
            "traits": ["精确写作", "代码理解", "规范审查", "文档质量"],
            "recommended": [
                "kiro/claude-sonnet-4-6",
                "bytecat-claude-real/claude-sonnet-4-6",
                "kiro/claude-sonnet-4-6-thinking",
                "msicu-codex/gpt-5.4",
            ],
            "variant_rec": "high",
        },
        "atlas": {
            "desc": "子编排器：由 /start-work 激活，使用专属子 agent 规划和执行复杂任务",
            "traits": ["任务协调", "子 agent 调度", "执行管理", "上下文维护"],
            "recommended": [
                "volcengine/kimi-k2.5",
                "kiro/claude-opus-4-6",
                "kiro/kimi-k2-thinking",
                "bytecat-claude-real/claude-opus-4-6",
            ],
            "variant_rec": None,
        },
        "sisyphus-junior": {
            "desc": "轻量编排器：sisyphus 的简化版，适用于中等复杂度的任务",
            "traits": ["均衡能力", "中等任务", "快速响应", "代码执行"],
            "recommended": [
                "msicu-codex/gpt-5.4",
                "kiro/claude-sonnet-4-6",
                "kiro/nova-swe",
                "kiro/qwen3-coder-480b",
                "bytecat-claude-real/claude-sonnet-4-6",
            ],
            "variant_rec": "xhigh",
        },
        "librarian": {
            "desc": "文档搜索专家：查询 OSS 代码、跟踪最新库 API，提供最佳实践参考",
            "traits": ["广泛知识", "文档检索", "API 理解", "时效性强"],
            "recommended": [
                "kiro/claude-sonnet-4-6",
                "bytecat-claude-real/claude-opus-4-6",
                "kiro/claude-opus-4-6",
                "kiro/claude-sonnet-4-6-1m",
            ],
            "variant_rec": "max",
        },
        "explore": {
            "desc": "快速代码探索：grep 模式发现、文件扫描，速度优先，不做复杂推理",
            "traits": ["极速响应", "模式搜索", "轻量任务", "低延迟"],
            "recommended": [
                "kiro/claude-haiku-4-5",
                "volcengine/ark-code-latest",
                "volcengine/doubao-seed-2.0-code",
            ],
            "variant_rec": None,
        },
        "multimodal-looker": {
            "desc": "视觉分析 agent：处理 UI/设计稿、截图理解，需要多模态输入能力",
            "traits": ["多模态", "图像理解", "UI 分析", "视觉推理"],
            "recommended": [
                "kiro/claude-sonnet-4-6",
                "kiro/claude-opus-4-6",
                "volcengine/kimi-k2.5",
                "kiro/claude-sonnet-4-6-thinking",
            ],
            "variant_rec": "medium",
        },
        "review-gpt": {
            "desc": "GPT 代码审查员：只读 review，专注 bug、回归风险、边界条件与可维护性",
            "traits": ["代码审查", "只读分析", "回归识别", "风险提示"],
            "recommended": [
                "openai/gpt-5.4",
                "msicu-codex/gpt-5.4",
                "kiro/claude-sonnet-4-6",
                "volcengine/ark-code-latest",
            ],
            "variant_rec": "high",
        },
        "review-opus": {
            "desc": "Opus 代码审查员：只读 review，强调正确性、架构问题与长期维护风险",
            "traits": ["代码审查", "深度推理", "架构洞察", "长期维护"],
            "recommended": [
                "bytecat-claude-real/claude-opus-4-6",
                "kiro/claude-opus-4-6",
                "kiro/claude-opus-4-6-thinking",
                "openai/gpt-5.4",
            ],
            "variant_rec": "xhigh",
        },
    },
    "categories": {
        "quick": {
            "desc": "速度优先：低延迟轻量任务，不需要深度推理，追求即时响应",
            "traits": ["极速响应", "低延迟", "简单任务", "轻量推理"],
            "recommended": [
                "kiro/claude-haiku-4-5",
                "volcengine/ark-code-latest",
                "volcengine/doubao-seed-2.0-code",
            ],
            "variant_rec": None,
        },
        "ultrabrain": {
            "desc": "最强推理：超复杂问题，需要最高级别的智能和扩展思考能力",
            "traits": ["最强推理", "扩展思考", "复杂问题", "高计算成本"],
            "recommended": [
                "kiro/claude-opus-4-6-thinking",
                "kiro/claude-opus-4-5-thinking",
                "msicu-codex/gpt-5.4",
                "kiro/kimi-k2-thinking",
            ],
            "variant_rec": "xhigh",
        },
        "deep": {
            "desc": "深度分析：需要仔细推理的任务，介于 quick 和 ultrabrain 之间",
            "traits": ["深度分析", "细致推理", "中高复杂度", "代码理解"],
            "recommended": [
                "kiro/claude-opus-4-6",
                "kiro/claude-sonnet-4-6-thinking",
                "bytecat-claude-real/claude-opus-4-6",
                "msicu-codex/gpt-5.4",
            ],
            "variant_rec": "medium",
        },
        "artistry": {
            "desc": "创意生成：UI 文案、创意写作、设计方案，注重表达质量和美感",
            "traits": ["创意写作", "语言表达", "美感设计", "风格多样"],
            "recommended": [
                "volcengine/doubao-seed-2.0-pro",
                "kiro/minimax-m2",
                "minimax/MiniMax-M2.7",
                "volcengine/kimi-k2.5",
            ],
            "variant_rec": "high",
        },
        "visual-engineering": {
            "desc": "视觉工程：前端/UI 开发，结合图像理解和代码生成能力",
            "traits": ["多模态", "前端代码", "UI 实现", "图像理解"],
            "recommended": [
                "volcengine/doubao-seed-2.0-code",
                "kiro/claude-sonnet-4-6",
                "volcengine/kimi-k2.5",
                "kiro/claude-opus-4-6",
            ],
            "variant_rec": "high",
        },
        "writing": {
            "desc": "文档写作：技术文档、README、注释生成，注重清晰表达和结构",
            "traits": ["技术写作", "文档结构", "语言流畅", "中英文能力"],
            "recommended": [
                "kiro/minimax-m2",
                "minimax/MiniMax-M2.7",
                "volcengine/doubao-seed-2.0-pro",
                "kiro/claude-sonnet-4-6",
            ],
            "variant_rec": None,
        },
        "unspecified-low": {
            "desc": "默认低档：未明确分类的简单任务兜底，均衡速度与质量",
            "traits": ["通用能力", "均衡性能", "轻量任务", "默认兜底"],
            "recommended": [
                "kiro/claude-sonnet-4-6",
                "bytecat-claude-real/claude-sonnet-4-6",
                "kiro/claude-sonnet-4-5",
            ],
            "variant_rec": None,
        },
        "unspecified-high": {
            "desc": "默认高档：未明确分类的复杂任务兜底，优先质量",
            "traits": ["通用能力", "高质量", "复杂任务", "默认兜底"],
            "recommended": [
                "kiro/claude-opus-4-6",
                "bytecat-claude-real/claude-opus-4-6",
                "kiro/claude-opus-4-5",
            ],
            "variant_rec": "max",
        },
    },
}

AGENTS = list(INFO["agents"].keys())
CATEGORIES = list(INFO["categories"].keys())
VARIANTS = ["(none)", "max", "xhigh", "high", "medium", "low"]

# ─── Color pair IDs ──────────────────────────────────────────────────────────
C_HEADER   = 1   # section headers (cyan)
C_CHANGED  = 2   # modified / OK (green)
C_MODEL    = 3   # model name / detail (yellow)
C_DIM      = 4   # hints / dimmed (white)
C_DANGER   = 5   # danger / clear (red)
C_SEARCH   = 6   # search box (cyan bold)
C_REC      = 7   # recommended marker (magenta)


# ─── JSONC helpers ───────────────────────────────────────────────────────────
def strip_jsonc(text: str) -> str:
    """Remove JSONC comments without touching string contents."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':                                   # string literal
            result.append(ch)
            i += 1
            while i < n:
                c = text[i]
                result.append(c)
                if c == '\\':                           # escape sequence
                    i += 1
                    if i < n:
                        result.append(text[i])
                elif c == '"':
                    break
                i += 1
            i += 1
        elif ch == '/' and i + 1 < n and text[i+1] == '/':   # line comment
            while i < n and text[i] != '\n':
                i += 1
        elif ch == '/' and i + 1 < n and text[i+1] == '*':   # block comment
            i += 2
            while i < n - 1 and not (text[i] == '*' and text[i+1] == '/'):
                i += 1
            i += 2
        else:
            result.append(ch)
            i += 1
    stripped = ''.join(result)
    return re.sub(r',(\s*[}\]])', r'\1', stripped)      # trailing commas


def load_omo() -> dict:
    omo_path = resolve_omo_path()
    if not omo_path.exists():
        return {"agents": {}, "categories": {}}
    try:
        return json.loads(strip_jsonc(omo_path.read_text()))
    except json.JSONDecodeError as e:
        sys.exit(f"Error parsing {omo_path}: {e}")


def save_omo(data: dict) -> None:
    omo_path = resolve_omo_path()
    out: dict = {}
    if "$schema" in data:
        out["$schema"] = data["$schema"]
    out["agents"]     = {k: v for k, v in data.get("agents", {}).items() if v}
    out["categories"] = {k: v for k, v in data.get("categories", {}).items() if v}
    if "_migrations" in data:
        out["_migrations"] = data["_migrations"]
    omo_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")


def load_models() -> list:
    """
    从 `opencode models` 命令获取完整的可用模型列表（包含内置 provider）。
    若命令不可用，回退到解析 opencode.json 中的自定义 provider。
    """
    try:
        proc = subprocess.run(
            ["opencode", "models"],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            models = [
                line.strip()
                for line in proc.stdout.strip().splitlines()
                if line.strip() and "/" in line.strip()
            ]
            if models:
                return sorted(models)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # ── 回退：手动解析 opencode.json ────────────────────────────────────────
    if not OPENCODE_JSON.exists():
        sys.exit("错误: opencode 命令不可用且 opencode.json 不存在，无法获取模型列表。")
    try:
        data = json.loads(OPENCODE_JSON.read_text())
    except json.JSONDecodeError as e:
        sys.exit(f"Error parsing {OPENCODE_JSON}: {e}")
    result = []
    for pname, pdata in data.get("provider", {}).items():
        for mname in pdata.get("models", {}).keys():
            result.append(f"{pname}/{mname}")
    return sorted(result)


def split_model_ref(model: str) -> tuple[str, str]:
    if not model or "/" not in model:
        return "", ""
    provider, model_name = model.split("/", 1)
    return provider.strip(), model_name.strip()


def build_provider_models(all_models: list) -> dict[str, set[str]]:
    provider_models: dict[str, set[str]] = {}
    for model in all_models:
        provider, model_name = split_model_ref(model)
        if provider and model_name:
            provider_models.setdefault(provider, set()).add(model_name)
    return provider_models


def get_info(section: str, name: str) -> dict:
    return INFO.get(section, {}).get(name, {
        "desc": "", "traits": [], "recommended": [], "variant_rec": None
    })


# ─── Safe drawing helpers ─────────────────────────────────────────────────────
def safe_addstr(win, y, x, text, attr=curses.A_NORMAL):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    text = text[:w - x]
    if not text:
        return
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def safe_hline(win, y, x, ch, n):
    h, w = win.getmaxyx()
    if y < 0 or y >= h:
        return
    n = min(n, w - x)
    if n <= 0:
        return
    try:
        win.hline(y, x, ch, n)
    except curses.error:
        pass


def wcswidth(s: str) -> int:
    """返回字符串在终端中的显示列数（CJK 双宽字符计 2 列）。"""
    w = 0
    for c in s:
        cp = ord(c)
        if (0x1100 <= cp <= 0x115F          # Hangul Jamo
                or 0x2E80 <= cp <= 0x303F   # CJK Radicals / Kangxi
                or 0x3040 <= cp <= 0x33FF   # Hiragana/Katakana/CJK Symbols
                or 0x3400 <= cp <= 0x4DBF   # CJK Extension A
                or 0x4E00 <= cp <= 0x9FFF   # CJK Unified Ideographs (主区)
                or 0xA000 <= cp <= 0xA4CF   # Yi
                or 0xAC00 <= cp <= 0xD7AF   # Hangul Syllables
                or 0xF900 <= cp <= 0xFAFF   # CJK Compatibility Ideographs
                or 0xFE10 <= cp <= 0xFE1F   # Vertical Forms
                or 0xFE30 <= cp <= 0xFE4F   # CJK Compatibility Forms
                or 0xFF00 <= cp <= 0xFF60   # Fullwidth
                or 0xFFE0 <= cp <= 0xFFE6   # Fullwidth Signs
                or 0x1B000 <= cp <= 0x1B0FF # Kana Supplement
                or 0x1F300 <= cp <= 0x1FBFF # Emoji / Misc
                or 0x20000 <= cp <= 0x2FA1F):  # CJK Extensions B–F
            w += 2
        else:
            w += 1
    return w


def wrap_text(text: str, max_cols: int) -> list:
    """将文本按 max_cols 列宽换行，返回行列表（CJK 感知）。"""
    lines = []
    line  = ""
    cols  = 0
    for ch in text:
        cw = 2 if wcswidth(ch) == 2 else 1
        if cols + cw > max_cols:
            lines.append(line)
            line = ch
            cols = cw
        else:
            line += ch
            cols += cw
    if line:
        lines.append(line)
    return lines or [""]


# ─── Model Picker ─────────────────────────────────────────────────────────────
def pick_model(stdscr, all_models: list, current: str, section: str, name: str) -> "str | None":
    """
    Full-screen model picker with live search and recommended-models section.
    Returns new model string, "" to clear, or None to cancel.
    """
    info       = get_info(section, name)
    rec_set    = set(info.get("recommended", []))
    rec_list   = [m for m in info.get("recommended", []) if m in all_models]
    other_list = [m for m in all_models if m not in rec_set]

    SPECIAL = ["(keep current)", "(clear model)"]

    search   = ""
    scroll   = 0
    selected = 0

    def build_list():
        q = search.lower()
        if q:
            matched = [m for m in all_models if q in m.lower()]
            matched_rec   = [m for m in rec_list   if q in m.lower()]
            matched_other = [m for m in other_list if q in m.lower()]
        else:
            matched_rec   = rec_list
            matched_other = other_list

        entries = list(SPECIAL)
        if matched_rec:
            entries.append("── 推荐模型 " + "─" * 30)
            for m in matched_rec:
                entries.append(("rec", m))
        if matched_other:
            entries.append("── 全部模型 " + "─" * 30)
            for m in matched_other:
                entries.append(m)
        return entries

    def clamp(lst):
        nonlocal scroll, selected
        n   = len(lst)
        selected = max(0, min(selected, n - 1))
        # skip separators
        while selected < n and isinstance(lst[selected], str) and lst[selected].startswith("──"):
            selected += 1
        selected = max(0, min(selected, n - 1))
        h2, _ = stdscr.getmaxyx()
        vis = max(1, h2 - 8)
        if selected < scroll:
            scroll = selected
        if selected >= scroll + vis:
            scroll = selected - vis + 1
        scroll = max(0, scroll)

    label = f"{section[:-1]}:{name}"

    while True:
        entries = build_list()
        clamp(entries)

        stdscr.erase()
        h, w = stdscr.getmaxyx()
        vis   = max(1, h - 8)

        # ── Header ──
        title = f" Set model for: {label} "
        safe_addstr(stdscr, 0, max(0, (w - len(title)) // 2), title[:w],
                    curses.A_BOLD | curses.A_REVERSE)
        cur_line = f" Current: {current or '(not set)'}"
        safe_addstr(stdscr, 1, 0, cur_line[:w], curses.color_pair(C_MODEL))

        # ── Info bar ──
        desc = info.get("desc", "")
        if desc:
            safe_addstr(stdscr, 2, 0, f" {desc}"[:w], curses.color_pair(C_DIM))
        traits = info.get("traits", [])
        if traits:
            trait_str = " · ".join(traits)
            safe_addstr(stdscr, 3, 0, f" [{trait_str}]"[:w],
                        curses.color_pair(C_REC))

        # ── Search box ──
        safe_hline(stdscr, 4, 0, curses.ACS_HLINE, w)
        prompt = " 搜索: "
        safe_addstr(stdscr, 5, 0, prompt, curses.color_pair(C_SEARCH) | curses.A_BOLD)
        safe_addstr(stdscr, 5, len(prompt), (search + "▌")[:w - len(prompt) - 1],
                    curses.color_pair(C_SEARCH))
        safe_hline(stdscr, 6, 0, curses.ACS_HLINE, w)

        # ── List ──
        for i, entry in enumerate(entries[scroll:scroll + vis]):
            idx   = i + scroll
            y     = i + 7
            is_sel = idx == selected

            if isinstance(entry, str) and entry.startswith("──"):
                safe_addstr(stdscr, y, 0, (" " + entry)[:w],
                            curses.color_pair(C_HEADER) | curses.A_DIM)
                continue

            is_rec  = isinstance(entry, tuple)
            model   = entry[1] if is_rec else entry
            is_cur  = model == current

            if entry == "(keep current)":
                attr = curses.A_REVERSE if is_sel else curses.color_pair(C_DIM)
                prefix = "  "
            elif entry == "(clear model)":
                attr = curses.A_REVERSE if is_sel else curses.color_pair(C_DANGER)
                prefix = "  "
            elif is_rec:
                attr = (curses.A_REVERSE | curses.A_BOLD) if is_sel else curses.color_pair(C_REC)
                prefix = "★ "
            else:
                attr = (curses.A_REVERSE | curses.A_BOLD) if (is_sel and is_cur) else \
                       (curses.A_REVERSE if is_sel else
                        (curses.color_pair(C_CHANGED) | curses.A_BOLD if is_cur else curses.A_NORMAL))
                prefix = "  "

            arrow = "▶ " if is_sel else "  "
            line  = f"{arrow}{prefix}{model}"
            safe_addstr(stdscr, y, 0, line.ljust(w)[:w], attr)

        # ── Footer ──
        total = sum(1 for e in entries if not (isinstance(e, str) and e.startswith("──")))
        safe_hline(stdscr, h - 2, 0, curses.ACS_HLINE, w)
        footer = (f" ↑↓/jk:移动  Enter:选择  Backspace:清除搜索  ESC/q:取消"
                  f"  [{total} 模型]")
        safe_addstr(stdscr, h - 1, 0, footer[:w - 1], curses.color_pair(C_DIM))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            selected -= 1
        elif key in (curses.KEY_DOWN, ord('j')):
            selected += 1
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - vis)
        elif key == curses.KEY_NPAGE:
            selected = min(len(entries) - 1, selected + vis)
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            entry = entries[selected]
            if isinstance(entry, tuple):
                entry = entry[1]
            if entry == "(keep current)":
                return None
            elif entry == "(clear model)":
                return ""
            elif isinstance(entry, str) and not entry.startswith("──"):
                return entry
        elif key in (ord('q'), 27):
            return None
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            search   = search[:-1]
            selected = 0
            scroll   = 0
        elif 32 <= key <= 126:
            search  += chr(key)
            selected = 0
            scroll   = 0


# ─── Variant Picker ───────────────────────────────────────────────────────────
def pick_variant(stdscr, current: str, section: str, name: str) -> "str | None":
    """Returns new variant string, "" to clear, or None to cancel."""
    info    = get_info(section, name)
    rec_var = info.get("variant_rec")
    selected = 0
    for i, v in enumerate(VARIANTS):
        if v == current or (current == "" and v == "(none)"):
            selected = i
            break
    label = f"{section[:-1]}:{name}"

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        title = f" Set variant for: {label} "
        safe_addstr(stdscr, 0, max(0, (w - len(title)) // 2), title[:w],
                    curses.A_BOLD | curses.A_REVERSE)
        safe_addstr(stdscr, 1, 0, f" Current: {current or '(none)'}"[:w],
                    curses.color_pair(C_MODEL))
        if rec_var:
            safe_addstr(stdscr, 2, 0, f" 推荐: {rec_var}"[:w],
                        curses.color_pair(C_REC))
        safe_hline(stdscr, 3, 0, curses.ACS_HLINE, w)

        for i, v in enumerate(VARIANTS):
            is_sel  = i == selected
            is_rec  = v == rec_var
            is_cur  = v == current or (current == "" and v == "(none)")

            if is_sel:
                attr = curses.A_REVERSE | curses.A_BOLD
            elif is_rec:
                attr = curses.color_pair(C_REC) | curses.A_BOLD
            elif is_cur:
                attr = curses.color_pair(C_CHANGED) | curses.A_BOLD
            elif v == "(none)":
                attr = curses.color_pair(C_DIM)
            else:
                attr = curses.A_NORMAL

            prefix = "▶ " if is_sel else "  "
            rec_tag = " ★推荐" if is_rec and not is_sel else ""
            cur_tag = " ✓当前" if is_cur and not is_sel else ""
            line    = f"{prefix}{v}{rec_tag}{cur_tag}"
            safe_addstr(stdscr, i + 4, 0, line.ljust(w)[:w], attr)

        safe_hline(stdscr, h - 2, 0, curses.ACS_HLINE, w)
        safe_addstr(stdscr, h - 1, 0,
                    " ↑↓/jk:移动  Enter:选择  ESC/q:取消 "[:w - 1],
                    curses.color_pair(C_DIM))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')) and selected > 0:
            selected -= 1
        elif key in (curses.KEY_DOWN, ord('j')) and selected < len(VARIANTS) - 1:
            selected += 1
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            v = VARIANTS[selected]
            return "" if v == "(none)" else v
        elif key in (ord('q'), 27):
            return None


# ─── Info overlay (press ?) ───────────────────────────────────────────────────
def show_info(stdscr, section: str, name: str, all_models: list):
    """Show a scrollable info popup for the selected agent/category."""
    info = get_info(section, name)
    rec_in_opencode = [m for m in info.get("recommended", []) if m in all_models]
    rec_missing     = [m for m in info.get("recommended", []) if m not in all_models]

    lines = []
    lines.append(f"{'─' * 60}")
    label = f"{section[:-1].upper()}: {name}"
    lines.append(f"  {label}")
    lines.append(f"{'─' * 60}")
    lines.append("")
    lines.append(f"  描述: {info.get('desc', '—')}")
    lines.append("")
    traits = info.get("traits", [])
    if traits:
        lines.append(f"  特性需求:")
        for t in traits:
            lines.append(f"    · {t}")
    lines.append("")
    lines.append(f"  推荐模型 (★ 可用 / ✗ 不在 opencode.json):")
    for m in info.get("recommended", []):
        if m in all_models:
            lines.append(f"    ★ {m}")
        else:
            lines.append(f"    ✗ {m}  ← 需要在 opencode.json 中添加 provider")
    rec_var = info.get("variant_rec")
    lines.append("")
    lines.append(f"  推荐 variant: {rec_var or '(不设置)'}")
    lines.append("")
    lines.append(f"{'─' * 60}")
    lines.append("  按任意键关闭")

    scroll = 0
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        vis   = h - 2
        title = f" 信息: {name} "
        safe_addstr(stdscr, 0, max(0, (w - len(title)) // 2), title[:w],
                    curses.A_BOLD | curses.A_REVERSE)
        for i, line in enumerate(lines[scroll:scroll + vis - 1]):
            y = i + 1
            attr = curses.A_NORMAL
            if line.startswith("  ★"):
                attr = curses.color_pair(C_REC) | curses.A_BOLD
            elif line.startswith("  ✗"):
                attr = curses.color_pair(C_DANGER)
            elif line.startswith("  描述") or line.startswith("  特性") or \
                 line.startswith("  推荐"):
                attr = curses.color_pair(C_MODEL) | curses.A_BOLD
            elif line.startswith("──") or line.startswith("  ─"):
                attr = curses.color_pair(C_HEADER)
            elif line.startswith("  按任意键"):
                attr = curses.color_pair(C_DIM)
            safe_addstr(stdscr, y, 0, line[:w], attr)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            scroll = max(0, scroll - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            scroll = min(max(0, len(lines) - vis), scroll + 1)
        else:
            break


# ─── Dialogs ─────────────────────────────────────────────────────────────────
def confirm(stdscr, message: str) -> bool:
    h, w = stdscr.getmaxyx()
    msg = f" {message} [y/N] "
    safe_addstr(stdscr, h - 1, 0, msg.ljust(w - 1)[:w - 1],
                curses.A_BOLD | curses.A_REVERSE)
    stdscr.refresh()
    return stdscr.getch() in (ord('y'), ord('Y'))


def flash(stdscr, message: str, color: int, ms: int = 900):
    h, w = stdscr.getmaxyx()
    msg = f" {message} "
    safe_addstr(stdscr, h - 1, max(0, (w - len(msg)) // 2), msg[:w - 1],
                curses.A_BOLD | curses.color_pair(color) | curses.A_REVERSE)
    stdscr.refresh()
    curses.napms(ms)


# ─── Config helpers ───────────────────────────────────────────────────────────
def get_cfg(config: dict, section: str, name: str) -> dict:
    return config.get(section, {}).get(name, {})


def set_cfg(config: dict, section: str, name: str, key: str, value):
    config.setdefault(section, {}).setdefault(name, {})[key] = value


def del_cfg_key(config: dict, section: str, name: str, key: str):
    config.get(section, {}).get(name, {}).pop(key, None)
    if not config.get(section, {}).get(name):
        config.get(section, {}).pop(name, None)


def iter_config_models(config: dict):
    for section in ("agents", "categories"):
        for name, cfg in config.get(section, {}).items():
            model = cfg.get("model", "")
            provider, model_name = split_model_ref(model)
            if provider and model_name:
                yield section, name, provider, model_name


def get_source_provider_choices(config: dict, provider_models: dict[str, set[str]]) -> list[dict]:
    used: dict[str, list[str]] = {}
    for _, _, provider, model_name in iter_config_models(config):
        used.setdefault(provider, []).append(model_name)

    choices = []
    for provider, names in sorted(used.items()):
        targets = 0
        max_replaceable = 0
        unique_names = set(names)
        for other, other_models in provider_models.items():
            if other == provider:
                continue
            replaceable = sum(1 for model_name in names if model_name in other_models)
            if replaceable:
                targets += 1
                max_replaceable = max(max_replaceable, replaceable)
        if targets:
            choices.append({
                "value": provider,
                "label": (
                    f"{provider}  [{len(names)} 项配置, {len(unique_names)} 个模型名, "
                    f"可切到 {targets} 个 provider]"
                ),
                "detail": f"最多可一次替换 {max_replaceable} 项配置",
            })
    return choices


def get_target_provider_choices(
    config: dict,
    source_provider: str,
    provider_models: dict[str, set[str]],
) -> list[dict]:
    source_entries = [
        model_name
        for _, _, provider, model_name in iter_config_models(config)
        if provider == source_provider
    ]
    if not source_entries:
        return []

    choices = []
    source_total = len(source_entries)
    unique_source = sorted(set(source_entries))
    for provider, models in sorted(provider_models.items()):
        if provider == source_provider:
            continue
        matched_entries = [model_name for model_name in source_entries if model_name in models]
        if not matched_entries:
            continue
        matched_unique = sorted(set(matched_entries))
        missing_unique = [model_name for model_name in unique_source if model_name not in models]
        sample = ", ".join(matched_unique[:3])
        if len(matched_unique) > 3:
            sample += ", ..."
        detail = f"将替换 {len(matched_entries)}/{source_total} 项"
        if sample:
            detail += f"；匹配: {sample}"
        if missing_unique:
            detail += f"；缺少 {len(missing_unique)} 个同名模型"
        choices.append({
            "value": provider,
            "label": (
                f"{provider}  [可替换 {len(matched_entries)}/{source_total} 项, "
                f"{len(matched_unique)} 个同名模型]"
            ),
            "detail": detail,
            "replaceable": len(matched_entries),
        })

    choices.sort(key=lambda item: (-item["replaceable"], item["value"]))
    return choices


def batch_replace_provider(
    config: dict,
    source_provider: str,
    target_provider: str,
    provider_models: dict[str, set[str]],
) -> int:
    target_models = provider_models.get(target_provider, set())
    replaced = 0
    for section in ("agents", "categories"):
        for cfg in config.get(section, {}).values():
            provider, model_name = split_model_ref(cfg.get("model", ""))
            if provider == source_provider and model_name in target_models:
                cfg["model"] = f"{target_provider}/{model_name}"
                replaced += 1
    return replaced


def pick_menu(stdscr, title: str, subtitle: str, options: list[dict], footer: str) -> "str | None":
    if not options:
        return None

    selected = 0
    scroll = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        vis = max(1, h - 7)

        safe_addstr(stdscr, 0, max(0, (w - len(title)) // 2), title[:w],
                    curses.A_BOLD | curses.A_REVERSE)
        if subtitle:
            safe_addstr(stdscr, 1, 0, f" {subtitle}"[:w], curses.color_pair(C_DIM))
        safe_hline(stdscr, 2, 0, curses.ACS_HLINE, w)

        if selected < scroll:
            scroll = selected
        elif selected >= scroll + vis:
            scroll = selected - vis + 1

        for i, option in enumerate(options[scroll:scroll + vis]):
            idx = scroll + i
            y = i + 3
            prefix = "▶ " if idx == selected else "  "
            attr = curses.A_REVERSE | curses.A_BOLD if idx == selected else curses.A_NORMAL
            safe_addstr(stdscr, y, 0, f"{prefix}{option['label']}".ljust(w)[:w], attr)

        detail = options[selected].get("detail", "")
        safe_hline(stdscr, h - 3, 0, curses.ACS_HLINE, w)
        if detail:
            safe_addstr(stdscr, h - 2, 0, f" {detail}"[:w - 1], curses.color_pair(C_MODEL))
        safe_addstr(stdscr, h - 1, 0, footer[:w - 1], curses.color_pair(C_DIM))
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')) and selected > 0:
            selected -= 1
        elif key in (curses.KEY_DOWN, ord('j')) and selected < len(options) - 1:
            selected += 1
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - vis)
        elif key == curses.KEY_NPAGE:
            selected = min(len(options) - 1, selected + vis)
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return options[selected]["value"]
        elif key in (ord('q'), 27):
            return None


def run_batch_provider_replace(stdscr, config: dict, all_models: list) -> int:
    provider_models = build_provider_models(all_models)
    source_choices = get_source_provider_choices(config, provider_models)
    if not source_choices:
        flash(stdscr, "当前没有可批量切换 provider 的模型配置", C_DIM, ms=1200)
        return 0

    source_provider = pick_menu(
        stdscr,
        " Select source provider ",
        "选择当前正在使用、准备被统一替换的 provider",
        source_choices,
        " ↑↓/jk:移动  Enter:选择  ESC/q:取消 ",
    )
    if not source_provider:
        return 0

    target_choices = get_target_provider_choices(config, source_provider, provider_models)
    if not target_choices:
        flash(stdscr, "目标 provider 中没有找到可替换的同名模型", C_DANGER, ms=1200)
        return 0

    target_provider = pick_menu(
        stdscr,
        " Select target provider ",
        f"将 {source_provider} 的同名模型批量切到哪个 provider",
        target_choices,
        " ↑↓/jk:移动  Enter:选择  ESC/q:取消 ",
    )
    if not target_provider:
        return 0

    replaceable = next(
        item["replaceable"] for item in target_choices if item["value"] == target_provider
    )
    if not confirm(
        stdscr,
        f"把 {replaceable} 项 {source_provider} 模型批量替换为 {target_provider}？",
    ):
        return 0

    replaced = batch_replace_provider(config, source_provider, target_provider, provider_models)
    if replaced:
        flash(stdscr, f"已批量替换 {replaced} 项模型 provider", C_CHANGED, ms=1200)
    return replaced


# ─── Main TUI ────────────────────────────────────────────────────────────────
def build_items():
    items = [("header", "── Agents ──", None)]
    for a in AGENTS:
        items.append(("agent", a, "agents"))
    items.append(("header", "── Categories ──", None))
    for c in CATEGORIES:
        items.append(("category", c, "categories"))
    return items


def main(stdscr):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_HEADER, curses.COLOR_CYAN,    -1)
    curses.init_pair(C_CHANGED, curses.COLOR_GREEN,  -1)
    curses.init_pair(C_MODEL,  curses.COLOR_YELLOW,  -1)
    curses.init_pair(C_DIM,    curses.COLOR_WHITE,   -1)
    curses.init_pair(C_DANGER, curses.COLOR_RED,     -1)
    curses.init_pair(C_SEARCH, curses.COLOR_CYAN,    -1)
    curses.init_pair(C_REC,    curses.COLOR_MAGENTA, -1)
    curses.curs_set(0)

    all_models = load_models()

    config   = load_omo()
    original = deepcopy(config)
    items    = build_items()
    sel_list = [i for i, it in enumerate(items) if it[0] != "header"]
    sel_pos  = 0
    scroll   = 0
    modified = False

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        # 底部保留 6 行：divider(1) + name-header(1) + desc-line1(1)
        #               + desc-line2/traits(1) + detail(1) + footer(1)
        content_h = h - 7

        cur_idx                    = sel_list[sel_pos]
        _, cur_name, cur_section   = items[cur_idx]

        # Scroll viewport
        if cur_idx < scroll:
            scroll = cur_idx
        elif cur_idx >= scroll + content_h:
            scroll = cur_idx - content_h + 1

        # ── Title ────────────────────────────────────────────────────────────
        title = " omo-model-set — oh-my-openagent 模型配置 "
        safe_addstr(stdscr, 0, max(0, (w - len(title)) // 2), title[:w],
                    curses.A_BOLD | curses.A_REVERSE)

        # ── Item list ────────────────────────────────────────────────────────
        row = 1
        for i, (kind, name, section) in enumerate(items[scroll:scroll + content_h + 3]):
            real_i = i + scroll
            if row >= h - 6:
                break
            if kind == "header":
                safe_addstr(stdscr, row, 1, name[:w - 2],
                            curses.color_pair(C_HEADER) | curses.A_BOLD)
                row += 1
                continue

            is_sel  = real_i == cur_idx
            cfg     = get_cfg(config,   section, name)
            orig    = get_cfg(original, section, name)
            changed = cfg != orig
            model   = cfg.get("model",   "")
            variant = cfg.get("variant", "")
            info_i  = get_info(section, name)
            is_rec  = model in info_i.get("recommended", [])
            not_in  = model and model not in all_models

            # Indicators
            chg_mark = "* " if changed else "  "
            rec_mark = "★" if is_rec else ("!" if not_in else " ")
            arrow    = "▶ " if is_sel else "  "

            # Layout: indicator(2) + arrow(2) + name(22) + model(42) + variant
            name_col    = f"{name:<22}"
            model_disp  = model or "—"
            model_col   = f"{rec_mark} {model_disp:<39}"
            variant_col = variant or "—"

            line = f"{chg_mark}{arrow}{name_col}{model_col}  {variant_col}"
            if len(line) > w:
                line = line[:w - 3] + "..."

            if is_sel:
                attr = curses.A_REVERSE | curses.A_BOLD
            elif not_in:
                attr = curses.color_pair(C_DANGER)
            elif changed:
                attr = curses.color_pair(C_CHANGED)
            else:
                attr = curses.A_NORMAL

            safe_addstr(stdscr, row, 0, line.ljust(w)[:w], attr)
            row += 1

        # ── Bottom info area ─────────────────────────────────────────────────
        info_cur = get_info(cur_section, cur_name)
        cfg_cur  = get_cfg(config, cur_section, cur_name)

        safe_hline(stdscr, h - 6, 0, curses.ACS_HLINE, w)

        # h-5: name header + traits
        traits_str = "  ".join(info_cur.get("traits", []))
        header_left  = f" {cur_section[:-1].upper()} {cur_name}"
        header_right = f"[{traits_str}]" if traits_str else ""
        gap = w - wcswidth(header_left) - wcswidth(header_right) - 1
        if gap >= 2:
            header_line = header_left + " " * gap + header_right
        else:
            header_line = header_left
        safe_addstr(stdscr, h - 5, 0, header_line[:w], curses.color_pair(C_MODEL) | curses.A_BOLD)

        # h-4: description line 1（换行到 h-3）
        desc       = info_cur.get("desc", "")
        desc_lines = wrap_text(" " + desc, w - 1)
        safe_addstr(stdscr, h - 4, 0,
                    (desc_lines[0] if desc_lines else "")[:w],
                    curses.color_pair(C_DIM))

        # h-3: desc 第二行（若有），否则显示当前 model / variant
        cur_model   = cfg_cur.get("model", "—")
        cur_variant = cfg_cur.get("variant", "—")
        if len(desc_lines) > 1:
            safe_addstr(stdscr, h - 3, 0, desc_lines[1][:w],
                        curses.color_pair(C_DIM))
        else:
            cfg_line = f" model: {cur_model}   variant: {cur_variant}"
            safe_addstr(stdscr, h - 3, 0, cfg_line[:w - 1],
                        curses.color_pair(C_DIM))

        # h-2: 推荐模型列表 — 按终端宽度尽量多显示
        rec_models = [m for m in info_cur.get("recommended", []) if m in all_models]
        prefix     = " 推荐: "
        budget     = w - 1 - wcswidth(prefix)
        parts: list = []
        used_budget = 0
        for m in rec_models:
            sep    = "  " if parts else ""
            item   = f"★{m}"
            needed = wcswidth(sep + item)
            remaining_after = len(rec_models) - len(parts) - 1
            # 用与最终拼接完全一致的后缀格式来预留宽度
            suffix = f"  [+{remaining_after}]" if remaining_after > 0 else ""
            if used_budget + needed + wcswidth(suffix) <= budget:
                parts.append(item)
                used_budget += needed
            else:
                break
        remaining = len(rec_models) - len(parts)
        rec_line  = prefix + "  ".join(parts)
        if remaining > 0:
            rec_line += f"  [+{remaining}]"
        safe_addstr(stdscr, h - 2, 0, rec_line[:w - 1],
                    curses.color_pair(C_REC))

        # ── Footer ───────────────────────────────────────────────────────────
        mod_tag     = "  [已修改 — s保存]" if modified else ""
        footer      = (
            f" ↑↓/jk:移动  m:改模型  v:改variant  b:批量换provider  ?:详情"
            f"  s:保存  r:重置  q:退出{mod_tag} "
        )
        footer_attr = (curses.color_pair(C_CHANGED) | curses.A_BOLD) if modified \
                      else curses.color_pair(C_DIM)
        safe_addstr(stdscr, h - 1, 0, footer[:w - 1], footer_attr)

        stdscr.refresh()

        # ── Input ────────────────────────────────────────────────────────────
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord('k')) and sel_pos > 0:
            sel_pos -= 1
        elif key in (curses.KEY_DOWN, ord('j')) and sel_pos < len(sel_list) - 1:
            sel_pos += 1
        elif key == curses.KEY_PPAGE:
            sel_pos = max(0, sel_pos - 10)
        elif key == curses.KEY_NPAGE:
            sel_pos = min(len(sel_list) - 1, sel_pos + 10)
        elif key == ord('g'):
            sel_pos = 0
        elif key == ord('G'):
            sel_pos = len(sel_list) - 1

        elif key in (ord('m'), curses.KEY_ENTER, ord('\n'), ord('\r')):
            cfg_cur = get_cfg(config, cur_section, cur_name)
            result  = pick_model(stdscr, all_models, cfg_cur.get("model", ""),
                                 cur_section, cur_name)
            if result is not None:
                if result == "":
                    del_cfg_key(config, cur_section, cur_name, "model")
                else:
                    set_cfg(config, cur_section, cur_name, "model", result)
                modified = config != original

        elif key == ord('v'):
            cfg_cur = get_cfg(config, cur_section, cur_name)
            result  = pick_variant(stdscr, cfg_cur.get("variant", ""),
                                   cur_section, cur_name)
            if result is not None:
                if result == "":
                    del_cfg_key(config, cur_section, cur_name, "variant")
                else:
                    set_cfg(config, cur_section, cur_name, "variant", result)
                modified = config != original

        elif key == ord('b'):
            replaced = run_batch_provider_replace(stdscr, config, all_models)
            if replaced:
                modified = config != original

        elif key == ord('?'):
            show_info(stdscr, cur_section, cur_name, all_models)

        elif key == ord('s'):
            save_omo(config)
            original = deepcopy(config)
            modified = False
            flash(stdscr, f"已保存 → {resolve_omo_path()}", C_CHANGED)

        elif key == ord('r'):
            config   = deepcopy(original)
            modified = False
            flash(stdscr, "已重置为上次保存状态", C_DIM)

        elif key in (ord('q'), 27):
            if modified:
                if confirm(stdscr, "有未保存修改，保存后退出？"):
                    save_omo(config)
                    flash(stdscr, f"已保存 → {resolve_omo_path()}", C_CHANGED)
            break


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        has_opencode = subprocess.run(
            ["opencode", "--version"], capture_output=True, timeout=5
        ).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        has_opencode = False

    if not has_opencode and not OPENCODE_JSON.exists():
        sys.exit("错误: opencode 命令不可用且 opencode.json 不存在。")
    omo_path = resolve_omo_path()
    if not omo_path.exists():
        print(f"提示: {omo_path} 不存在，保存时将自动创建。")
    curses.wrapper(main)
