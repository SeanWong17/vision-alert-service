#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : cleaner.py
@desc          : 自动清除文件及数据处理
@dateTime      : 2020/5/22 16:6:38
@author        : 5km
@contact       : 5km@smslit.cn
'''

import os
from datetime import datetime

from app.utilities.config import config
from app.utilities.logging import logger


def find_all_files(base):
    '''
    查找指定目录下所有文件
    '''
    for root, dirs, files in os.walk(base):
        for f in files:
            yield os.path.join(root, f)


def check_and_clean():
    expired_seconds = config.ai.autoclean.clean_expired * 60
    now = datetime.now().timestamp()
    files = []
    upload_path = os.path.abspath(config.filepath.upload)
    result_path = os.path.abspath(config.filepath.result)
    logger.info(f'==========Auto Cleaner start===========')
    for f in find_all_files(upload_path):
        files.append(f)
    for f in find_all_files(result_path):
        files.append(f)
    for filepath in files:
        try:
            mtime = os.path.getmtime(filepath)
            if now - mtime >= expired_seconds:
                os.remove(filepath)
                logger.info(
                    'Auto Cleaner -> remove file({}) successfully! '.format(
                        filepath
                    )
                )
        except Exception as e:
            continue
