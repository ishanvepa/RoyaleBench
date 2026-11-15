"""Publish docs/writeup.html; see docs/modal_guide.md for the deploy command."""

from pathlib import Path
import re

import modal

ROOT = Path(__file__).resolve().parent
app = modal.App("royalebench-writeup")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("starlette==1.10.0")
    .add_local_file(ROOT / "docs/writeup.html", "/site/writeup.html")
    .add_local_dir(ROOT / "docs/writeup-assets", "/site/writeup-assets")
)


def _web_app(source: Path = Path("/site/writeup.html")):
    from starlette.applications import Starlette
    from starlette.exceptions import HTTPException
    from starlette.responses import FileResponse, RedirectResponse
    from starlette.routing import Mount, Route
    from starlette.staticfiles import StaticFiles

    # Keep the original HTML intact; relative guide links open rendered GitHub docs.
    guides = set(re.findall(r'href="([^"/]+\.md)"', source.read_text(encoding="utf-8")))

    async def writeup(request):
        return FileResponse(source, media_type="text/html", headers={"Cache-Control": "no-cache"})

    async def guide(request):
        document = request.path_params["document"]
        if document not in guides:
            raise HTTPException(status_code=404)
        return RedirectResponse(f"https://github.com/ishanvepa/RoyaleBench/blob/main/docs/{document}")

    return Starlette(routes=[
        Route("/", writeup),
        Route("/writeup.html", writeup),
        Mount("/writeup-assets", app=StaticFiles(directory=source.parent / "writeup-assets"), name="assets"),
        Route("/{document}", guide),
    ])


@app.function(image=image, cpu=0.25, memory=256, max_containers=1, scaledown_window=60)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(label="royalebench-writeup")
def serve():
    return _web_app()


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Preview the public writeup locally, without deploying.")
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    uvicorn.run(_web_app(ROOT / "docs/writeup.html"), host="127.0.0.1", port=args.port)
