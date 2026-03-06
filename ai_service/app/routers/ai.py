#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import cv2
import json
import time
import threading
import os.path as op
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from app.utilities.logging import logger
from app.utilities.config import ZHYConfigParser
from app.utilities.config import config as app_config

json_path = os.path.join(app_config.filepath.config_file, 'config.json')
if os.path.exists(json_path):
    with open(json_path, 'r') as f:
        config_json = json.load(f)
else:
    config_json = {}

try:
    if config_json.get("water_task", {}).get("ultrahigh_people_task", True):
        from app.water_post_process.General_DrowingPrevent.cal_drowning_prevent import drowing_prevent
    else:
        drowing_prevent = None
except Exception:
    drowing_prevent = None
    logger.exception("启用 people 模型遇到问题")

lock = threading.Lock()
config = ZHYConfigParser().config


def delete_image_files_older_by_days(directory: str, days: int = 15):
    last_run_file = os.path.join(directory, ".last_run")

    if os.path.exists(last_run_file):
        with open(last_run_file, 'r') as file:
            last_run_date = file.read()
        if last_run_date == datetime.now().strftime("%Y-%m-%d"):
            return
        with open(last_run_file, 'w') as file:
            file.write(datetime.now().strftime("%Y-%m-%d"))
    else:
        with open(last_run_file, 'w') as file:
            file.write(datetime.now().strftime("%Y-%m-%d"))

    now = datetime.now()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if now - file_mod_time > timedelta(days=days):
                        os.remove(file_path)


def _parse_people_tasks(people_tasks: Any) -> List[Dict[str, Any]]:
    if isinstance(people_tasks, str):
        people_tasks = json.loads(people_tasks)

    parsed_tasks: List[Dict[str, Any]] = []
    for task in people_tasks:
        if isinstance(task, str):
            parsed_tasks.append(json.loads(task))
        else:
            parsed_tasks.append(task)
    return parsed_tasks


def _normalize_coordinates(coordinates: Any):
    if not isinstance(coordinates, list) or len(coordinates) < 4:
        return [-1, -1, -1, -1]
    return coordinates


def analysis_water_all(file_name: str, tasks: Dict[str, Any], file_path: str, save_res_img: bool = True):
    t1 = time.time()

    people_tasks = tasks.get("ultrahigh_people_task") if isinstance(tasks, dict) else None
    if not people_tasks:
        logger.warning("tasks 中未找到 ultrahigh_people_task")
        return []

    parsed_tasks = _parse_people_tasks(people_tasks)
    coordinates = _normalize_coordinates(parsed_tasks[0].get("params", {}).get("coordinate") if parsed_tasks else None)

    result, raw_det_res, res_image = [], [], None

    lock.acquire()
    try:
        result, res_image, raw_det_res = analysis_water_people(parsed_tasks, file_path, coordinates)
    finally:
        lock.release()

    result_path = op.join(config.filepath.result, 'ultrahigh_people_task')
    if len(raw_det_res) > 0:
        file_base, file_ext = os.path.splitext(file_name)
        file_name = f"{file_base}_ALARM{file_ext}"

    if save_res_img and res_image is not None:
        position = file_name.split('_')[0] if '_' in file_name else 'other'
        save_path = os.path.join(result_path, position)
        if not os.path.exists(save_path):
            os.makedirs(save_path)

        save_img_path = os.path.join(save_path, file_name)
        cv2.imwrite(save_img_path, res_image)

        delete_image_files_older_by_days(config.filepath.result)
        delete_image_files_older_by_days(config.filepath.upload)

    logger.info(f"-----people analysis time：{time.time()-t1}----------")
    return result


def analysis_water_people(people_tasks: List[Dict[str, Any]], file_path: str, coordinates: Any):
    logger.info(f"----------people_tasks----------{people_tasks}")
    results, res_image, raw_det_res = [], [], []

    try:
        if drowing_prevent is None:
            raise RuntimeError("people model is disabled or failed to load")

        coordinates = _normalize_coordinates(coordinates)
        det_result, res_image, water_color_dict, shoreline_points, raw_det_res = drowing_prevent.cal_drowing_judgement(file_path, coordinates)

        detect_objects = [{"water_color_dict": water_color_dict}]

        if det_result:
            for obj in det_result:
                xmin, ymin, xmax, ymax, score, tag_name = obj
                detect_objects.append({
                    "coordinate": [xmin, ymin, xmax, ymax],
                    "score": score,
                    "tagName": tag_name,
                })

        res_shoreline_points = [[list(tup) for tup in sublist] for sublist in shoreline_points]
        detect_objects.append({"shoreline_points": res_shoreline_points})

        for task in people_tasks:
            task_limit = int(task.get("params", {}).get("limit", 0))
            reserved = "1" if len(detect_objects) > task_limit else "0"
            result_item = dict(task)
            result_item["reserved"] = reserved
            result_item["detail"] = detect_objects
            results.append(result_item)

        logger.info(f"----------results----------{results}")
        return results, res_image, raw_det_res
    except Exception as e:
        logger.exception(e)
        return results, res_image, raw_det_res
