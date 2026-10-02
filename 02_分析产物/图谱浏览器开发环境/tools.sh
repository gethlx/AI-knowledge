#!/bin/sh
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PATH="/Users/larry/.local/share/fnm/node-versions/v24.14.0/installation/bin:$PATH"
case "${1:-help}" in
 npm)
  shift
  cd "$base"
  exec npm "$@" ;;
 impeccable)
  shift
  export IMPECCABLE_NO_UPDATE_CHECK=1 IMPECCABLE_NO_TELEMETRY=1 DO_NOT_TRACK=1
  export IMPECCABLE_BIN=/Users/larry/AI-Tools/shared/skills/impeccable/scripts/bin/darwin-arm64/impeccable
  cd "$base"
  exec /Users/larry/AI-Tools/shared/skills/impeccable/scripts/impeccable "$@" ;;
 browser)
  shift
  exec /Users/larry/.codex/skills/playwright/scripts/playwright_cli.sh "$@" ;;
 *) printf '%s\n' 'tools.sh npm <args> | tools.sh impeccable <command> | tools.sh browser <command>' ;;
esac
