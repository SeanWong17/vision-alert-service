#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@fileName      : zhyredis.py
@desc          : zhyredis 包
@dateTime      : 2020/5/19 17:6:15
@author        : 5km
@contact       : 5km@smslit.cn
'''

from redis.client import PubSub
from redis import Redis, ConnectionPool

from app.utilities.config import config


class ZHYRedis(Redis):
    pool: ConnectionPool = None

    def __init__(
            self,
            host=None,
            port=None,
            db=None,
            password=None,
            socket_timeout=None,
            socket_connect_timeout=None,
            socket_keepalive=None,
            socket_keepalive_options=None,
            connection_pool=None,
            unix_socket_path=None,
            encoding='utf-8',
            encoding_errors='strict',
            charset=None,
            errors=None,
            decode_responses=True,
            retry_on_timeout=False,
            ssl=False,
            ssl_keyfile=None,
            ssl_certfile=None,
            ssl_cert_reqs='required',
            ssl_ca_certs=None,
            ssl_check_hostname=False,
            max_connections=None,
            single_connection_client=False,
            health_check_interval=0,
            client_name=None,
            username=None
    ):
        if host is None:
            host = config.redis.host
        if port is None:
            port = config.redis.port
        if db is None:
            db = config.redis.database
        if password is None:
            password = config.redis.password

        if self.pool == None:
            ZHYRedis.pool = ZHYRedis.get_conn_pool(
                host=host,
                port=port,
                password=password,
                db=db,
                encoding=encoding,
                decode_responses=decode_responses,
            )
        super().__init__(
            host=host,
            port=port,
            db=db,
            password=password,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            socket_keepalive=socket_keepalive,
            socket_keepalive_options=socket_keepalive_options,
            connection_pool=self.pool,
            unix_socket_path=unix_socket_path,
            encoding=encoding,
            encoding_errors=encoding_errors,
            charset=charset,
            errors=errors,
            decode_responses=decode_responses,
            retry_on_timeout=retry_on_timeout,
            ssl=ssl, ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            ssl_cert_reqs=ssl_cert_reqs,
            ssl_ca_certs=ssl_ca_certs,
            ssl_check_hostname=ssl_check_hostname,
            max_connections=max_connections,
            single_connection_client=single_connection_client,
            health_check_interval=health_check_interval,
            client_name=client_name,
            username=username
        )
        self.ps: PubSub = self.pubsub(ignore_subscribe_messages=True)

    @staticmethod
    def get_conn_pool(
            host='localhost',
            port=6379,
            password=None,
            db=0,
            encoding='utf-8',
            decode_responses=True
    ) -> ConnectionPool:
        return ConnectionPool(
            host=host,
            port=port,
            password=password,
            db=db,
            encoding=encoding,
            decode_responses=decode_responses
        )

    def subscribe(self, *args, **kwargs):
        return self.ps.subscribe(*args, **kwargs)

    def unsubscribe(self, *args):
        return self.ps.unsubscribe(*args)

    def get_message(self, ignore_subscribe_messages=True, timeout=0):
        return self.ps.get_message(
            ignore_subscribe_messages=ignore_subscribe_messages,
            timeout=timeout
        )
