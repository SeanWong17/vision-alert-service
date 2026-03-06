#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json
import os
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, List

import cv2

from app.pipeline.people.engine import people_engine
from app.utilities.config import ZHYConfigParser
from app.utilities.logging import logger


_lock = Lock()
_config = ZHYConfigParser().config


def normalize_coordinates(coordinates: Any):
    if not isinstance(coordinates, list) or len(coordinates) < 4:
        return [-1, -1, -1, -1]
    return coordinates


def parse_people_tasks(people_tasks: Any) -> List[Dict[str, Any]]:
    if isinstance(people_tasks, str):
        people_tasks = json.loads(people_tasks)

    parsed_tasks: List[Dict[str, Any]] = []
    for task in people_tasks:
        if isinstance(task, str):
            parsed_tasks.append(json.loads(task))
        else:
            parsed_tasks.append(task)
    return parsed_tasks


def cleanup_old_images(directory: str, days: int = 15):
    last_run_file = os.path.join(directory, '.last_run')

    if os.path.exists(last_run_file):
        with open(last_run_file, 'r') as file:
            last_run_date = file.read()
        if last_run_date == datetime.now().strftime('%Y-%m-%d'):
            return
        with open(last_run_file, 'w') as file:
            file.write(datetime.now().strftime('%Y-%m-%d'))
    else:
        with open(last_run_file, 'w') as file:
            file.write(datetime.now().strftime('%Y-%m-%d'))

    now = datetime.now()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if now - file_mod_time > timedelta(days=days):
                        os.remove(file_path)


def run_people_sync_inference(people_tasks: List[Dict[str, Any]], file_path: str, coordinates: Any):
    logger.info(f'people tasks: {people_tasks}')
    results, result_image, raw_det_res = [], [], []

    try:
        coordinates = normalize_coordinates(coordinates)
        det_result, result_image, water_color_dict, shoreline_points, raw_det_res = people_engine.analyze_image(file_path, coordinates)

        detect_objects = [{"water_color_dict": water_color_dict}]

        if det_result:
            for obj in det_result:
                xmin, ymin, xmax, ymax, score, tag_name = obj
                detect_objects.append(
                    {
                        'coordinate': [xmin, ymin, xmax, ymax],
                        'score': score,
                        'tagName': tag_name,
                    }
                )

        shoreline = [[list(point) for point in sublist] for sublist in shoreline_points]
        detect_objects.append({'shoreline_points': shoreline})

        for task in people_tasks:
            task_limit = int(task.get('params', {}).get('limit', 0))
            reserved = '1' if len(detect_objects) > task_limit else '0'
            result_item = dict(task)
            result_item['reserved'] = reserved
            result_item['detail'] = detect_objects
            results.append(result_item)

        return results, result_image, raw_det_res
    except Exception as e:
        logger.exception(e)
        return results, result_image, raw_det_res


def run_people_async_pipeline(file_name: str, tasks: Dict[str, Any], file_path: str, save_result_image: bool = True):
    start_at = time.time()

    people_tasks = tasks.get('ultrahigh_people_task') if isinstance(tasks, dict) else None
    if not people_tasks:
        logger.warning('tasks 中未找到 ultrahigh_people_task')
        return []

    parsed_tasks = parse_people_tasks(people_tasks)
    coordinates = normalize_coordinates(parsed_tasks[0].get('params', {}).get('coordinate') if parsed_tasks else None)

    results, raw_det_res, result_image = [], [], None
    with _lock:
        results, result_image, raw_det_res = run_people_sync_inference(parsed_tasks, file_path, coordinates)

    if save_result_image and result_image is not None:
        from app.modules.transmission.naming import position_from_filename, result_image_name

        result_path = os.path.join(_config.filepath.result, 'ultrahigh_people_task')
        save_name = result_image_name(file_name, has_alarm=bool(raw_det_res))
        save_path = os.path.join(result_path, position_from_filename(save_name))
        os.makedirs(save_path, exist_ok=True)
        cv2.imwrite(os.path.join(save_path, save_name), result_image)

        cleanup_old_images(_config.filepath.result)
        cleanup_old_images(_config.filepath.upload)

    logger.info(f'people async pipeline elapsed={time.time() - start_at}')
    return results
