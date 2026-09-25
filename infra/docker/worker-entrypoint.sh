#!/bin/sh
# Worker entrypoint for AeroCloud Celery GPU worker.
#
# Design decisions (Phase 12, D-23, D-24):
#   - ulimit -c 0: core dumps disabled per CLAUDE.md section 12 (MVP production hardening).
#   - prefork pool: GPU tasks require process isolation; threading pool shares CUDA context.
#   - concurrency=1: one GPU task at a time per worker instance (D-12).
#   - max-tasks-per-child=50: recycle forked child after 50 tasks to prevent GPU memory
#       leak accumulation (T-12-03-02).
#   - queues=realtime,background: worker handles both render (realtime) and self-play (background).
#   - exec: replaces shell with celery process — clean signal delivery (SIGTERM → drain → exit).
#
# GPU isolation (D-14):
#   Set CUDA_VISIBLE_DEVICES=N in the Docker container or PM2 env — not in this script.
#   Each worker instance receives its own GPU assignment via the container environment.

set -e

# D-24: Disable core dumps (CLAUDE.md section 12 — MVP production hardening)
ulimit -c 0

exec celery -A aerocloud_worker.celery_app worker \
    --pool=prefork \
    --concurrency=1 \
    --max-tasks-per-child=50 \
    --queues=realtime,background \
    --loglevel=info
