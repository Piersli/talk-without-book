#!/usr/bin/env bash
# 读后无书 · 一键安装
# 自动检测 Claude Code / Hermes Agent / OpenClaw，把三个 skill 部署到所有发现的平台。

set -euo pipefail

# ── 路径 ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"

# 三个 skill 的目录名
SKILLS=(twb-extract twb-structure twb-daily)

# 平台 → 安装目录（按 agentskills.io 标准）
declare -a PLATFORMS=(
  "claude:$HOME/.claude/skills"
  "hermes:$HOME/.hermes/skills"
  "openclaw:$HOME/.openclaw/skills"
)

# ── 颜色 ──────────────────────────────────────────
G='\033[32m'; Y='\033[33m'; B='\033[34m'; R='\033[31m'; N='\033[0m'

# ── 检查 ──────────────────────────────────────────
echo -e "${B}📦 读后无书 · 多平台一键安装${N}"
echo

[ -d "$SKILLS_SRC" ] || { echo -e "${R}✗ 找不到 $SKILLS_SRC${N}"; exit 1; }

# 检测哪些平台已安装
DETECTED=()
for entry in "${PLATFORMS[@]}"; do
  IFS=':' read -r name parent <<< "$entry"
  parent_root="${parent%/skills}"
  if [ -d "$parent_root" ]; then
    DETECTED+=("$entry")
    echo -e "${G}✓${N} 发现 $name 在 $parent_root"
  fi
done

# 如果一个都没发现，问用户要不要强制装 Claude Code 位置
if [ "${#DETECTED[@]}" -eq 0 ]; then
  echo -e "${Y}⚠️  没检测到任何已安装的 agent 平台（Claude/Hermes/OpenClaw）${N}"
  echo -ne "${Y}? 仍要装到默认的 ~/.claude/skills/？[y/N] ${N}"
  read -r ans
  if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    DETECTED=("claude:$HOME/.claude/skills")
  else
    echo "未安装。退出。"
    exit 0
  fi
fi

echo

# ── 安装 ──────────────────────────────────────────
INSTALL_MODE="symlink"  # 默认用 symlink（开发者友好）

# Hermes 和 OpenClaw 可能更想要 copy（manifest 校验）；
# 但 symlink 也是合法的。这里保守起见三家都 symlink，让用户必要时改成 copy。

for entry in "${DETECTED[@]}"; do
  IFS=':' read -r platform dst_dir <<< "$entry"
  echo -e "${B}── 部署到 $platform ($dst_dir) ──${N}"

  mkdir -p "$dst_dir"

  for skill in "${SKILLS[@]}"; do
    src="$SKILLS_SRC/$skill"
    dst="$dst_dir/$skill"

    [ -d "$src" ] || { echo -e "${Y}⚠️  跳过 $skill（源不存在）${N}"; continue; }

    if [ -e "$dst" ] || [ -L "$dst" ]; then
      if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        echo -e "  ${G}✓${N} $skill  已存在（同源符号链接），跳过"
        continue
      fi
      echo -ne "  ${Y}? $skill 已存在 ($dst)，覆盖？[y/N] ${N}"
      read -r ans
      if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
        echo "    跳过"
        continue
      fi
      rm -rf "$dst"
    fi

    ln -s "$src" "$dst"
    echo -e "  ${G}✓${N} $skill  → $dst"
  done

  echo
done

# ── 收尾 ──────────────────────────────────────────
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "${G}✨ 读后无书 · 安装完成${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo
echo "下一步："
echo "  1. 重启 agent 会话（Claude Code / Hermes / OpenClaw）"
echo "  2. 说：今天的道  → 触发 twb-daily"
echo
echo "查看方法论：cat $SCRIPT_DIR/METHODOLOGY.md"
echo "查看安装详情：cat $SCRIPT_DIR/INSTALL.md"
echo
echo "如果还没有任何 \"道\"，先用 twb-extract 拆一本书："
echo "  在 agent 里说：拆解 /path/to/your-book.md"
