#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : __init__.py
@desc          : 
@dateTime      : 2020/03/20 13:38:37
@author        : 5km
@contact       : 5km@smslit.cn
'''

# import modules here
from .zhylogger import init_logger
from app.utilities.config import ZHYConfigParser

__config = ZHYConfigParser().config

logger = init_logger(log_dir=__config.filepath.log)
elk_logger = init_logger(log_dir=__config.filepath.log, log_name='zhyai_elk.log')
filter_logger = init_logger(log_dir=__config.filepath.log, log_name='zhyai_filter.log')
es_logger = init_logger(log_dir=__config.filepath.log, log_name='zhyai_es.log')
