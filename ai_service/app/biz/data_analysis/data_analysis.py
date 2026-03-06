import json
from app.utilities.config import config
from app.utilities.logging import logger
from app.utilities import datetime_utils
from app.models.data_analysis import DataAnalysisKey
from app.utilities.redis import ZHYRedis


class DataAnalysis:

    def __init__(self):
        self.config = config
        self.redis = ZHYRedis()

    def statistics_upload(self):
        """
        统计上传图片数量
        :return:
        """

        key = DataAnalysisKey.upload_queue
        count = self.redis.llen(key)
        self.redis.delete(key)
        if not count:
            return

        to_day = datetime_utils.prc_today_int()
        time = int(datetime_utils.prcnow().format('YYYYMMDDHH'))

        data = {
            'time': time,
            'count': count,
            'speed': count
        }

        data_json = json.dumps(data)

        l_key = '_'.join([key, str(to_day)])

        self.redis.rpush(l_key, data_json)
        self.redis.expire(l_key, 86400)

        logger.info(f'=======key: {key}, data: {data}=============')

    def statistics_analysis(self):
        """
        统计分析图片数量
        :return:
        """

        key = DataAnalysisKey.complete_queue
        count = self.redis.llen(key)
        self.redis.delete(key)
        if not count:
            return

        to_day = datetime_utils.prc_today_int()
        time = int(datetime_utils.prcnow().format('YYYYMMDDHH'))

        data = {
            'time': time,
            'count': count,
            'speed': count
        }

        data_json = json.dumps(data)

        l_key = '_'.join([key, str(to_day)])

        self.redis.rpush(l_key, data_json)
        self.redis.expire(l_key, 86400)

        logger.info(f'=======key: {key}, data: {data}=============')

    def statistics(self):
        try:
            self.statistics_upload()
            self.statistics_analysis()
        except Exception as e:
            logger.exception(e)


data_analysis_obj = DataAnalysis()
