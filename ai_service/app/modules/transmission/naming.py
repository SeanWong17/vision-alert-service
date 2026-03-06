#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os


def position_from_filename(file_name: str) -> str:
    return file_name.split('_')[0] if '_' in file_name else 'other'


def result_image_name(file_name: str, has_alarm: bool) -> str:
    if not has_alarm:
        return file_name
    base, ext = os.path.splitext(file_name)
    return f"{base}_ALARM{ext}"
