# coding=utf-8

import copy
import unittest
from mock import patch
from ddt import ddt, data
import provider.digest_provider as digest_provider
import provider.lax_provider as lax_provider
from activity.activity_IngestDigestToEndpoint import (
    activity_IngestDigestToEndpoint as activity_object)
import tests.activity.settings_mock as settings_mock
from tests.activity.classes_mock import FakeLogger, FakeStorageContext, FakeSession
import tests.activity.test_activity_data as test_activity_data


def session_data(test_data):
    "return the session data for testing with values rewritten if specified"
    session_data = copy.copy(test_activity_data.session_example)
    for value in ['article_id', 'run_type', 'status', 'version']:
        if test_data.get(value):
            session_data[value] = test_data.get(value)
    return session_data


@ddt
class TestIngestDigestToEndpoint(unittest.TestCase):

    def setUp(self):
        fake_logger = FakeLogger()
        self.activity = activity_object(settings_mock, fake_logger, None, None, None)

    def tearDown(self):
        # clean the temporary directory
        self.activity.clean_tmp_dir()

    @patch.object(lax_provider, 'article_highest_version')
    @patch.object(digest_provider, 'storage_context')
    @patch('activity.activity_IngestDigestToEndpoint.get_session')
    @patch.object(activity_object, 'emit_monitor_event')
    @patch('activity.activity_IngestDigestToEndpoint.storage_context')
    @data(
        {
            "comment": "article with no digest files",
            "article_id": '00000',
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_approve_status": True,
            "expected_download_status": None
        },
        {
            "comment": "digest files with version greater than lax highest version",
            "bucket_resources": ["s3://bucket/digests/outbox/99999/digest-99999.docx",
                                 "s3://bucket/digests/outbox/99999/digest-99999.jpg"],
            "article_id": '99999',
            "status": 'vor',
            'version': '2',
            "lax_highest_version": '1',
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_approve_status": True,
            "expected_download_status": True
        },
        {
            "comment": "poa article has no digest",
            "article_id": '99999',
            "status": 'poa',
            'version': '1',
            "lax_highest_version": '1',
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_approve_status": False,
            "expected_download_status": None
        },
        {
            "comment": "silent correction of a previous version",
            "article_id": '99999',
            "run_type": "silent-correction",
            "status": 'vor',
            'version': '1',
            "lax_highest_version": '2',
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_approve_status": False,
            "expected_download_status": None
        },
        {
            "comment": "silent correction exception for bad version number",
            "article_id": '99999',
            "run_type": "silent-correction",
            "status": 'vor',
            "lax_highest_version": None,
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_approve_status": False,
            "expected_download_status": None
        },
    )
    def test_do_activity(self, test_data, fake_storage_context, fake_emit,
                         fake_session, fake_provider_storage_context,
                         fake_highest_version):
        # copy files into the input directory using the storage context
        named_fake_storage_context = FakeStorageContext()
        named_fake_storage_context.resources = test_data.get('bucket_resources')
        fake_storage_context.return_value = named_fake_storage_context
        fake_highest_version.return_value = test_data.get('lax_highest_version')
        session_test_data = session_data(test_data)
        fake_session.return_value = FakeSession(session_test_data)
        fake_provider_storage_context.return_value = FakeStorageContext()
        activity_data = test_activity_data.data_example_before_publish
        # do the activity
        result = self.activity.do_activity(activity_data)
        # check assertions
        self.assertEqual(result, test_data.get("expected_result"),
                         'failed in {comment}'.format(comment=test_data.get("comment")))
        self.assertEqual(self.activity.approve_status, test_data.get("expected_approve_status"),
                         'failed in {comment}'.format(comment=test_data.get("comment")))
        self.assertEqual(self.activity.download_status, test_data.get("expected_download_status"),
                         'failed in {comment}'.format(comment=test_data.get("comment")))

if __name__ == '__main__':
    unittest.main()
