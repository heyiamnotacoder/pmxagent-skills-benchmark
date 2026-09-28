#!/usr/bin/env bash
# Start/stop PMxAgent (arm A1) from its published 1.0.0 images, pinned by digest. Deployed copy lives outside this repo.
set -euo pipefail
cd ~/pmxbench_runs/_pmxagent
export PMXAGENT_RAPI_IMAGE=ghcr.io/peterbloomingdale/pmxagent-rapi@sha256:98c8d076a7d71aad8105351bcf56659546e35092e774022000329bf83765ae56
export PMXAGENT_MCP_IMAGE=ghcr.io/peterbloomingdale/pmxagent-mcp@sha256:44795024bc39c233dc2c971b720ea0b9efa1b7d6d47c7f14bc925c260ffe0384
case "${1:-status}" in
  up)     colima status >/dev/null 2>&1 || colima start
          docker compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d --no-build ;;
  down)   docker compose -f docker-compose.yml -f docker-compose.ghcr.yml down ;;
  status) docker compose -f docker-compose.yml -f docker-compose.ghcr.yml ps ;;
esac
