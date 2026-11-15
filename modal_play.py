"""Deploy the ten-match public game: uv run --extra hosting modal deploy modal_play.py."""

from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent
app = modal.App("royalebench-play")
volume = modal.Volume.from_name("royalebench-play-data", create_if_missing=True, version=2)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(uv_project_dir=str(ROOT), uv_version="0.9.26", extra_options="--only-group play")
    .env({"PYTHONPATH": "/app", "CR_ARENA_DB": "/data/arena.db",
          "CR_ARENA_REPLAY_DIR": "/data/human-play", "CR_ARENA_LEADERBOARD": "/data/leaderboard.csv"})
    # Runtime file mounts must come after all image build steps, including env().
    .add_local_dir(ROOT / "cr_arena", "/app/cr_arena", ignore=["__pycache__", "*.pyc"])
    .add_local_dir(ROOT / "configs", "/app/configs")
    .add_local_dir(ROOT / "supabase", "/app/supabase")
)


@app.server(
    image=image,
    cpu=32,  # ten planner parents + two search workers per match, with game-loop headroom
    memory=16384,
    min_containers=1,
    max_containers=1,
    compute_region="us-west",
    routing_region="us-west",
    port=8000,
    unauthenticated=True,
    volumes={"/data": volume},
)
class PlayServer:
    @modal.enter()
    def start(self):
        import subprocess

        # Native Servers proxy WebSockets directly to Uvicorn, bypassing Function input queues.
        self.process = subprocess.Popen([
            "python", "-m", "cr_arena.live", "--public", "--host", "0.0.0.0", "--port", "8000",
        ])

    @modal.exit()
    def stop(self):
        import subprocess

        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        volume.commit()


# Keep the originally shared modal.run link usable; only the game Server stays warm.
@app.function(image=image, max_containers=1, scaledown_window=2, routing_region="us-west")
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def serve():
    from starlette.applications import Starlette
    from starlette.responses import RedirectResponse
    from starlette.routing import Route

    def redirect(request):
        return RedirectResponse(PlayServer.get_url().rstrip("/") + request.url.path)

    return Starlette(routes=[Route("/{path:path}", redirect)])
