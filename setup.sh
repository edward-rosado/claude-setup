#!/usr/bin/env bash
set -euo pipefail

# Claude Setup — Cross-platform bootstrap script
# Symlinks rules, skills, and instincts into ~/.claude/
# Installs plugins declaratively from settings.json

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
BACKUP_DIR="$CLAUDE_HOME/backups/claude-setup-$(date +%Y%m%d-%H%M%S)"
DRY_RUN=false
VERBOSE=false

# ─── Colors ───────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_dry()   { echo -e "${YELLOW}[DRY]${NC}   $*"; }

# ─── Platform Detection ──────────────────────────────────
detect_platform() {
    case "$(uname -s)" in
        Linux*)     PLATFORM="linux";;
        Darwin*)    PLATFORM="macos";;
        CYGWIN*|MINGW*|MSYS*) PLATFORM="windows";;
        *)          PLATFORM="unknown";;
    esac

    if [[ "$PLATFORM" == "windows" ]]; then
        # Check if Developer Mode is enabled (symlinks work without admin)
        if reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /v AllowDevelopmentWithoutDevLicense 2>/dev/null | grep -q "0x1"; then
            SYMLINK_METHOD="native"
        else
            SYMLINK_METHOD="junction"
            log_warn "Developer Mode not enabled. Using junctions for directories."
        fi
    else
        SYMLINK_METHOD="native"
    fi

    log_info "Platform: $PLATFORM (symlink method: $SYMLINK_METHOD)"
}

# ─── Symlink Helpers ─────────────────────────────────────

# Check if a target is a symlink or junction pointing to our source
is_our_link() {
    local target="$1"
    local source="$2"

    # True symlink check
    if [[ -L "$target" ]]; then
        return 0
    fi

    # On Windows, junctions aren't detected by -L but we can check
    # if the target exists and contains the same content as our source
    if [[ "$PLATFORM" == "windows" && -d "$target" && -d "$source" ]]; then
        # Check if it's a junction by comparing resolved paths
        local target_resolved source_resolved
        target_resolved="$(cd "$target" 2>/dev/null && pwd)" || return 1
        source_resolved="$(cd "$source" 2>/dev/null && pwd)" || return 1
        if [[ "$target_resolved" == "$source_resolved" ]]; then
            return 0
        fi
    fi

    return 1
}

create_symlink() {
    local source="$1"
    local target="$2"

    # Check if target already points to the right place
    if is_our_link "$target" "$source"; then
        [[ "$VERBOSE" == true ]] && log_ok "Already linked: $target"
        return 0
    fi

    if $DRY_RUN; then
        log_dry "Would link: $target → $source"
        return 0
    fi

    # Back up existing file/dir if it exists and isn't our link
    if [[ -e "$target" ]]; then
        mkdir -p "$BACKUP_DIR"
        local backup_name
        backup_name="$(basename "$target")"
        if [[ ! -e "$BACKUP_DIR/$backup_name" ]]; then
            cp -r "$target" "$BACKUP_DIR/$backup_name"
            log_warn "Backed up: $target → $BACKUP_DIR/$backup_name"
        fi
        rm -rf "$target"
    fi

    # Create parent directory
    mkdir -p "$(dirname "$target")"

    # Create the symlink
    ln -sf "$source" "$target"

    log_ok "Linked: $target → $source"

    # Record in manifest if available
    if [[ -n "${MANIFEST_FILE:-}" && -f "${MANIFEST_FILE:-/dev/null}" ]]; then
        echo "$target|$source" >> "$MANIFEST_FILE"
    fi
}

remove_symlink() {
    local target="$1"
    local source="${2:-}"

    # Check both true symlinks and junctions
    if [[ -L "$target" ]] || { [[ -n "$source" ]] && is_our_link "$target" "$source"; }; then
        if $DRY_RUN; then
            log_dry "Would remove: $target"
        else
            rm -rf "$target"
            log_ok "Removed: $target"
        fi
    fi
}

# ─── Install ─────────────────────────────────────────────
do_install() {
    log_info "Installing claude-setup into $CLAUDE_HOME"

    # Ensure target directories exist
    mkdir -p "$CLAUDE_HOME/rules" "$CLAUDE_HOME/skills"

    # Track what we install for check/uninstall
    MANIFEST_FILE="$CLAUDE_HOME/.claude-setup-manifest"
    : > "$MANIFEST_FILE"

    # Symlink rules (flatten grouped structure)
    log_info "Linking rules..."
    for group_dir in "$SCRIPT_DIR"/rules/*/; do
        [[ -d "$group_dir" ]] || continue
        for rule_file in "$group_dir"*.md; do
            [[ -f "$rule_file" ]] || continue
            local basename
            basename="$(basename "$rule_file")"
            create_symlink "$rule_file" "$CLAUDE_HOME/rules/$basename"
        done
    done

    # Symlink skills (flatten grouped structure, link entire skill dirs)
    log_info "Linking skills..."
    for group_dir in "$SCRIPT_DIR"/skills/*/; do
        [[ -d "$group_dir" ]] || continue
        for skill_dir in "$group_dir"*/; do
            [[ -d "$skill_dir" ]] || continue
            local skill_name
            skill_name="$(basename "$skill_dir")"
            create_symlink "$skill_dir" "$CLAUDE_HOME/skills/$skill_name"
        done
    done

    # Symlink learned instincts if they exist
    if [[ -d "$SCRIPT_DIR/learned/instincts" ]]; then
        log_info "Linking learned instincts..."
        mkdir -p "$CLAUDE_HOME/homunculus"
        # Link individual instinct files, not the whole directory
        # (homunculus manages its own structure)
        for instinct_file in "$SCRIPT_DIR"/learned/instincts/*; do
            [[ -e "$instinct_file" ]] || continue
            local basename
            basename="$(basename "$instinct_file")"
            create_symlink "$instinct_file" "$CLAUDE_HOME/homunculus/instincts/$basename"
        done
    fi

    # Merge settings
    log_info "Merging settings..."
    merge_settings

    # Install plugins
    log_info "Installing plugins..."
    install_plugins

    echo ""
    log_ok "Installation complete!"
}

# ─── Settings Merge ──────────────────────────────────────
merge_settings() {
    local manifest="$SCRIPT_DIR/settings.json"
    local target="$CLAUDE_HOME/settings.json"

    if [[ ! -f "$manifest" ]]; then
        log_warn "No settings.json manifest found, skipping"
        return 0
    fi

    if $DRY_RUN; then
        log_dry "Would merge settings from $manifest into $target"
        return 0
    fi

    # If no existing settings, start from empty object
    if [[ ! -f "$target" ]]; then
        echo '{}' > "$target"
    fi

    # Find python binary
    local py_cmd=""
    if command -v python3 &> /dev/null; then
        py_cmd="python3"
    elif command -v python &> /dev/null; then
        py_cmd="python"
    else
        log_error "Python not found. Cannot merge settings. Install Python 3 and retry."
        return 1
    fi

    # Use python for JSON merging (available on all platforms)
    "$py_cmd" - "$manifest" "$target" << 'PYEOF'
import json, sys

manifest_path = sys.argv[1]
target_path = sys.argv[2]

with open(manifest_path) as f:
    manifest = json.load(f)
with open(target_path) as f:
    existing = json.load(f)

# Merge env vars
if 'env' in manifest:
    existing.setdefault('env', {})
    existing['env'].update(manifest['env'])

# Merge enabled plugins
if 'plugins' in manifest:
    existing.setdefault('enabledPlugins', {})
    for plugin in manifest['plugins']:
        existing['enabledPlugins'][plugin] = True

# Merge marketplaces
if 'marketplaces' in manifest:
    existing.setdefault('extraKnownMarketplaces', {})
    for name, config in manifest['marketplaces'].items():
        existing['extraKnownMarketplaces'][name] = {'source': config}

with open(target_path, 'w') as f:
    json.dump(existing, f, indent=2)
PYEOF

    log_ok "Settings merged"
}

# ─── Plugin Install ──────────────────────────────────────
install_plugins() {
    local manifest="$SCRIPT_DIR/settings.json"

    if [[ ! -f "$manifest" ]]; then
        return 0
    fi

    if $DRY_RUN; then
        log_dry "Would install plugins from manifest"
        return 0
    fi

    # Check if claude CLI is available
    if ! command -v claude &> /dev/null; then
        log_warn "Claude CLI not found. Plugins listed in settings.json but cannot auto-install."
        log_warn "Install Claude Code CLI, then rerun: setup.sh --install"
        return 0
    fi

    log_info "Plugin installation requires Claude CLI — skipping if not interactive"
}

# ─── Uninstall ────────────────────────────────────────────
do_uninstall() {
    log_info "Uninstalling claude-setup from $CLAUDE_HOME"

    local manifest="$CLAUDE_HOME/.claude-setup-manifest"

    if [[ -f "$manifest" ]]; then
        # Use manifest to know exactly what to remove
        while IFS='|' read -r target source; do
            [[ -z "$target" ]] && continue
            if [[ -e "$target" ]]; then
                if $DRY_RUN; then
                    log_dry "Would remove: $target"
                else
                    rm -rf "$target"
                    log_ok "Removed: $target"
                fi
            fi
        done < "$manifest"
        $DRY_RUN || rm -f "$manifest"
    else
        # Fallback: scan for known files
        for group_dir in "$SCRIPT_DIR"/rules/*/; do
            [[ -d "$group_dir" ]] || continue
            for rule_file in "$group_dir"*.md; do
                [[ -f "$rule_file" ]] || continue
                local basename
                basename="$(basename "$rule_file")"
                local target="$CLAUDE_HOME/rules/$basename"
                [[ -e "$target" ]] && { $DRY_RUN && log_dry "Would remove: $target" || { rm -rf "$target"; log_ok "Removed: $target"; }; }
            done
        done

        for group_dir in "$SCRIPT_DIR"/skills/*/; do
            [[ -d "$group_dir" ]] || continue
            for skill_dir in "$group_dir"*/; do
                [[ -d "$skill_dir" ]] || continue
                local skill_name
                skill_name="$(basename "$skill_dir")"
                local target="$CLAUDE_HOME/skills/$skill_name"
                [[ -e "$target" ]] && { $DRY_RUN && log_dry "Would remove: $target" || { rm -rf "$target"; log_ok "Removed: $target"; }; }
            done
        done
    fi

    echo ""
    log_ok "Uninstall complete. Backups remain in $CLAUDE_HOME/backups/"
}

# ─── Check ────────────────────────────────────────────────
do_check() {
    log_info "Checking claude-setup installation status..."
    local all_good=true

    # Check rules — use -e (exists) not -L (symlink) for Windows compat
    for group_dir in "$SCRIPT_DIR"/rules/*/; do
        [[ -d "$group_dir" ]] || continue
        for rule_file in "$group_dir"*.md; do
            [[ -f "$rule_file" ]] || continue
            local basename
            basename="$(basename "$rule_file")"
            local target="$CLAUDE_HOME/rules/$basename"
            if [[ -e "$target" && -r "$target" ]]; then
                log_ok "Rule: $basename"
            else
                log_warn "Missing: $basename"
                all_good=false
            fi
        done
    done

    # Check skills
    for group_dir in "$SCRIPT_DIR"/skills/*/; do
        [[ -d "$group_dir" ]] || continue
        for skill_dir in "$group_dir"*/; do
            [[ -d "$skill_dir" ]] || continue
            local skill_name
            skill_name="$(basename "$skill_dir")"
            local target="$CLAUDE_HOME/skills/$skill_name"
            if [[ -e "$target" ]]; then
                log_ok "Skill: $skill_name"
            else
                log_warn "Missing: $skill_name"
                all_good=false
            fi
        done
    done

    # Check manifest
    if [[ -f "$CLAUDE_HOME/.claude-setup-manifest" ]]; then
        log_ok "Manifest: present"
    else
        log_warn "Manifest: missing (run --install to create)"
    fi

    if $all_good; then
        log_ok "All components installed correctly"
        return 0
    else
        log_warn "Some components are missing. Run: setup.sh --install"
        return 1
    fi
}

# ─── Generate Mobile ─────────────────────────────────────
do_generate_mobile() {
    local output="$SCRIPT_DIR/mobile/project-knowledge.md"

    log_info "Generating mobile project knowledge..."

    if $DRY_RUN; then
        log_dry "Would generate: $output"
        return 0
    fi

    cat > "$output" << 'HEADER'
# Eddie's AI Tooling Setup — Project Knowledge

> Auto-generated by `setup.sh --generate-mobile`. Do not edit directly.
> Source: github.com/edward-rosado/claude-setup

---

HEADER

    # Concatenate all rules
    for group_dir in "$SCRIPT_DIR"/rules/*/; do
        [[ -d "$group_dir" ]] || continue
        local group_name
        group_name="$(basename "$group_dir")"
        echo "## Rules — ${group_name^}" >> "$output"
        echo "" >> "$output"
        for rule_file in "$group_dir"*.md; do
            [[ -f "$rule_file" ]] || continue
            cat "$rule_file" >> "$output"
            echo "" >> "$output"
            echo "---" >> "$output"
            echo "" >> "$output"
        done
    done

    # Note about skills
    echo "## Available Skills" >> "$output"
    echo "" >> "$output"
    for group_dir in "$SCRIPT_DIR"/skills/*/; do
        [[ -d "$group_dir" ]] || continue
        for skill_dir in "$group_dir"*/; do
            [[ -d "$skill_dir" ]] || continue
            local skill_name
            skill_name="$(basename "$skill_dir")"
            echo "- **/$skill_name**" >> "$output"
            # Extract description from SKILL.md frontmatter
            if [[ -f "$skill_dir/SKILL.md" ]]; then
                local desc
                desc=$(grep -m1 "^description:" "$skill_dir/SKILL.md" 2>/dev/null | sed 's/^description: *//' || true)
                [[ -n "$desc" ]] && echo "  $desc" >> "$output"
            fi
        done
    done
    echo "" >> "$output"

    log_ok "Generated: $output"
}

# ─── Sync Instincts ──────────────────────────────────────
do_sync() {
    log_info "Syncing learned instincts from $CLAUDE_HOME into repo..."

    local instinct_source="$CLAUDE_HOME/homunculus"
    local instinct_target="$SCRIPT_DIR/learned/instincts"

    if [[ ! -d "$instinct_source" ]]; then
        log_warn "No homunculus directory found at $instinct_source"
        return 0
    fi

    if $DRY_RUN; then
        log_dry "Would sync instincts from $instinct_source"
        return 0
    fi

    # Copy any instinct files that don't exist in the repo yet
    local count=0
    find "$instinct_source" -name "*.json" -path "*/instincts/*" 2>/dev/null | while read -r f; do
        local basename
        basename="$(basename "$f")"
        if [[ ! -f "$instinct_target/$basename" ]]; then
            cp "$f" "$instinct_target/$basename"
            log_ok "Synced: $basename"
            count=$((count + 1))
        fi
    done

    if [[ $count -eq 0 ]]; then
        log_info "No new instincts to sync"
    fi
}

# ─── Test Runner ──────────────────────────────────────────
do_test() {
    log_info "Running test suite..."
    if [[ -f "$SCRIPT_DIR/tests/test_setup.sh" ]]; then
        bash "$SCRIPT_DIR/tests/test_setup.sh" "$SCRIPT_DIR"
    else
        log_error "Test file not found: tests/test_setup.sh"
        return 1
    fi
}

# ─── Usage ────────────────────────────────────────────────
usage() {
    cat << EOF
Usage: setup.sh [OPTIONS] COMMAND

Claude Setup — Cross-platform AI tooling bootstrap

Commands:
  --install           Symlink rules + skills into ~/.claude/, install plugins
  --generate-mobile   Generate project-knowledge.md for claude.ai mobile
  --sync              Pull new learned instincts from ~/.claude/ into repo
  --uninstall         Remove symlinks, preserve backups
  --check             Dry-run check: show installation status
  --test              Run the test suite

Options:
  --claude-home DIR   Override ~/.claude/ location (for testing)
  --dry-run           Show what would happen without making changes
  --verbose           Show extra detail
  -h, --help          Show this help

Examples:
  setup.sh --install                    # First-time setup
  setup.sh --check                      # Verify installation
  setup.sh --install --dry-run          # Preview changes
  setup.sh --generate-mobile            # Build mobile instructions
  setup.sh --sync                       # Pull new instincts
  setup.sh --test                       # Run tests
EOF
}

# ─── Main ─────────────────────────────────────────────────
main() {
    local command=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --install)          command="install";;
            --uninstall)        command="uninstall";;
            --check)            command="check";;
            --generate-mobile)  command="generate-mobile";;
            --sync)             command="sync";;
            --test)             command="test";;
            --claude-home)      shift; CLAUDE_HOME="$1";;
            --dry-run)          DRY_RUN=true;;
            --verbose)          VERBOSE=true;;
            -h|--help)          usage; exit 0;;
            *)                  log_error "Unknown option: $1"; usage; exit 1;;
        esac
        shift
    done

    if [[ -z "$command" ]]; then
        usage
        exit 1
    fi

    detect_platform

    case "$command" in
        install)          do_install;;
        uninstall)        do_uninstall;;
        check)            do_check;;
        generate-mobile)  do_generate_mobile;;
        sync)             do_sync;;
        test)             do_test;;
    esac
}

main "$@"
