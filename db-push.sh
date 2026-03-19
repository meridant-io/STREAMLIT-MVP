#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# db-push.sh — Upload databases to Fly.io from local dev machine
#
# Usage:
#   ./db-push.sh --frameworks      # push framework DB only (safe, normal workflow)
#   ./db-push.sh --assessments     # push assessment DB (DESTRUCTIVE — overwrites prod)
#   ./db-push.sh --both            # push both DBs (DESTRUCTIVE)
#   ./db-push.sh --dry-run         # show what would be pushed, don't upload
#
# WARNING: Pushing the assessment DB overwrites live production data.
#          Only do this for initial setup, seeding, or deliberate restore.
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
PUSH_FRAMEWORKS=false
PUSH_ASSESSMENTS=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --frameworks)  PUSH_FRAMEWORKS=true ;;
    --assessments) PUSH_ASSESSMENTS=true ;;
    --both)        PUSH_FRAMEWORKS=true; PUSH_ASSESSMENTS=true ;;
    --dry-run)     DRY_RUN=true ;;
  esac
done

if [[ "$PUSH_FRAMEWORKS" == false && "$PUSH_ASSESSMENTS" == false ]]; then
  echo "Usage:"
  echo "  ./db-push.sh --frameworks      # push framework DB (safe)"
  echo "  ./db-push.sh --assessments     # push assessment DB (overwrites prod)"
  echo "  ./db-push.sh --both            # push both"
  echo "  ./db-push.sh --dry-run         # preview without uploading"
  exit 1
fi

# ── Preflight ─────────────────────────────────────────────────────────────────
command -v fly >/dev/null || error "fly CLI is not installed — see https://fly.io/docs/hands-on/install-flyctl/"

# ── Confirm destructive assessment DB push ────────────────────────────────────
if [[ "$PUSH_ASSESSMENTS" == true && "$DRY_RUN" == false ]]; then
  echo ""
  warn "WARNING: You are about to overwrite the production assessment database."
  warn "This will replace all live user data on Fly.io with your local copy."
  echo ""
  read -r -p "Type YES to confirm: " confirm
  if [[ "$confirm" != "YES" ]]; then
    error "Aborted — type exactly YES to proceed"
  fi
  echo ""
fi

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

# ── Helper: push a single file via SFTP ──────────────────────────────────────
push_db() {
  local local_path="$1"
  local remote_name="$2"
  local label="$3"

  if [[ ! -f "$local_path" ]]; then
    error "$label not found at $local_path"
  fi

  local size
  size=$(du -sh "$local_path" | cut -f1)
  info "Pushing $label: $local_path ($size) → $FLY_DATA_DIR/$remote_name"

  if [[ "$DRY_RUN" == true ]]; then
    warn "[dry-run] Would upload $local_path to $FLY_DATA_DIR/$remote_name"
    return
  fi

  # fly ssh sftp shell's `put` refuses to overwrite existing files, so delete first.
  info "Removing existing remote file (if any)..."
  fly ssh console --app "$APP" --command "rm -f $FLY_DATA_DIR/$remote_name" 2>/dev/null || true

  printf "put %s %s/%s\nexit\n" "$local_path" "$FLY_DATA_DIR" "$remote_name" \
    | fly ssh sftp shell --app "$APP"

  local remote_bytes local_bytes
  remote_bytes=$(fly ssh console --app "$APP" --command "wc -c < $FLY_DATA_DIR/$remote_name" 2>/dev/null | tr -d ' \n')
  local_bytes=$(wc -c < "$local_path" | tr -d ' ')
  success "$label uploaded (local: $local_bytes bytes, remote: $remote_bytes bytes)"
}

# ── Push framework DB ─────────────────────────────────────────────────────────
if [[ "$PUSH_FRAMEWORKS" == true ]]; then
  if   [[ -f "$LOCAL_DATA_DIR/meridant_frameworks.db" ]]; then
    push_db "$LOCAL_DATA_DIR/meridant_frameworks.db" "meridant_frameworks.db" "Framework DB"
  elif [[ -f "$LOCAL_DATA_DIR/e2caf.db" ]]; then
    push_db "$LOCAL_DATA_DIR/e2caf.db" "e2caf.db" "Framework DB (legacy name)"
  else
    error "No framework DB found in $LOCAL_DATA_DIR/"
  fi
fi

# ── Push assessment DB ────────────────────────────────────────────────────────
if [[ "$PUSH_ASSESSMENTS" == true ]]; then
  push_db "$LOCAL_DATA_DIR/meridant.db" "meridant.db" "Assessment DB"
fi

echo ""
success "Push complete — https://$APP.fly.dev"
