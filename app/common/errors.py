"""核心异常定义模块。"""

from __future__ import annotations

from typing import Any

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_400_BAD_REQUEST


class ApiError(StarletteHTTPException):
    """面向 HTTP 层的错误，直接映射为指定状态码。"""

    def __init__(self, status_code: int = HTTP_400_BAD_REQUEST, message: Any = "api request failed"):
        """构造 API 错误对象。"""

        super().__init__(status_code=status_code, detail=message)
        self.message = message


class AlertingError(Exception):
    """告警领域异常，包含业务错误码与错误信息。"""

    def __init__(self, code: int = -1, message: Any = "request failed"):
        """构造领域错误对象。"""

        super().__init__(str(message))
        self.code = code
        self.message = message
