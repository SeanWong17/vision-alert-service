#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : __init__.py
@desc          : 
@dateTime      : 2020/03/26 13:40:00
@author        : 5km
@contact       : 5km@smslit.cn
'''

# import modules here
from .parser import ZHYConfigParser

parser = ZHYConfigParser()
config = parser.config

__all__ = [
    'config',
    'parser'
]
