#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : main.py
@desc          : 
@dateTime      : 2020/03/23 08:29:13
@author        : 5km
@contact       : 5km@smslit.cn
'''
import os
import json

import click
from .common import ConfigOperation, ServiceOperation


@click.group()
def cli():
    pass


@click.command()
@click.option(
    '--generate',
    'operation',
    flag_value=ConfigOperation.Generate,
    help='生成配置文件'
)
@click.option(
    '--reset',
    'operation',
    flag_value=ConfigOperation.Reset,
    help='重置所有配置信息，并保存到配置文件'
)
@click.option(
    '--remove',
    'operation',
    flag_value=ConfigOperation.Remove,
    help='删除配置文件'
)
@click.option(
    '--list',
    'operation',
    flag_value=ConfigOperation.List,
    default=True,
    help='列出当前所有配置信息'
)
def config(operation):

    from .common import ConfigOperation
    from app.utilities.config import parser
    from app.models.config import CONFIG_FILE_PATH
    from app.utilities.config import config as app_config

    if operation == ConfigOperation.Generate:
        parser.save()
        click.echo('已经生成配置文件 {}!'.format(CONFIG_FILE_PATH))
    elif operation == ConfigOperation.Reset:
        parser.reset()
        parser.save()
        click.echo('已经重置所有配置，请查阅 {}!'.format(CONFIG_FILE_PATH))
    elif operation == ConfigOperation.Remove:
        if os.path.exists(CONFIG_FILE_PATH):
            os.remove(CONFIG_FILE_PATH)
            click.echo('已经删除配置文件!')
    elif operation == ConfigOperation.List:
        if not os.path.exists(CONFIG_FILE_PATH):
            click.echo(
                '还没有生成配置文件！可执行以下命令生成:\n\n\tpython main.py config --generate')
        config_dict = app_config.dict()
        config_str = json.dumps(
            config_dict,
            indent=4,
            separators=[',', ':'],
            ensure_ascii=False
        )
        config_str = '\n配置如下：\n\n' + config_str.replace('":', '": ') + '\n'
        click.echo(config_str)


@click.command()
@click.option(
    '--inject',
    'operation',
    flag_value=ServiceOperation.Inject,
    help='注入 APP 服务到系统服务'
)
@click.option(
    '--eject',
    'operation',
    flag_value=ServiceOperation.Eject,
    help='从系统服务中弹出 APP 服务'
)
def service(operation):
    from .common import inject_service, eject_service
    from app.utilities.config import config as app_config
    if operation == ServiceOperation.Inject:
        inject_service(app_config)
    elif operation == ServiceOperation.Eject:
        eject_service()


@cli.command()
def clear():
    import os
    from app.utilities.config import ZHYConfigParser
    config = ZHYConfigParser().config
    if os.system('rm -rf {}/*'.format(config.filepath.upload)) == 0:
        click.echo('成功删除上传的图像!')
    if os.system('rm -rf {}/*'.format(config.filepath.result)) == 0:
        click.echo('成功删除分析结果图像!')


cli.add_command(config)
cli.add_command(service)
cli.add_command(clear)

__all__ = [
    'cli'
]
