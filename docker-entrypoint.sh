#!/bin/sh
set -e

mkdir -p "$(dirname "${QA_TASKS_DB:-/data/qa_tasks.db}")"

exec "$@"
