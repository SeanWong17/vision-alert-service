"""
@fileName      : service_mixins.py
@desc          :
@dateTime      : 2020/6/17 10:30：00
@author        : 631961895
@contact       : 631961895
"""


class Singletion:
    _instance = None

    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance
