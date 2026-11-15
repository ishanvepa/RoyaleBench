"""Validate all v3 coordinate references, isolation, restart and fresh-container grading.

    uv run python -m cr_arena.validate_v3_docker --jobs 2
"""
from .build_v3 import OUT
from .validate_v1_docker import main

if __name__ == "__main__":
    main(default_benchmark=OUT)
