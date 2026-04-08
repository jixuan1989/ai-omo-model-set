#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
INSTALL_NAME="omo-set"
INSTALL_PATH="$INSTALL_DIR/$INSTALL_NAME"

if [[ ! -e "$INSTALL_PATH" && ! -L "$INSTALL_PATH" ]]; then
  echo "未找到已安装的 $INSTALL_PATH，无需卸载。"
  exit 0
fi

rm -f "$INSTALL_PATH"
echo "✓ 已卸载: $INSTALL_PATH"
