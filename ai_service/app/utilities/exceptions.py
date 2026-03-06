"""
@fileName      : exceptiions.py
@desc          : 常用错误
@dateTime      : 2020/6/17 10:30：00
@author        : 631961895
@contact       : 631961895
"""
from typing import Any

from starlette.status import HTTP_400_BAD_REQUEST
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.utilities.logging import logger


class ApiError(StarletteHTTPException):
    status_code = HTTP_400_BAD_REQUEST
    detail = message = 'API请求失败'

    def __init__(
        self, status_code: int = None, message: Any = None
    ) -> None:
        if status_code:
            self.status_code = status_code
        if message is not None:
            self.detail = self.message = message
        logger.error(f'=====status_code: {status_code}, message: {message}=======')


class RpcRuntimeError(StarletteHTTPException):
    status_code = HTTP_400_BAD_REQUEST
    detail = message = 'RPC请求失败'

    def __init__(
        self, status_code: int = None, message: Any = None
    ) -> None:
        if status_code:
            self.status_code = status_code
        if message is not None:
            self.detail = self.message = message
        logger.error(f'=====status_code: {status_code}, message: {message}=======')


class TransmissionError(Exception):
    code = -1
    message = 'api request fail!'

    def __init__(
        self, code: int = None, message: Any = None
    ) -> None:
        if code:
            self.code = code
        if message is not None:
            self.message = message
        logger.error(f'=====status_code: {code}, message: {message}=======')
