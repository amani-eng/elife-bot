
domain = ""
default_task_list = ""

storage_provider = 's3'
expanded_bucket = 'origin_bucket'

publishing_buckets_prefix = ""

bucket = ""

aws_access_key_id = ""
aws_secret_access_key = ""

workflow_starter_queue = ""
sqs_region = ""


simpledb_region = ""
simpledb_domain_postfix = "_test"
ejp_bucket = 'ejp_bucket'
templates_bucket = 'templates_bucket'
bot_bucket = 'bot_bucket'
lens_bucket = 'dest_bucket'
poa_packaging_bucket = 'poa_packaging_bucket'
poa_bucket = 'poa_bucket'
ses_poa_sender_email = ""
ses_poa_recipient_email = ""

lax_article_versions = 'https://test/eLife.{article_id}/version/'
verify_ssl = False

no_download_extensions = 'tif'

# Logging
setLevel = "INFO"

# PDF cover
pdf_cover_generator = "https://localhost/personalised-covers/"
pdf_cover_landing_page = "https://localhost.org/download-your-cover/"

# Fastly CDNs
fastly_service_ids = ['3M35rb7puabccOLrFFxy2']
fastly_api_key = 'fake_fastly_api_key'
