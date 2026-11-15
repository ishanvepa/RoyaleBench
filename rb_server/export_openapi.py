"""Write rb_server/openapi.json, the contract the web app's TypeScript types are generated from.

    uv run python -m rb_server.export_openapi
A test fails when the committed file is stale, so the API and the UI cannot drift apart silently.
"""

from __future__ import annotations

import json
from pathlib import Path

from rb_evals.fake import FakeValkyrie

from .app import create_app
from .context import build_context
from .settings import Settings

OPENAPI_PATH = Path(__file__).with_name("openapi.json")


def build_openapi() -> dict:
    settings = Settings()
    app = create_app(settings, ctx=build_context(settings, valkyrie=FakeValkyrie(seed=False)))
    return app.openapi()


def render(spec: dict) -> str:
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    OPENAPI_PATH.write_text(render(build_openapi()), encoding="utf-8", newline="\n")
    print("wrote", OPENAPI_PATH)


if __name__ == "__main__":
    main()
