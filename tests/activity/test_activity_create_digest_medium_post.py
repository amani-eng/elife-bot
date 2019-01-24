# coding=utf-8

import unittest
import copy
from collections import OrderedDict
from mock import patch
from ddt import ddt, data
import activity.activity_CreateDigestMediumPost as activity_module
from activity.activity_CreateDigestMediumPost import (
    activity_CreateDigestMediumPost as activity_object)
import provider.article as article
import provider.lax_provider as lax_provider
import provider.digest_provider as digest_provider
import provider.article_processing as article_processing
import tests.activity.settings_mock as settings_mock
from tests.activity.classes_mock import FakeLogger, FakeStorageContext


ACTIVITY_DATA = {
    "run": "",
    "article_id": "99999",
    "version": "1",
    "status": "vor",
    "expanded_folder": "digests",
    "run_type": None
}


def digest_activity_data(data, status=None, run_type=None):
    new_data = copy.copy(data)
    if new_data and status:
        new_data["status"] = status
    if new_data and run_type:
        new_data["run_type"] = run_type
    return new_data


EXPECTED_MEDIUM_CONTENT = OrderedDict(
    [
        ('title', u'Fishing for errors in the\xa0tests'),
        ('contentFormat', 'html'),
        ('content', u'<h1>Fishing for errors in the\xa0tests</h1><h2>Testing a document which mimics the format of a file we’ve used \xa0before plus CO<sub>2</sub> and Ca<sup>2+</sup>.</h2><hr/><p>Microbes live in us and on us. They are tremendously important for our health, but remain difficult to understand, since a microbial community typically consists of hundreds of species that interact in complex ways that we cannot fully characterize. It is tempting to ask whether one might instead characterize such a community as a whole, treating it as a multicellular "super-organism". However, taking this view beyond a metaphor is controversial, because the formal criteria of multicellularity require pervasive levels of cooperation between organisms that do not occur in most natural communities.</p><p>In nature, entire communities of microbes routinely come into contact – for example, kissing can mix together the communities in each person’s mouth. Can such events be usefully described as interactions between community-level "wholes", even when individual bacteria do not cooperate with each other? And can these questions be asked in a rigorous mathematical framework?</p><p>Mikhail Tikhonov has now developed a theoretical model that shows that communities of purely "selfish" members may effectively act together when competing with another community for resources. This model offers a new way to formalize the "super-organism" metaphor: although individual members compete against each other within a community, when seen from the outside the community interacts with its environment and with other communities much like a single organism.</p><p>This perspective blurs the distinction between two fundamental concepts: competition and genetic recombination. Competition combines two communities to produce a third where species are grouped in a new way, just as the genetic material of parents is recombined in their offspring.</p><p>Tikhonov’s model is highly simplified, but this suggests that the "cohesion" seen when viewing an entire community is a general consequence of ecological interactions. In addition, the model considers only competitive interactions, but in real life, species depend on each other; for example, one organism\'s waste is another\'s food. A natural next step would be to incorporate such cooperative interactions into a similar model, as cooperation is likely to make community cohesion even stronger.</p>'),
        ('tags', [
            'Face Recognition', 'Neuroscience', 'Vision']
        ),
        ('license', 'cc-40-by')
    ]
)


@ddt
class TestCreateDigestMediumPost(unittest.TestCase):

    def setUp(self):
        fake_logger = FakeLogger()
        self.activity = activity_object(settings_mock, fake_logger, None, None, None)

    def tearDown(self):
        # clean the temporary directory
        self.activity.clean_tmp_dir()

    @patch('digestparser.medium_post.post_content')
    @patch.object(lax_provider, 'article_first_by_status')
    @patch.object(lax_provider, 'article_highest_version')
    @patch.object(article_processing, 'storage_context')
    @patch.object(article, 'storage_context')
    @patch.object(digest_provider, 'storage_context')
    @patch.object(activity_object, 'emit_monitor_event')
    @data(
        {
            "comment": "approved for medium post",
            "bucket_resources": ["elife-15747-v2.xml"],
            "bot_bucket_resources": ["digests/outbox/99999/digest-99999.docx",
                                     "digests/outbox/99999/digest-99999.jpg"],
            "first_vor": True,
            "lax_highest_version": '1',
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_medium_content": EXPECTED_MEDIUM_CONTENT
        },
        {
            "comment": "not first vor",
            "bucket_resources": ["elife-15747-v2.xml"],
            "bot_bucket_resources": ["digests/outbox/99999/digest-99999.docx",
                                     "digests/outbox/99999/digest-99999.jpg"],
            "first_vor": False,
            "lax_highest_version": '1',
            "expected_result": activity_object.ACTIVITY_SUCCESS,
            "expected_medium_content": None
        },
    )
    def test_do_activity(self, test_data, fake_emit, fake_storage_context,
                         fake_article_storage_context, fake_processing_storage_context,
                         fake_highest_version, fake_first, fake_post_content):
        # copy files into the input directory using the storage context
        fake_emit.return_value = None
        activity_data = digest_activity_data(
            ACTIVITY_DATA
            )
        named_storage_context = FakeStorageContext()
        if test_data.get('bucket_resources'):
            named_storage_context.resources = test_data.get('bucket_resources')
        fake_article_storage_context.return_value = named_storage_context
        bot_storage_context = FakeStorageContext()
        if test_data.get('bot_bucket_resources'):
            bot_storage_context.resources = test_data.get('bot_bucket_resources')
        fake_storage_context.return_value = bot_storage_context
        fake_processing_storage_context.return_value = FakeStorageContext()
        # lax mocking
        fake_highest_version.return_value = test_data.get('lax_highest_version')
        fake_first.return_value = test_data.get("first_vor")
        # do the activity
        result = self.activity.do_activity(activity_data)
        # check assertions
        self.assertEqual(result, test_data.get("expected_result"))
        self.assertEqual(self.activity.medium_content, test_data.get("expected_medium_content"))

    @patch.object(activity_object, 'emit_monitor_event')
    def test_do_activity_missing_credentials(self, fake_emit):
        # copy files into the input directory using the storage context
        fake_emit.return_value = None
        activity_data = digest_activity_data(
            ACTIVITY_DATA
            )
        self.activity.digest_config['medium_application_client_id'] = ''
        # do the activity
        result = self.activity.do_activity(activity_data)
        # check assertions
        self.assertEqual(result, activity_object.ACTIVITY_SUCCESS)

    @patch.object(lax_provider, 'article_first_by_status')
    @patch.object(lax_provider, 'article_highest_version')
    @data(
        {
            "comment": "a poa",
            "article_id": '00000',
            "status": "poa",
            "version": 3,
            "run_type": None,
            "highest_version": '1',
            "first_vor": False,
            "expected": False
        },
        {
            "comment": "silent correction",
            "article_id": '00000',
            "status": "vor",
            "version": 3,
            "run_type": "silent-correction",
            "highest_version": '1',
            "first_vor": False,
            "expected": False
        },
        {
            "comment": "non-first vor",
            "article_id": '00000',
            "status": "vor",
            "version": 3,
            "run_type": None,
            "highest_version": '1',
            "first_vor": False,
            "expected": False
        },
    )
    def test_approve(self, test_data, fake_highest_version, fake_first):
        "test various scenarios for digest ingest approval"
        fake_highest_version.return_value = test_data.get("highest_version")
        fake_first.return_value = test_data.get("first_vor")
        status = self.activity.approve(
            test_data.get("article_id"),
            test_data.get("status"),
            test_data.get("version"),
            test_data.get("run_type")
        )
        self.assertEqual(status, test_data.get("expected"),
                         "failed in {comment}".format(comment=test_data.get("comment")))

    def test_create_medium_content_empty(self):
        result = activity_module.post_medium_content(None, {}, FakeLogger())
        self.assertIsNone(result)

    @patch('digestparser.medium_post.post_content')
    def test_create_medium_content_exception(self, fake_post_content):
        fake_post_content.side_effect = Exception("Something went wrong!")
        result = activity_module.post_medium_content('content', {}, FakeLogger())
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
