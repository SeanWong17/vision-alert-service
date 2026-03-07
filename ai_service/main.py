"""命令行启动入口。"""

from __future__ import annotations

import click
import uvicorn


@click.command()
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8011, show_default=True, type=int)
def run(host: str, port: int) -> None:
    """启动 Web 服务。"""

    uvicorn.run("app.main:app", host=host, port=port)


if __name__ == "__main__":
    run()
