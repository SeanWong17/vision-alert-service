from enum import Enum


class DataAnalysisKey(str, Enum):
    # 上传队列
    upload_queue = "data_analysis_upload"
    # 分析队列
    complete_queue = "data_analysis_complete"
