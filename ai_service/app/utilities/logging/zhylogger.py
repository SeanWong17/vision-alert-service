#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : zhylogger.py
@desc          : 
@dateTime      : 2020/03/25 10:01:40
@author        : 5km
@contact       : 5km@smslit.cn
'''

import os
from logging.handlers import TimedRotatingFileHandler
from logging import getLogger, INFO, Formatter, StreamHandler, Logger

LOG_FILES_DIR = os.path.join(
    os.path.expanduser('~'),
    '.zhyai/log'
)


def init_logger(
    log_dir=LOG_FILES_DIR,
    log_name='zhyai.log',
    log_level=INFO,
    disable_stream=False
) -> Logger:
    """

    Keyword Arguments:
        log_dir {str} -- 日志存储目录 (default: {LOG_FILES_DIR})
        log_name {str} -- 日志文件默认名称 (default: {'zhyai.log'})
        log_level {Union[int, str]} -- 日志等级 (default: {INFO})
        disable_stream {bool} -- 是否禁用日志打印到标准输出 (default: {False})

    Returns:
        [Logging.Logger] -- logger 对象
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = Formatter(
        '[%(asctime)s][%(filename)s:%(lineno)d][%(levelname)s] - %(message)s')

    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, log_name),
        when='H',
        interval=1,
        backupCount=48,
        encoding='UTF-8',
        delay=False,
        utc=False
    )
    file_handler.setFormatter(formatter)

    logger = getLogger(log_name)

    # 防止重复初始化，清空原有 handler，清空之前先关闭
    if logger.handlers:
        [handler.close() for handler in logger.handlers]
        logger.handlers.pop()

    logger.addHandler(file_handler)

    if not disable_stream:
        stream_handler = StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.setLevel(log_level)

    return logger
