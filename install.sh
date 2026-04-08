#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_SRC="$SCRIPT_DIR/omo-model-set.py"
INSTALL_DIR="${HOME}/.local/bin"
INSTALL_NAME="omo-set"
INSTALL_PATH="$INSTALL_DIR/$INSTALL_NAME"

# ── 检查 Python ───────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "错误: 未找到 python3，请先安装 Python 3.8+。" >&2
  exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 8) ]]; then
  echo "错误: 需要 Python 3.8+，当前为 $PY_VER。" >&2
  exit 1
fi

# ── 检查源文件 ────────────────────────────────────────────────────────────────
if [[ ! -f "$SCRIPT_SRC" ]]; then
  echo "错误: 找不到 $SCRIPT_SRC" >&2
  exit 1
fi

# ── 创建安装目录 ──────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"

# ── 安装（创建指向源文件的符号链接，更新时无需重新安装）────────────────────────
if [[ -L "$INSTALL_PATH" ]]; then
  echo "更新已有链接: $INSTALL_PATH"
  ln -sf "$SCRIPT_SRC" "$INSTALL_PATH"
elif [[ -f "$INSTALL_PATH" ]]; then
  echo "替换已有文件: $INSTALL_PATH"
  ln -sf "$SCRIPT_SRC" "$INSTALL_PATH"
else
  ln -s "$SCRIPT_SRC" "$INSTALL_PATH"
fi

chmod +x "$SCRIPT_SRC"

# ── 检查 PATH ─────────────────────────────────────────────────────────────────
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$INSTALL_DIR"; then
  echo ""
  echo "⚠️  $INSTALL_DIR 不在 PATH 中，请将以下内容添加到你的 shell 配置文件："
  echo ""
  echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo ""
  echo "    ~/.zshrc / ~/.bashrc / ~/.config/fish/config.fish 等"
fi

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo "✓ 安装完成: $INSTALL_PATH -> $SCRIPT_SRC"
echo ""
echo "使用方法:"
echo "  omo-set          启动交互式模型配置 TUI"
echo "  omo-set --help   查看帮助（若已实现）"
echo ""
