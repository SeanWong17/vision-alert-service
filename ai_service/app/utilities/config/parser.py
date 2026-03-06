#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : parser.py
@desc          : 配置解析
@dateTime      : 2020/03/26 14:15:37
@author        : 5km
@contact       : 5km@smslit.cn
'''

# import modules here
import os
import json

from app.models.config import CONFIG_FILE_PATH, Config


class ZHYConfigParser:

    __config: Config = None

    def __init__(self, path: str = CONFIG_FILE_PATH):
        super().__init__()
        if ZHYConfigParser.__config is not None:
            return
        if not os.path.exists(path):
            ZHYConfigParser.__config = Config()
            return
        try:
            with open(path, 'r') as fp:
                config_dict = json.load(fp=fp)
                ZHYConfigParser.__config = Config(**config_dict)
        except Exception as e:
            print('load config from file failed! error: {}'.format(e))
            ZHYConfigParser.__config = Config()

    def save(self, path: str = CONFIG_FILE_PATH):
        dir_path, filename = os.path.split(path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(path, 'w') as fp:
            config_dict = self.__config.dict()
            config_str = json.dumps(
                config_dict,
                indent=4,
                separators=[',', ':'],
                ensure_ascii=False
            )
            config_str = config_str.replace('":', '": ') + '\n'
            fp.write(config_str)

    def reset(self):
        ZHYConfigParser.__config = Config()

    def read(self, path: str = CONFIG_FILE_PATH):
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r') as fp:
                config_dict = json.load(fp=fp)
                ZHYConfigParser.__config = Config(**config_dict)
        except Exception as e:
            print('load config from file failed! error: {}'.format(e))

    def __str__(self):
        return self.__config.__str__()

    @property
    def config(self):
        return self.__config
