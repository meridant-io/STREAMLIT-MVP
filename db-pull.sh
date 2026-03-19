#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# db-pull.sh — Download databases from Fly.io to local dev machine
#
# Usage:
#   ./db-pull.sh                   # pull both DBs (frameworks + assessments)
#   ./db-pull.sh --frameworks      # pull framework DB only
#   ./db-pull.sh --assessments     # pull assessment DB only
#   ./db-pull.sh --dry-run         # show what would be pulled, don't overwrite
#
# DB flow rules (per ADR-009):
#   Framework DB  (meridant_frameworks.db) : Fly.io → local  ✓  (to sync dev machines)
#   Assessment DB (meridant.db)            : Fly.io → local  ✓  (prod data, read-only on dev)
#
# Run this on any dev machine to get in sync with production.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

APP="streamlit-mvp"
FLY_DATA_DIR="/data"
LOCAL_DATA_DIR="data"

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

info()    { echo -e "${BOLD}▸ $*${RESET}"; }
success() { echo -e "${GREEN}✓ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠ $*${RESET}"; }
error()   { echo -e "${RED}✗ $*${RESET}" >&2; exit 1; }

# ── Argument parsing ──────────────────────────────────────────────────────────
PULL_FRAMEWORKS=true
PULL_ASSESSMENTS=true
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --frameworks)  PULL_ASSESSMENTS=false ;;
    --assessments) PULL_FRAMEWORKS=false ;;
    --dry-run)     DRY_RUN=true ;;
  esac
done

# ── Preflight ─────────────────────────────────────────────────────────────────
command -v fly >/dev/null || error "fly CLI is not installed — see https://fly.io/docs/hands-on/install-flyctl/"
mkdir -p "$LOCAL_DATA_DIR"

# ── Ensure a VM is running ────────────────────────────────────────────────────
info "Ensuring a VM is running..."
fly machine start --app "$APP" 2>/dev/null || true

MAX_WAIT=90
ELAPSED=0
until fly status --app "$APP" 2>/dev/null | grep -q "started"; do
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    error "Timed out waiting for a running VM after ${MAX_WAIT}s"
  fi
  info "  Waiting for VM... (${ELAPSED}s / ${MAX_WAIT}s)"
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done
success "VM is running"

# ── Helper: pull a single file via SFTP ──────────────────────────────────────
pull_db() {
  local remote_name="$1"
  local local_path="$2"
  local label="$3"

  info "Pulling $label: $FLY_DATA_DIR/$remote_name → $local_path"

  if [[ "$DRY_RUN" == true ]]; then
    warn "[dry-run] Would download $FLY_DATA_DIR/$remote_name to $local_path"
    return
  fi

  # Backup existing file then remove it — fly ssh sftp shell's `get` refuses
  # to overwrite an existing file, so we must delete before downloading.
  if [[ -f "$local_path" ]]; then
    local backup="${local_path}.bak"
    cp "$local_path" "$backup"
    warn "Backed up existing file to $backup"
    rm -f "$local_path"
  fi

  printf "get %s/%s %s\nexit\n" "$FLY_DATA_DIR" "$remote_name" "$local_path" \
    | fly ssh sftp shell --app "$APP"

  local size
  size=$(du -sh "$local_path" 2>/dev/null | cut -f1 || echo "unknown size")
  success "$label downloaded ($size) → $local_path"
}

# ── Pull framework DB ─────────────────────────────────────────────────────────
if [[ "$PULL_FRAMEWORKS" == true ]]; then
  # Try the current name first, fall back to legacy name
  if fly ssh sftp shell --app "$APP" <<< "ls /data/meridant_frameworks.db" 2>/dev/null | grep -q "meridant_frameworks.db"; then
    pull_db "meridant_frameworks.db" "$LOCAL_DATA_DIR/meridant_frameworks.db" "Framework DB"
  elif fly ssh sftp shell --app "$APP" <<< "ls /data/e2caf.db" 2>/dev/null | grep -q "e2caf.db"; then
    pull_db "e2caf.db" "$LOCAL_DATA_DIR/e2caf.db" "Framework DB (legacy name)"
  else
    warn "No framework DB found on Fly.io volume. Skipping."
  fi
fi

# ── Pull assessment DB ────────────────────────────────────────────────────────
if [[ "$PULL_ASSESSMENTS" == true ]]; then
  if fly ssh sftp shell --app "$APP" <<< "ls /data/meridant.db" 2>/dev/null | grep -q "meridant.db"; then
    pull_db "meridant.db" "$LOCAL_DATA_DIR/meridant.db" "Assessment DB (prod data)"
    warn "Assessment DB contains production data — do not push this back to Fly.io"
  else
    warn "No assessment DB found on Fly.io volume. Skipping."
  fi
fi

echo ""
success "Pull complete — local data/ is now in sync with $APP.fly.dev"
