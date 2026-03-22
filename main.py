"""命令行启动入口。"""

from __future__ import annotations

import click
import uvicorn


@click.command()
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8011, show_default=True, type=int)
@click.option("--workers", default=1, show_default=True, type=int, help="uvicorn worker 进程数")
def run(host: str, port: int, workers: int) -> None:
    """启动 Web 服务。"""

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=workers,
        timeout_graceful_shutdown=15,
    )


if __name__ == "__main__":
    run()
