import unittest


def _runtime_ready() -> bool:
    try:
        import fastapi  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), 'runtime deps not installed')
class TaskParserTest(unittest.TestCase):
    def test_list_input_is_wrapped(self):
        from app.modules.transmission.task_parser import normalize_people_tasks

        payload = [{"id": 1, "params": {"limit": 1}}]
        got = normalize_people_tasks(payload)
        self.assertIn("ultrahigh_people_task", got)
        self.assertEqual(len(got["ultrahigh_people_task"]), 1)

    def test_invalid_coordinate_is_defaulted(self):
        from app.modules.transmission.task_parser import normalize_people_tasks, DEFAULT_COORDINATE

        payload = {"ultrahigh_people_task": [{"id": 1, "params": {"limit": 1}}]}
        got = normalize_people_tasks(payload)
        coord = got["ultrahigh_people_task"][0]["params"]["coordinate"]
        self.assertEqual(coord, DEFAULT_COORDINATE)

    def test_invalid_shape_raises(self):
        from app.modules.transmission.task_parser import normalize_people_tasks
        from app.utilities import exceptions

        with self.assertRaises(exceptions.TransmissionError):
            normalize_people_tasks({"foo": []})


if __name__ == '__main__':
    unittest.main()
