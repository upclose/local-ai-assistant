#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# push_to_github.sh  —  initialise repo and push to a new GitHub repository.
#
# Usage:
#   chmod +x scripts/push_to_github.sh
#   ./scripts/push_to_github.sh <github_username> <repo_name>
#
# Requirements:
#   • git installed
#   • GitHub CLI (gh) installed  →  https://cli.github.com/
#     OR set GITHUB_TOKEN env var and the script uses the API directly
#
# Example:
#   ./scripts/push_to_github.sh john-doe local-ai-assistant
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GITHUB_USER="${1:-}"
REPO_NAME="${2:-local-ai-assistant}"

if [[ -z "$GITHUB_USER" ]]; then
  echo "Usage: $0 <github_username> [repo_name]"
  exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "══════════════════════════════════════════════"
echo "  Local AI Assistant — GitHub Push Script"
echo "  User : $GITHUB_USER"
echo "  Repo : $REPO_NAME"
echo "  Dir  : $REPO_DIR"
echo "══════════════════════════════════════════════"

# ── 1. Git init ───────────────────────────────────────────────────────────────
if [[ ! -d ".git" ]]; then
  echo "[1/5] Initialising git repository…"
  git init
  git checkout -b main
else
  echo "[1/5] Git already initialised — skipping."
fi

# ── 2. Ensure .env is not committed ──────────────────────────────────────────
echo "[2/5] Checking .gitignore…"
if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "      Created .env from .env.example — edit it before using."
fi
# Make sure data/ dir exists with a placeholder so git tracks the folder
mkdir -p data/notes
touch data/.gitkeep data/notes/.gitkeep

# ── 3. Stage everything ───────────────────────────────────────────────────────
echo "[3/5] Staging files…"
git add .
git status --short

# ── 4. Commit ─────────────────────────────────────────────────────────────────
echo "[4/5] Committing…"
git commit -m "feat: initial commit — local AI assistant" \
           -m "Offline AI assistant powered by Ollama. Features: streaming chat,
SQLite message history, FAISS semantic memory, tool-calling system,
FastAPI backend, and vanilla-JS web UI." \
  || echo "      Nothing to commit (already up to date)."

# ── 5. Create GitHub repo and push ───────────────────────────────────────────
echo "[5/5] Creating GitHub repository and pushing…"

if command -v gh &>/dev/null; then
  # Preferred: use GitHub CLI
  gh auth status &>/dev/null || gh auth login

  gh repo create "$REPO_NAME" \
    --public \
    --description "Offline local AI assistant — Ollama + FastAPI + FAISS. No paid APIs." \
    --push \
    --source=. \
    --remote=origin \
    2>/dev/null || true   # ignore if repo already exists

  git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git" 2>/dev/null || true
  git push -u origin main

elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
  # Fallback: create repo via API then push
  echo "      Using GITHUB_TOKEN to create repo via API…"
  curl -s -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user/repos \
    -d "{
      \"name\": \"$REPO_NAME\",
      \"description\": \"Offline local AI assistant — Ollama + FastAPI + FAISS. No paid APIs.\",
      \"private\": false,
      \"auto_init\": false
    }" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Repo:', d.get('html_url','(check output)'))"

  git remote remove origin 2>/dev/null || true
  git remote add origin "https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
  git push -u origin main

else
  echo ""
  echo "  ⚠  Neither 'gh' CLI nor GITHUB_TOKEN found."
  echo "  Options:"
  echo "    A) Install GitHub CLI:  https://cli.github.com/"
  echo "    B) Set env var:         export GITHUB_TOKEN=<your_token>"
  echo ""
  echo "  Then re-run this script, OR push manually:"
  echo "    git remote add origin https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
  echo "    git push -u origin main"
  exit 1
fi

echo ""
echo "  ✅  Done!  https://github.com/${GITHUB_USER}/${REPO_NAME}"
