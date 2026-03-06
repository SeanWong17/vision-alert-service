import unittest


def _runtime_ready() -> bool:
    try:
        import fastapi  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), 'runtime deps not installed')
class PeopleHelpersTest(unittest.TestCase):
    def test_normalize_coordinates_default(self):
        from app.modules.people.service import normalize_coordinates

        self.assertEqual(normalize_coordinates(None), [-1, -1, -1, -1])
        self.assertEqual(normalize_coordinates([1, 2]), [-1, -1, -1, -1])

    def test_normalize_coordinates_valid(self):
        from app.modules.people.service import normalize_coordinates

        self.assertEqual(normalize_coordinates([1, 2, 3, 4]), [1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
