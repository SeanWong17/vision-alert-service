#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json
from typing import Any, Dict

from app.utilities import exceptions


DEFAULT_COORDINATE = [-1, -1, -1, -1]


def normalize_people_tasks(tasks: Any) -> Dict[str, Any]:
    if isinstance(tasks, str):
        tasks = json.loads(tasks)

    if isinstance(tasks, list):
        tasks = {"ultrahigh_people_task": tasks}

    if not isinstance(tasks, dict):
        raise exceptions.TransmissionError(message='tasks format is invalid')

    people_tasks = tasks.get("ultrahigh_people_task")
    if not isinstance(people_tasks, list) or not people_tasks:
        raise exceptions.TransmissionError(message='ultrahigh_people_task is required')

    for task in people_tasks:
        if not isinstance(task, dict):
            raise exceptions.TransmissionError(message='task item format is invalid')
        params = task.setdefault("params", {})
        coordinate = params.get("coordinate")
        if not isinstance(coordinate, list) or len(coordinate) < 4:
            params["coordinate"] = list(DEFAULT_COORDINATE)

    return {"ultrahigh_people_task": people_tasks}
