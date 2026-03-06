#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : cli.py
@desc          : 
@dateTime      : 2020/03/31 12:25:50
@author        : 5km
@contact       : 5km@smslit.cn
'''
import os
import shutil
import getpass
from enum import Enum

import click

from app.models.config import Config


class ConfigOperation(int, Enum):
    Generate = 0
    Reset = 1
    List = 2
    Remove = -1


class ServiceOperation(int, Enum):
    Inject = 0
    Eject = -1


# $0 -> 用户
# $1 -> 用户组
# $2 -> 工程目录绝对路径
# $3 -> uvicorn 的绝对路径
# $4 -> 部署服务的 Host
# $5 -> 部署服务的端口
SERVICE_STR_FORMATTER = '''[Unit]
Description = zhy_ai_service
After = network.target

[Service]
User = {}
Group = {}

WorkingDirectory = {}
ExecStart = {} --host {} --port {} --workers {} app.main:app
Type = simple

[Install]
WantedBy = multi-user.target
'''

SERVICE_TIP_STR = '''
现在使用 systemctl 或 service 启停服务：

  启动
    sudo systemctl start zhyai 或
    sudo service zhyai start
  停止
    sudo systemctl stop zhyai 或
    sudo service zhyai stop
'''


def inject_service(config: Config):
    click.echo('此操作会将服务文件注入 systemd!')
    pwd = os.getcwd()
    python_path = shutil.which('uvicorn')
    user = getpass.getuser()
    group = shutil.getgrnam(user)[0]

    host = config.server.host
    port = config.server.port

    try:
        workers = int(input('部署 workers 个数(默认 4): '))
    except Exception as e:
        workers = 4
        pass

    service_str = SERVICE_STR_FORMATTER.format(
        user,
        group,
        pwd,
        python_path,
        host,
        port,
        workers
    )
    print(service_str)
    if os.system('sudo systemctl stop zhyai') == 0:
        click.echo('检测到已有此服务，已经停止服务！')
    with open('zhyai.service', 'w') as f:
        f.write(service_str)
    if os.system('sudo mv zhyai.service /etc/systemd/system/') == 0:
        click.echo('服务文件 zhyai.service 注入成功！')
    if os.system('sudo systemctl daemon-reload') == 0:
        click.echo('系统服务重载成功！')
        click.echo(SERVICE_TIP_STR)


def eject_service():
    service_path = '/etc/systemd/system/zhyai.service'
    if not os.path.exists(service_path):
        click.echo('未注入过 APP 服务到系统服务!')
        return
    if os.system('sudo rm -f {}'.format(service_path)) == 0:
        click.echo('已删除 APP 服务文件!')
    if os.system('sudo systemctl daemon-reload') == 0:
        click.echo('已弹出 APP 服务文件!')
