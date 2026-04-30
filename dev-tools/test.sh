#!/bin/bash

set -e

call() {
  echo $@
  $@
}

call ruff check src/ tests/ dev-tools/
call pyright src/
call pytest tests/
cd web
call npm run lint
call npm test
call npm run build
