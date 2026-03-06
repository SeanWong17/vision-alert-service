#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : main.py
@desc          : 
@dateTime      : 2020/04/10 22:28:21
@author        : 5km
@contact       : 5km@smslit.cn
'''

import _thread as thread

from apscheduler.schedulers.background import BackgroundScheduler

from app import create_app
from app.biz.transmission import TransmissionBackstage
from app.utilities.cleaner import check_and_clean
from app.utilities.config import config as app_config
from app.biz.data_analysis.data_analysis import data_analysis_obj

transmission_backstage = TransmissionBackstage.instance()

background_scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
background_scheduler.add_job(
    id='autoclean_job',
    func=check_and_clean,
    trigger='interval',
    seconds=60
)

background_scheduler.add_job(
    id='data_analysis_statistics',
    func=data_analysis_obj.statistics,
    trigger='interval',
    seconds=3600
)

# if app_config.ai.autoclean.enable:
#     background_scheduler.start()

sub_threads = []
# 启动一个线程处理输电图像
sub_threads.append(thread.start_new(transmission_backstage.auto_analyze, ()))

app = create_app(app_config, sub_threads)
