#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : main.py
@desc          :
@dateTime      : 2020/03/23 08:29:13
@author        : 5km
@contact       : 5km@smslit.cn
'''
import click
import uvicorn

from app.main import app
from app.utilities.cli import cli


@click.command()
@click.option(
    '--host',
    type=str,
    default='0.0.0.0',
    help='指定服务启动 host'
)
@click.option(
    '--port',
    type=int,
    default=8011,
    help='指定服务启动 port'
)
def run(host, port):
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli.add_command(run)
    cli()
