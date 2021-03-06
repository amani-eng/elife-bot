import unittest
import os
from collections import OrderedDict
from ddt import ddt, data
from mock import patch
import activity.activity_PubmedArticleDeposit as activity_module
from activity.activity_PubmedArticleDeposit import activity_PubmedArticleDeposit
from provider import lax_provider, sftp
from tests.classes_mock import FakeSMTPServer
import tests.activity.settings_mock as settings_mock
from tests.activity.classes_mock import FakeLogger
from tests.activity.classes_mock import FakeStorageContext
import tests.activity.test_activity_data as activity_test_data
import tests.test_data as test_case_data
import tests.activity.helpers as helpers


@ddt
class TestPubmedArticleDeposit(unittest.TestCase):

    def setUp(self):
        fake_logger = FakeLogger()
        self.activity = activity_PubmedArticleDeposit(settings_mock, fake_logger, None, None, None)

    def tearDown(self):
        self.activity.clean_tmp_dir()
        helpers.delete_files_in_folder(activity_test_data.ExpandArticle_files_dest_folder,
                                       filter_out=['.gitkeep'])

    def tmp_dir(self):
        "return the tmp dir name for the activity"
        return self.activity.directories.get("TMP_DIR")

    @patch.object(activity_PubmedArticleDeposit, 'clean_tmp_dir')
    @patch.object(activity_module.email_provider, 'smtp_connect')
    @patch.object(lax_provider, 'article_versions')
    @patch.object(activity_PubmedArticleDeposit, 'sftp_files_to_endpoint')
    @patch('activity.activity_PubmedArticleDeposit.storage_context')
    @patch.object(FakeStorageContext, 'list_resources')
    @data(
        {
            "comment": 'example PoA file will have an aheadofprint',
            "outbox_filenames": ['elife-29353-v1.xml', 'not_an_xml_file.pdf'],
            "sftp_files_return_value": True,
            "article_versions_data": test_case_data.lax_article_versions_response_data,
            "expected_result": True,
            "expected_statuses": OrderedDict([
                ('generate', True),
                ('approve', True),
                ('upload', True),
                ('publish', True),
                ('outbox', True),
                ('activity', True),
            ]),
            "expected_file_count": 1,
            "expected_pubmed_xml_contains": [
                (b'<ArticleTitle>An evolutionary young defense metabolite influences the root' +
                 b' growth of plants via the ancient TOR signaling pathway</ArticleTitle>'),
                (b'<PubDate PubStatus="aheadofprint"><Year>2017</Year>' +
                 b'<Month>December</Month><Day>12</Day></PubDate>'),
                b'<ELocationID EIdType="doi">10.7554/eLife.29353</ELocationID>',
                (b'<AbstractText Label="">To optimize fitness a plant should monitor its' +
                 b' metabolism to appropriately control growth and defense.')
                ]
        },
        {
            "comment": 'example VoR file will have a Replaces tag',
            "outbox_filenames": ['elife-15747-v2.xml'],
            "sftp_files_return_value": True,
            "article_versions_data": test_case_data.lax_article_versions_response_data,
            "expected_result": True,
            "expected_statuses": OrderedDict([
                ('generate', True),
                ('approve', True),
                ('upload', True),
                ('publish', True),
                ('outbox', True),
                ('activity', True),
            ]),
            "expected_file_count": 1,
            "expected_pubmed_xml_contains": [
                b'<Replaces IdType="doi">10.7554/eLife.15747</Replaces>',
                b'<ArticleTitle>Community-level cohesion without cooperation</ArticleTitle>',
                (b'<PubDate PubStatus="epublish"><Year>2016</Year>' +
                 b'<Month>June</Month><Day>16</Day></PubDate>'),
                b'<ELocationID EIdType="doi">10.7554/eLife.15747</ELocationID>',
                b'<Identifier Source="ORCID">http://orcid.org/0000-0002-9558-1121</Identifier>'
                ]
        },
        {
            "comment": 'test for if the article is published False (not published yet)',
            "outbox_filenames": ['elife-15747-v2.xml'],
            "sftp_files_return_value": True,
            "article_versions_data": [],
            "expected_result": True,
            "expected_statuses": OrderedDict([
                ('generate', False),
                ('approve', False),
                ('upload', None),
                ('publish', None),
                ('outbox', None),
                ('activity', True),
            ]),
            "expected_file_count": 0
        },
        {
            "comment": 'test for if FTP status is False',
            "outbox_filenames": ['elife-15747-v2.xml'],
            "sftp_files_return_value": False,
            "article_versions_data": test_case_data.lax_article_versions_response_data,
            "expected_result": activity_PubmedArticleDeposit.ACTIVITY_PERMANENT_FAILURE,
            "expected_statuses": OrderedDict([
                ('generate', True),
                ('approve', True),
                ('upload', False),
                ('publish', False),
                ('outbox', None),
                ('activity', False),
            ]),
            "expected_file_count": 1,
        },
        {
            "comment": 'test for if the XML file has no version it will use lax data',
            "outbox_filenames": ['elife-15747.xml'],
            "sftp_files_return_value": True,
            "article_versions_data": test_case_data.lax_article_versions_response_data,
            "expected_result": True,
            "expected_statuses": OrderedDict([
                ('generate', True),
                ('approve', True),
                ('upload', True),
                ('publish', True),
                ('outbox', True),
                ('activity', True),
            ]),
            "expected_file_count": 1,
            "expected_pubmed_xml_contains": [
                b'<Replaces IdType="doi">10.7554/eLife.15747</Replaces>'
                ]
        },
    )
    def test_do_activity(self, test_data, fake_list_resources, fake_storage_context,
                         fake_sftp_files_to_endpoint, fake_article_versions,
                         fake_email_smtp_connect, fake_clean_tmp_dir):
        fake_email_smtp_connect.return_value = FakeSMTPServer(self.activity.get_tmp_dir())
        fake_clean_tmp_dir.return_value = None
        # copy XML files into the input directory using the storage context
        fake_storage_context.return_value = FakeStorageContext()
        fake_list_resources.return_value = test_data.get("outbox_filenames")
        # lax data overrides
        fake_article_versions.return_value = 200, test_data.get("article_versions_data")
        # ftp
        fake_sftp_files_to_endpoint.return_value = test_data.get("sftp_files_return_value")
        # do the activity
        result = self.activity.do_activity()
        # check assertions
        self.assertEqual(result, test_data.get("expected_result"),
                         'failed in {comment}'.format(comment=test_data.get("comment")))
        # check statuses assertions
        for status_name in test_data.get("expected_statuses"):
            status_value = self.activity.statuses.get(status_name)
            expected = test_data.get("expected_statuses").get(status_name)
            self.assertEqual(
                status_value, expected,
                '{expected} {status_name} status not equal to {status_value} in {comment}'.format(
                    expected=expected, status_name=status_name, status_value=status_value,
                    comment=test_data.get("comment")))

        # check the outbox_s3_key_names values
        self.assertEqual(self.activity.outbox_s3_key_names,
                         [self.activity.outbox_folder + '/' + filename
                          for filename in test_data.get("outbox_filenames")],
                         'failed in {comment}'.format(comment=test_data.get("comment")))
        # Count PubMed XML file in the tmp directory
        file_count = len(os.listdir(self.tmp_dir()))
        self.assertEqual(file_count, test_data.get("expected_file_count"),
                         'failed in {comment}'.format(comment=test_data.get("comment")))
        if file_count > 0 and test_data.get("expected_pubmed_xml_contains"):
            # Open the first Pubmed XML and check some of its contents
            pubmed_xml_filename_path = os.path.join(self.tmp_dir(), os.listdir(self.tmp_dir())[0])
            with open(pubmed_xml_filename_path, 'rb') as open_file:
                pubmed_xml = open_file.read()
                for expected in test_data.get("expected_pubmed_xml_contains"):
                    self.assertTrue(
                        expected in pubmed_xml,
                        'failed in {comment}: {expected} not found in pubmed_xml {path}'.format(
                            comment=test_data.get("comment"), expected=expected,
                            path=pubmed_xml_filename_path))
        # clean directory after each test
        self.activity.clean_tmp_dir()

    @patch.object(activity_PubmedArticleDeposit, 'sftp_files_to_endpoint')
    @patch.object(activity_PubmedArticleDeposit, 'approve_for_publishing')
    @patch.object(activity_PubmedArticleDeposit, 'generate_pubmed_xml')
    @patch.object(activity_PubmedArticleDeposit, 'download_files_from_s3_outbox')
    @patch.object(activity_PubmedArticleDeposit, 'get_outbox_s3_key_names')
    def test_do_activity_upload_exception(self, fake_get, fake_download, fake_generate,
                                          fake_approve, fake_sftp_files_to_endpoint):
        fake_get.return_value = True
        fake_download.return_value = True
        fake_generate.return_value = True
        fake_approve.return_value = True
        fake_sftp_files_to_endpoint.side_effect = Exception('SFTP upload exception')
        # do the activity
        self.activity.do_activity()
        # check assertions
        self.assertIsNone(self.activity.statuses.get('upload'))
        self.assertEqual(self.activity.logger.logexception, 'SFTP upload exception')

    @patch.object(sftp.SFTP, 'sftp_connect')
    def test_sftp_files_connection_exception(self, fake_sftp_connect):
        fake_sftp_connect.side_effect = Exception('SFTP connect exception')
        with self.assertRaises(Exception):
            self.activity.sftp_files_to_endpoint('', '')
        self.assertEqual(
            self.activity.logger.logexception,
            'Failed to connect to SFTP endpoint : SFTP connect exception')

    @patch.object(sftp.SFTP, 'sftp_to_endpoint')
    @patch.object(sftp.SFTP, 'sftp_connect')
    def test_sftp_files_transfer_exception(self, fake_sftp_connect, fake_sftp_to_endpoint):
        fake_sftp_connect.return_value = True
        fake_sftp_to_endpoint.side_effect = Exception('SFTP transfer exception')
        with self.assertRaises(Exception):
            self.activity.sftp_files_to_endpoint('', '')
        self.assertEqual(
            self.activity.logger.logexception,
            'Failed to upload files by SFTP to PubMed: SFTP transfer exception')


@ddt
class TestPubmedParseArticleXml(unittest.TestCase):

    def tearDown(self):
        helpers.delete_files_in_folder(activity_test_data.ExpandArticle_files_dest_folder,
                                       filter_out=['.gitkeep'])

    @data(
        {
            "article_xml": 'elife-29353-v1.xml',
            "expected_article": "not none",
            "expected_doi": '10.7554/eLife.29353'
        },
        {
            "article_xml": 'bad_xml.xml',
            "expected_article": None
        }
    )
    def test_parse_article_xml(self, test_data):
        source_doc = "tests/files_source/pubmed/outbox/" + test_data.get('article_xml')
        article = activity_module.parse_article_xml(
            source_doc, {}, activity_test_data.ExpandArticle_files_dest_folder)
        if test_data.get('expected_article') is None:
            self.assertEqual(article, test_data.get('expected_article'),
                             'failed comparing expected_article')
        else:
            self.assertIsNotNone(article, 'failed comparing expected_article')
        if article:
            self.assertEqual(article.doi, test_data.get('expected_doi'),
                             'failed comparing expected_doi')


if __name__ == '__main__':
    unittest.main()
