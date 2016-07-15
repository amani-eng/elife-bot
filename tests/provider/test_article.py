import unittest
from provider.article import article
import tests.settings_mock as settings_mock
import tests.test_data as test_data
from mock import mock, patch

class TestProviderArticle(unittest.TestCase):

    @patch('provider.simpleDB')
    def setUp(self, mock_simpleDB):
        mock_simpleDB.return_value = None
        self.articleprovider = article(settings_mock)

    @patch('provider.lax_provider.article_versions')
    def test_download_article_xml_from_s3_error_article_version_500(self, mock_lax_provider_article_versions):
        mock_lax_provider_article_versions.return_value = 500, test_data.lax_article_versions_response_data
        result = self.articleprovider.download_article_xml_from_s3('08411')
        self.assertEqual(result, False)

    @patch('provider.lax_provider.article_versions')
    def test_download_article_xml_from_s3_error_article_version_404(self, mock_lax_provider_article_versions):
        mock_lax_provider_article_versions.return_value = 404, test_data.lax_article_versions_response_data
        result = self.articleprovider.download_article_xml_from_s3('08411')
        self.assertEqual(result, False)



if __name__ == '__main__':
    unittest.main()
