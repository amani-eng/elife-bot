import unittest
from mock import mock, patch
import activity.activity_ScheduleDownstream as activity_module
from activity.activity_ScheduleDownstream import activity_ScheduleDownstream as activity_object
from provider import article
import tests.activity.settings_mock as settings_mock
from tests.activity.classes_mock import FakeLogger, FakeStorageContext
import tests.activity.test_activity_data as activity_test_data


class TestScheduleDownstream(unittest.TestCase):

    def setUp(self):
        fake_logger = FakeLogger()
        self.activity = activity_object(settings_mock, fake_logger, None, None, None)

    @patch.object(article, 'storage_context')
    @patch.object(activity_module, 'storage_context')
    def test_do_activity(self, fake_activity_storage_context, fake_storage_context):
        expected_result = True
        fake_storage_context.return_value = FakeStorageContext()
        fake_activity_storage_context.return_value = FakeStorageContext()
        self.activity.emit_monitor_event = mock.MagicMock()
        # do the activity
        result = self.activity.do_activity(activity_test_data.data_example_before_publish)
        # check assertions
        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    unittest.main()