#!/usr/bin/env bash
# One-time dev setup for a fresh clone. Points git at the repo-owned hooks
# in .githooks/ (instead of the untracked, per-clone .git/hooks/) and makes
# sure they're executable.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

git config core.hooksPath .githooks
chmod +x .githooks/*

echo "Configured core.hooksPath -> .githooks"
echo "Hooks installed:"
ls -la .githooks
