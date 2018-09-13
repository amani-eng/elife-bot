# coding=utf-8

import os
import json
import copy
import unittest
from mock import patch
from ddt import ddt, data
import provider.digest_provider as digest_provider
import provider.article as article
import provider.lax_provider as lax_provider
from activity.activity_IngestDigestToEndpoint import (
    activity_IngestDigestToEndpoint as activity_object)
from tests import read_fixture
import tests.activity.settings_mock as settings_mock
from tests.activity.classes_mock import FakeLogger, FakeStorageContext, FakeSession, FakeResponse
import tests.activity.test_activity_data as test_activity_data


def session_data(test_data):
    "return the session data for testing with values rewritten if specified"
    session_data = copy.copy(test_activity_data.session_example)
    for value in ['article_id', 'run_type', 'status', 'version', 'expanded_folder']:
        if test_data.get(value):
            session_data[value] = test_data.get(value)
    return session_data


IMAGE_JSON = {"width": 1, "height": 1}


RELATED_DATA = [{
    'id': '99999',
    'type': 'research-article',
    'status': 'vor',
    'version': 1,
    'doi': '10.7554/eLife.99999',
    'authorLine': 'Anonymous et al.',
    'title': 'A research article related to the digest',
    'stage': 'published',
    'published': '2018-06-04T00:00:00Z',
    'statusDate': '2018-06-04T00:00:00Z',
    'volume': 7,
    'elocationId': 'e99999'}]


@ddt
class TestIngestDigestToEndpoint(unittest.TestCase):

    def setUp(self):
        fake_logger = FakeLogger()
        self.activity = activity_object(settings_mock, fake_logger, None, None, None)

    def tearDown(self):
        # clean the temporary directory
        self.activity.clean_tmp_dir()

    @patch('activity.activity_IngestDigestToEndpoint.json_output.requests.get')
    @patch.object(article, 'storage_context')
    @patch.object(lax_provider, 'article_json')
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
            "bucket_resources": ["elife-15747-v2.xml"],
            "expanded_folder": "digests",
            "article_id": '99999',
            "status": 'vor',
            'version': '2',
            "lax_highest_version": '1',
            "article_json": RELATED_DATA[0],
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_approve_status": True,
            "expected_download_status": True,
            "expected_docx_file": "digest-99999.docx",
            "expected_jats_file": "elife-15747-v2.xml",
            "expected_json_contains": [
                u'"title": "Fishing for errors in the\u00a0tests"',
                "Microbes live in us and on us",
                u'"relatedContent": [{"type": "research-article"'
                ]
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
                         fake_highest_version, fake_article_json,
                         fake_article_storage_context, fake_get):
        # copy files into the input directory using the storage context
        named_fake_storage_context = FakeStorageContext()
        if test_data.get('bucket_resources'):
            named_fake_storage_context.resources = test_data.get('bucket_resources')
        fake_article_storage_context.return_value = named_fake_storage_context
        fake_storage_context.return_value = FakeStorageContext()
        session_test_data = session_data(test_data)
        fake_session.return_value = FakeSession(session_test_data)
        fake_highest_version.return_value = test_data.get('lax_highest_version')
        fake_article_json.return_value = 200, test_data.get('article_json')
        fake_provider_storage_context.return_value = FakeStorageContext()
        fake_get.return_value = FakeResponse(200, IMAGE_JSON)
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
        if self.activity.values.get("docx_file"):
            expected_docx_file = (os.path.join(self.activity.input_dir,
                                               test_data.get("expected_docx_file")))
            self.assertEqual(self.activity.values.get("docx_file"), expected_docx_file,
                             'failed in {comment}'.format(comment=test_data.get("comment")))
        if self.activity.values.get("jats_file"):
            expected_jats_file = (os.path.join(self.activity.temp_dir,
                                               test_data.get("expected_jats_file")))
            self.assertEqual(self.activity.values.get("jats_file"), expected_jats_file,
                             'failed in {comment}'.format(comment=test_data.get("comment")))
        if self.activity.values.get("json_content") and test_data.get("expected_json_contains"):
            json_string = json.dumps(self.activity.values.get("json_content"))
            for expected in test_data.get("expected_json_contains"):
                self.assertTrue(
                    (expected in json_string, 'failed in json_content in {comment}'.format(
                        comment=test_data.get("comment"))))

    @patch('activity.activity_IngestDigestToEndpoint.json_output.requests.get')
    @data(
        {
            "comment": "Minimal json output of digest only",
            "docx_file": "tests/files_source/digests/outbox/99999/digest-99999.docx",
            "image_file": None,
            "jats_file": None,
            "related": None,
            "expected_json_file": "json_content_99999_minimal.py"
        },
        {
            "comment": "Basic json output including an image file",
            "docx_file": "tests/files_source/digests/outbox/99999/digest-99999.docx",
            "image_file": "digest-99999.jpg",
            "jats_file": None,
            "related": None,
            "expected_json_file": "json_content_99999_basic.py"
        },
        {
            "comment": "JSON output with image file and JATS paragraph replacements",
            "docx_file": "tests/files_source/digests/outbox/99999/digest-99999.docx",
            "image_file": "digest-99999.jpg",
            "jats_file": "tests/test_data/elife-15747-v2.xml",
            "related": None,
            "expected_json_file": "json_content_99999_jats.py"
        },
        {
            "comment": "JSON output from all possible source data",
            "docx_file": "tests/files_source/digests/outbox/99999/digest-99999.docx",
            "image_file": "digest-99999.jpg",
            "jats_file": "tests/test_data/elife-15747-v2.xml",
            "related": RELATED_DATA,
            "expected_json_file": "json_content_99999_full.py"
        },
    )
    def test_digest_json(self, test_data, fake_get):
        "test producing digest json with various inputs"
        fake_get.return_value = FakeResponse(200, IMAGE_JSON)
        json_content = self.activity.digest_json(
            test_data.get("docx_file"),
            test_data.get("jats_file"),
            test_data.get("image_file"),
            test_data.get("related"),
        )
        folder_name = "digests"
        expected_json = read_fixture(test_data.get("expected_json_file"), folder_name)
        self.assertEqual(json_content, expected_json)


if __name__ == '__main__':
    unittest.main()
