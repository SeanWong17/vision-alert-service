#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@fileName: datetime_utils.py
@desc:
@dateTime: 2020/7/1 15:58
@author: 631961895
@contact: 631961895
"""

import arrow
from functools import partial

now = arrow.now

utcnow = arrow.utcnow

prc_tz = 'PRC'  # MUST uppercase!


def to_prc(d):
    return arrow.get(d).to(prc_tz)


def prcnow():
    return arrow.now(prc_tz)


def prctoday():
    return prcnow().date()


def span_range(start, end, frame, tz=None):
    return arrow.Arrow.span_range(frame, start, end, tz=tz)


def time_range(start, end, frame, tz=None):
    return arrow.Arrow.range(frame, start, end, tz=tz)


span_range_by_minute = partial(span_range, frame='minute')
span_range_by_hour = partial(span_range, frame='hour')
span_range_by_day = partial(span_range, frame='day')

prc_span_range_by_minute = partial(span_range, frame='minute', tz=prc_tz)
prc_span_range_by_hour = partial(span_range, frame='hour', tz=prc_tz)
prc_span_range_by_day = partial(span_range, frame='day', tz=prc_tz)

prc_range_by_minute = partial(time_range, frame='minute', tz=prc_tz)
prc_range_by_hour = partial(time_range, frame='hour', tz=prc_tz)
prc_range_by_day = partial(time_range, frame='day', tz=prc_tz)


def utc_today_int():
    return int(arrow.utcnow().format('YYYYMMDD'))


def prc_today_int():
    return int(prcnow().format('YYYYMMDD'))


def month_int():
    return int(prcnow().format('YYYYMM'))


def prc_today_datetime_format():
    return prcnow().format('YYYYMMDD-HH_mm_ss')


def prc_yesterday_int():
    return int(prcnow().replace(days=-1).format('YYYYMMDD'))


def prc_next_days_int(days=1):
    return int(prcnow().replace(days=days).format('YYYYMMDD'))


def utc_from_today_int(date_int):
    return arrow.Arrow.strptime(str(date_int), '%Y%m%d')


def prc_from_today_int(date_int):
    return arrow.Arrow.strptime(str(date_int), '%Y%m%d', tzinfo=prc_tz)


def timestamp(is_float=False):
    if is_float:
        return arrow.utcnow().float_timestamp
    else:
        return arrow.utcnow().timestamp


def utc_from_timestamp(ts):
    return arrow.Arrow.utcfromtimestamp(ts)


def prc_from_timestamp(ts):
    return arrow.Arrow.fromtimestamp(ts, prc_tz)


def format_iso8601(d):
    return arrow.Arrow.fromdatetime(d).isoformat()


def from_iso8601(s):
    return arrow.get(s).naive


def format_date_int(d):
    a = arrow.get(d)
    return int(a.format('YYYYMMDD'))


def prc_format_date_int(d):
    a = arrow.get(d)
    return int(a.to(prc_tz).format('YYYYMMDD'))


def datetime_int(arrow_datetime):
    """compatible, alias of format_date_int

    :param arrow_datetime:
    :type arrow_datetime:
    :return:
    :rtype:
    """
    return format_date_int(arrow_datetime)


def next_days(days=1, from_dt=None):
    """Next days future arrow datatime

    :param days:
    :type days:
    :param from_dt:
    :type from_dt:
    :return:
    :rtype: Arrow
    """
    if not from_dt:
        from_dt = arrow.utcnow()
    else:
        from_dt = arrow.get(from_dt)
    to_dt = from_dt.replace(days=days)
    return to_dt


def prc_day_range(day_int):
    """将day int转换为当日的时间查询范围

        >>> prc_day_range(20170524)
        (<Arrow [2017-05-24T00:00:00+08:00]>,
            <Arrow [2017-05-24T23:59:59.999999+08:00]>)

    :param day:
    :type day: int
    :return:
    :rtype:
    """
    return prc_from_today_int(day_int).span('day')


MINUTE = 60
HOUR = MINUTE * 60
DAY = HOUR * 24

_all_chunks = (
    (60 * 60 * 24 * 365, u'年'),
    (60 * 60 * 24 * 30, u'月'),
    (60 * 60 * 24 * 7, u'周'),
    (60 * 60 * 24, u'天'),
    (60 * 60, u'小时'),
    (60, u'分钟')
)

_day_chunks = (
    (60 * 60 * 24, u'天'),
    (60 * 60, u'小时'),
    (60, u'分钟')
)


def from_prc_datetime_str(s, format='YYYY-MM-DD HH:mm:ss'):
    return arrow.get(s, format, tzinfo=prc_tz)
