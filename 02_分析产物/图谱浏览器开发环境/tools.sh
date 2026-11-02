#!/bin/sh
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$base"
case "${1:-help}" in
 npm)
  shift
  exec npm "$@" ;;
 impeccable)
  shift
  tool=${IMPECCABLE_BIN:-impeccable}
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf '%s\n' 'Optional Impeccable tool not found. Set IMPECCABLE_BIN or add it to PATH. It is not needed to run the atlas.' >&2
    exit 127
  fi
  export IMPECCABLE_NO_UPDATE_CHECK=1 IMPECCABLE_NO_TELEMETRY=1 DO_NOT_TRACK=1
  exec "$tool" "$@" ;;
 browser)
  shift
  tool=${PLAYWRIGHT_CLI:-playwright-cli}
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf '%s\n' 'Optional browser tool not found. Set PLAYWRIGHT_CLI or add playwright-cli to PATH. It is not needed to run the atlas.' >&2
    exit 127
  fi
  exec "$tool" "$@" ;;
 *) printf '%s\n' 'tools.sh npm <args> | tools.sh impeccable <command> | tools.sh browser <command>' ;;
esac
