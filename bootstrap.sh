#!/usr/bin/env bash
# 读后无书 · 远程一键安装
# 用法：在终端或 agent shell 里跑这一行：
#
#   curl -fsSL https://raw.githubusercontent.com/Piersli/talk-without-book/main/bootstrap.sh | bash
#
# 或者直接告诉 agent："请把 https://github.com/Piersli/talk-without-book 装上"

set -euo pipefail

# ── 配置 ──────────────────────────────────────────
REPO_URL="https://github.com/Piersli/talk-without-book.git"
INSTALL_DIR="${TWB_INSTALL_DIR:-$HOME/.talk-without-book}"
BRANCH="${TWB_BRANCH:-main}"

G='\033[32m'; Y='\033[33m'; B='\033[34m'; R='\033[31m'; N='\033[0m'

echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "${B}  读后无书 · talk without book — 远程安装  ${N}"
echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo

# ── 检查依赖 ──────────────────────────────────────
command -v git >/dev/null 2>&1 || { echo -e "${R}✗ 缺 git${N}"; exit 1; }

# ── 拉代码 ──────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo -e "${G}✓${N} 已存在 $INSTALL_DIR — 拉取最新代码"
  git -C "$INSTALL_DIR" fetch --quiet
  git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" --quiet
else
  echo -e "${B}↓${N} Clone 到 $INSTALL_DIR"
  git clone --quiet --depth=1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

echo

# ── 跑 install.sh ────────────────────────────────
bash "$INSTALL_DIR/install.sh"

echo
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "${G}  下一步：跟你的 agent 说"今天的道"  ${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo
echo "速查："
echo "  调用三个 skill 的触发词：cat $INSTALL_DIR/TRIGGERS.md"
echo "  方法论：               cat $INSTALL_DIR/METHODOLOGY.md"
echo "  更新到最新：           bash $INSTALL_DIR/bootstrap.sh"
