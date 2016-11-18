import requests
import time
from . import article
import base64
import json
from dateutil.parser import parse

def article_versions(article_id, settings):
    url = settings.lax_article_versions.replace('{article_id}', article_id)
    response = requests.get(url, verify=settings.verify_ssl)
    status_code = response.status_code
    if status_code == 200:
        data = response.json()
        if "versions" in data:
            return status_code, data["versions"]
    return status_code, None


def article_version(article_id, version, settings):
    url = settings.lax_article_versions
    url = url.replace('{article_id}', article_id)
    url = url.replace('{version}', version)
    response = requests.get(url, verify=settings.verify_ssl)
    return response.status_code, response.json()


def article_highest_version(article_id, settings, logger=None):
    status_code, data = article_versions(article_id, settings)
    if status_code == 200:
        high_version = 0 if len(data) < 1 else max(map(lambda x: int(x["version"]), data))
        return high_version
    elif status_code == 404:
        return "1"
    else:
        if logger:
            logger.error("Error obtaining version information from Lax" +
                         str(status_code))
        return None


def article_next_version(article_id, settings):
    version = article_highest_version(article_id, settings)
    if isinstance(version, (int,long)) and version >= 0:
        version = str(version + 1)
    if version is None:
        return "-1"
    return version


def article_publication_date_by_version(article_id, version, settings):
    status_code, data = article_versions(article_id, settings)
    print data
    if status_code == 200:
        version_data = (vd for vd in data if vd["version"] == int(version)).next()
        return parse(version_data["published"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    raise Exception("Error in article_publication_date_by_version: Version date not found. Status: " + str(status_code))


def article_version_date(article_id, version, settings):
    status_code, data = article_version(article_id, version, settings)
    if status_code == 200:
        if "versionDate" in data:
            return parse(data["versionDate"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def article_publication_date(article_id, settings, logger=None):
    status_code, data = article_versions(article_id, settings)
    if status_code == 200:
        first_published_version_list = filter(lambda x: int(x["version"]) == 1, data)
        if len(first_published_version_list) < 1:
            return None
        first_published_version = first_published_version_list[0]
        if "published" not in first_published_version:
            return None
        date_str = None
        try:
            date_struct = time.strptime(first_published_version['published'], "%Y-%m-%dT%H:%M:%SZ")
            date_str = time.strftime('%Y%m%d%H%M%S', date_struct)

        except:
            if logger:
                logger.error("Error parsing the datetime_published from Lax: "
                             + str(first_published_version['published']))

        return date_str
    elif status_code == 404:
        return None
    else:
        if logger:
            logger.error("Error obtaining version information from Lax" + str(status_code))
        return None


def poa_vor_status(data):
    if len(data) < 1:
        return None, None
    check_status = lambda status_type : True if next((vd for vd in data if vd["status"] == status_type), None) \
                                                is not None else None
    poa_status = check_status("poa")
    vor_status = check_status("vor")
    return poa_status, vor_status


def prepare_action_message(settings, article_id, run, expanded_folder, version, status, eif_location, action, force=False):
        xml_bucket = settings.publishing_buckets_prefix + settings.expanded_bucket
        xml_file_name = get_xml_file_name(settings, expanded_folder, xml_bucket)
        xml_path = 'https://s3.amazonaws.com/' + xml_bucket + '/' + expanded_folder + '/' + xml_file_name
        carry_over_data = {
            'action': action,
            'location': xml_path,
            'id': article_id,
            'version': int(version),
            'force': force,
            'token': lax_token(run, version, expanded_folder, status, eif_location, force)
        }
        message = carry_over_data
        return message

def get_xml_file_name(settings, expanded_folder, xml_bucket):
    Article = article.article()
    xml_file_name = Article.get_xml_file_name(settings, expanded_folder, xml_bucket)
    return xml_file_name

def lax_token(run, version, expanded_folder, status, eif_location, force=False):
    token = {
        'run': run, 
        'version': version,
        'expanded_folder': expanded_folder,
        'eif_location': eif_location,
        'status': status,
        'force': force
    }
    return base64.encodestring(json.dumps(token))

