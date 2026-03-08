#!/usr/bin/env bash
set -euo pipefail

# Test suite for setup.sh
# Verifies: installation, idempotency, uninstallation, mobile generation

SCRIPT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEST_HOME="$(mktemp -d)"
PASS=0
FAIL=0

# ─── Colors ───────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

assert() {
    local description="$1"
    shift
    if "$@" 2>/dev/null; then
        echo -e "${GREEN}  PASS${NC} $description"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}  FAIL${NC} $description"
        FAIL=$((FAIL + 1))
    fi
}

assert_not() {
    local description="$1"
    shift
    if ! "$@" 2>/dev/null; then
        echo -e "${GREEN}  PASS${NC} $description"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}  FAIL${NC} $description"
        FAIL=$((FAIL + 1))
    fi
}

cleanup() {
    rm -rf "$TEST_HOME"
}
trap cleanup EXIT

echo "═══════════════════════════════════════════"
echo " Claude Setup — Test Suite"
echo " Test home: $TEST_HOME"
echo "═══════════════════════════════════════════"
echo ""

# ─── Test 1: Fresh Install ────────────────────────────────
echo "▸ Test 1: Fresh install"

bash "$SCRIPT_DIR/setup.sh" --install --claude-home "$TEST_HOME" 2>&1 | tail -3

# Rules should exist (flattened) — use -e not -L for Windows junction compat
assert "agents.md exists"        test -e "$TEST_HOME/rules/agents.md"
assert "coding-style.md exists"  test -e "$TEST_HOME/rules/coding-style.md"
assert "git-workflow.md exists"  test -e "$TEST_HOME/rules/git-workflow.md"
assert "development-workflow.md exists" test -e "$TEST_HOME/rules/development-workflow.md"
assert "patterns.md exists"      test -e "$TEST_HOME/rules/patterns.md"
assert "security.md exists"      test -e "$TEST_HOME/rules/security.md"
assert "testing.md exists"       test -e "$TEST_HOME/rules/testing.md"
assert "hooks.md exists"         test -e "$TEST_HOME/rules/hooks.md"
assert "performance.md exists"   test -e "$TEST_HOME/rules/performance.md"

# Skills should exist (flattened)
assert "eddie-voice skill exists" test -e "$TEST_HOME/skills/eddie-voice"
assert "open-pr skill exists"     test -e "$TEST_HOME/skills/open-pr"
assert "update-pr skill exists"   test -e "$TEST_HOME/skills/update-pr"
assert "pr-diagrams skill exists" test -e "$TEST_HOME/skills/pr-diagrams"
assert "dotnet skill exists"      test -e "$TEST_HOME/skills/dotnet"

# Content should be readable through the links
assert "agents.md readable"       test -r "$TEST_HOME/rules/agents.md"
assert "eddie-voice SKILL.md readable" test -r "$TEST_HOME/skills/eddie-voice/SKILL.md"
assert "open-pr SKILL.md readable"     test -r "$TEST_HOME/skills/open-pr/SKILL.md"

# Settings should exist and have expected keys
assert "settings.json exists"     test -f "$TEST_HOME/settings.json"
assert "settings has enabledPlugins" grep -q "enabledPlugins" "$TEST_HOME/settings.json"
assert "settings has ECC plugin"  grep -q "everything-claude-code" "$TEST_HOME/settings.json"
assert "settings has env"         grep -q "ECC_HOOK_PROFILE" "$TEST_HOME/settings.json"

echo ""

# ─── Test 2: Idempotency ─────────────────────────────────
echo "▸ Test 2: Idempotency (second install)"

# Count files before
count_before=$(find "$TEST_HOME/rules" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
skills_before=$(find "$TEST_HOME/skills" -maxdepth 1 -mindepth 1 2>/dev/null | wc -l | tr -d ' ')

# Run install again
bash "$SCRIPT_DIR/setup.sh" --install --claude-home "$TEST_HOME" > /dev/null 2>&1

# Count files after
count_after=$(find "$TEST_HOME/rules" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
skills_after=$(find "$TEST_HOME/skills" -maxdepth 1 -mindepth 1 2>/dev/null | wc -l | tr -d ' ')

assert "rule count unchanged ($count_before → $count_after)"   test "$count_before" = "$count_after"
assert "skill count unchanged ($skills_before → $skills_after)" test "$skills_before" = "$skills_after"
assert "exactly 9 rules"    test "$count_after" -eq 9
assert "exactly 5 skills"   test "$skills_after" -eq 5

# Content still readable after reinstall
assert "agents.md still readable" test -r "$TEST_HOME/rules/agents.md"
assert "eddie-voice still readable" test -r "$TEST_HOME/skills/eddie-voice/SKILL.md"

echo ""

# ─── Test 3: Check command ───────────────────────────────
echo "▸ Test 3: Check command"

assert "check passes after install" bash "$SCRIPT_DIR/setup.sh" --check --claude-home "$TEST_HOME"

echo ""

# ─── Test 4: Generate Mobile ─────────────────────────────
echo "▸ Test 4: Generate mobile project knowledge"

bash "$SCRIPT_DIR/setup.sh" --generate-mobile --claude-home "$TEST_HOME" > /dev/null 2>&1

assert "project-knowledge.md generated" test -f "$SCRIPT_DIR/mobile/project-knowledge.md"
assert "contains rules content"          grep -q "Agent Orchestration" "$SCRIPT_DIR/mobile/project-knowledge.md"
assert "contains skills list"            grep -q "Available Skills" "$SCRIPT_DIR/mobile/project-knowledge.md"

# Clean up generated file
rm -f "$SCRIPT_DIR/mobile/project-knowledge.md"

echo ""

# ─── Test 5: Uninstall ───────────────────────────────────
echo "▸ Test 5: Uninstall"

bash "$SCRIPT_DIR/setup.sh" --uninstall --claude-home "$TEST_HOME" 2>&1 | tail -3

assert_not "agents.md removed"        test -e "$TEST_HOME/rules/agents.md"
assert_not "eddie-voice removed"      test -e "$TEST_HOME/skills/eddie-voice"
assert_not "open-pr removed"          test -e "$TEST_HOME/skills/open-pr"

echo ""

# ─── Test 6: Reinstall after uninstall ────────────────────
echo "▸ Test 6: Reinstall after uninstall"

bash "$SCRIPT_DIR/setup.sh" --install --claude-home "$TEST_HOME" > /dev/null 2>&1

assert "agents.md re-linked"     test -e "$TEST_HOME/rules/agents.md"
assert "eddie-voice re-linked"   test -e "$TEST_HOME/skills/eddie-voice"
assert "rules readable again"    test -r "$TEST_HOME/rules/agents.md"

echo ""

# ─── Test 7: Dry run makes no changes ────────────────────
echo "▸ Test 7: Dry run safety"

# Uninstall first
bash "$SCRIPT_DIR/setup.sh" --uninstall --claude-home "$TEST_HOME" > /dev/null 2>&1

bash "$SCRIPT_DIR/setup.sh" --install --dry-run --claude-home "$TEST_HOME" > /dev/null 2>&1

assert_not "dry run did not create rules" test -e "$TEST_HOME/rules/agents.md"

echo ""

# ─── Results ──────────────────────────────────────────────
echo "═══════════════════════════════════════════"
echo -e " Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "═══════════════════════════════════════════"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
