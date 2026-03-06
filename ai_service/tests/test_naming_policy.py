import unittest


def _runtime_ready() -> bool:
    try:
        import fastapi  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_runtime_ready(), 'runtime deps not installed')
class NamingPolicyTest(unittest.TestCase):
    def test_position_from_filename(self):
        from app.modules.transmission.naming import position_from_filename

        self.assertEqual(position_from_filename('A100_20250101.jpg'), 'A100')
        self.assertEqual(position_from_filename('nounderscore.jpg'), 'other')

    def test_result_image_name(self):
        from app.modules.transmission.naming import result_image_name

        self.assertEqual(result_image_name('a.jpg', False), 'a.jpg')
        self.assertEqual(result_image_name('a.jpg', True), 'a_ALARM.jpg')


if __name__ == '__main__':
    unittest.main()
