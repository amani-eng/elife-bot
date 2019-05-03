import os
import json
from collections import OrderedDict
import zipfile
import shutil
import re

from ftplib import FTP
import ftplib

import boto.swf
import boto.s3
from boto.s3.connection import S3Connection

import provider.s3lib as s3lib
from provider.article_structure import ArticleInfo, file_parts
from elifetools import parseJATS as parser
from elifetools import xmlio
from activity.objects import Activity


class activity_PMCDeposit(Activity):

    def __init__(self, settings, logger, conn=None, token=None, activity_task=None):
        super(activity_PMCDeposit, self).__init__(
            settings, logger, conn, token, activity_task)

        self.name = "PMCDeposit"
        self.version = "1"
        self.default_task_heartbeat_timeout = 30
        self.default_task_schedule_to_close_timeout = 60 * 30
        self.default_task_schedule_to_start_timeout = 30
        self.default_task_start_to_close_timeout = 60 * 15
        self.description = ("Download single zip file an article, repackage it, " +
                            "send to PMC and notify them.")

        # Local directory settings
        self.TMP_DIR = self.get_tmp_dir() + os.sep + "tmp_dir"
        self.INPUT_DIR = self.get_tmp_dir() + os.sep + "input_dir"
        self.JUNK_DIR = self.get_tmp_dir() + os.sep + "junk_dir"
        self.ZIP_DIR = self.get_tmp_dir() + os.sep + "zip_dir"
        self.EPS_DIR = self.get_tmp_dir() + os.sep + "eps_dir"
        self.TIF_DIR = self.get_tmp_dir() + os.sep + "tif_dir"
        self.OUTPUT_DIR = self.get_tmp_dir() + os.sep + "output_dir"

        # Bucket settings
        self.input_bucket = None
        self.input_bucket_default = (settings.publishing_buckets_prefix +
                                     settings.archive_bucket)

        self.publish_bucket = settings.poa_packaging_bucket
        self.published_folder = "pmc/published"
        self.published_zip_folder = "pmc/zip"

        # journal
        self.journal = 'elife'

        # Outgoing FTP settings are set later
        self.FTP_URI = None
        self.FTP_USERNAME = None
        self.FTP_PASSWORD = None
        self.FTP_CWD = None
        self.FTP_SUBDIR = []

    def do_activity(self, data=None):
        """
        Activity, do the work
        """
        if self.logger:
            self.logger.info('data: %s' % json.dumps(data, sort_keys=True, indent=4))

        # Data passed to this activity
        self.document = data["data"]["document"]

        # set the FTP folder for resupplies
        if "folder" in data["data"]:
            self.FTP_SUBDIR = [data["data"]["folder"]]

        # Custom bucket, if specified
        if "bucket" in data["data"]:
            self.input_bucket = data["data"]["bucket"]
        else:
            self.input_bucket = self.input_bucket_default

        # Create output directories
        self.create_activity_directories()

        # Download the S3 objects
        self.download_files_from_s3(self.document)

        verified = None
        # Check for an empty folder and respond true
        #  if we do not do this it will continue to attempt this activity
        if self.file_list(self.INPUT_DIR):
            if self.logger:
                self.logger.info('folder was empty in PMCDeposit: ' + self.INPUT_DIR)
            verified = True

        folder = self.INPUT_DIR
        if self.logger:
            self.logger.info('processing files in folder ' + folder)

        self.unzip_article_files(self.file_list(folder))

        (fid, status, version, volume) = self.profile_article(self.document)

        # Rename the files
        file_name_map = self.rename_files_remove_version_number()

        (verified, renamed_list, not_renamed_list) = self.verify_rename_files(file_name_map)
        if self.logger:
            self.logger.info("verified " + folder + ": " + str(verified))
            self.logger.info(file_name_map)

        if len(not_renamed_list) > 0:
            if self.logger:
                self.logger.info("not renamed " + str(not_renamed_list))

        # Convert the XML
        self.convert_xml(xml_file=self.article_xml_file(),
                         file_name_map=file_name_map)

        # Get the new zip file name
        # take into account the r1 r2 revision numbers when replacing an article
        revision = self.zip_revision_number(fid)
        self.zip_file_name = self.new_zip_filename(self.journal, volume, fid, revision)
        print(self.zip_file_name)
        self.create_new_zip(self.zip_file_name)

        # Set FTP settings
        self.set_ftp_settings(fid)

        ftp_status = None
        if verified and self.zip_file_name:
            ftp_status = self.ftp_to_endpoint(self.file_list(self.ZIP_DIR), self.FTP_SUBDIR, passive=True)

            if ftp_status is True:
                self.upload_article_zip_to_s3()

        # Return the activity result, True or False
        if verified is True and ftp_status is True:
            result = True
        else:
            result = False

        # Clean up disk
        self.clean_tmp_dir()

        return result

    def set_ftp_settings(self, doi_id):
        """
        Set the outgoing FTP server settings based on the
        workflow type specified
        """

        self.FTP_URI = self.settings.PMC_FTP_URI
        self.FTP_USERNAME = self.settings.PMC_FTP_USERNAME
        self.FTP_PASSWORD = self.settings.PMC_FTP_PASSWORD
        self.FTP_CWD = self.settings.PMC_FTP_CWD

    def ftp_upload(self, ftp, file):
        ext = os.path.splitext(file)[1]
        # print(file)
        uploadname = file.split(os.sep)[-1]
        if ext in (".txt", ".htm", ".html"):
            ftp.storlines("STOR " + file, open(file))
        else:
            # print("uploading " + uploadname)
            ftp.storbinary("STOR " + uploadname, open(file, "rb"), 1024)
            # print("uploaded " + uploadname)

    def ftp_cwd_mkd(self, ftp, sub_dir):
        """
        Given an FTP connection and a sub_dir name
        try to cwd to the directory. If the directory
        does not exist, create it, then cwd again
        """
        cwd_success = None
        try:
            ftp.cwd(sub_dir)
            cwd_success = True
        except ftplib.error_perm:
            # Directory probably does not exist, create it
            ftp.mkd(sub_dir)
            cwd_success = False
        if cwd_success is not True:
            ftp.cwd(sub_dir)

        return cwd_success

    def ftp_to_endpoint(self, uploadfiles, sub_dir_list=None, passive=True):
        try:
            for uploadfile in uploadfiles:
                ftp = FTP()
                if passive is False:
                    ftp.set_pasv(False)
                ftp.connect(self.FTP_URI)
                ftp.login(self.FTP_USERNAME, self.FTP_PASSWORD)

                self.ftp_cwd_mkd(ftp, "/")
                if self.FTP_CWD != "":
                    self.ftp_cwd_mkd(ftp, self.FTP_CWD)
                if sub_dir_list is not None:
                    for sub_dir in sub_dir_list:
                        self.ftp_cwd_mkd(ftp, sub_dir)

                self.ftp_upload(ftp, uploadfile)
                ftp.quit()
                return True
        except:
            return False

    def download_files_from_s3(self, document):

        if self.logger:
            self.logger.info('downloading VoR file ' + document)

        subfolder_name = ""

        # Connect to S3 and bucket
        s3_conn = S3Connection(self.settings.aws_access_key_id, self.settings.aws_secret_access_key)
        bucket = s3_conn.lookup(self.input_bucket)

        s3_key_name = document
        s3_key_names = [s3_key_name]

        self.download_s3_key_names_to_subfolder(bucket, s3_key_names, subfolder_name)

    def download_s3_key_names_to_subfolder(self, bucket, s3_key_names, subfolder_name):

        for s3_key_name in s3_key_names:
            # Download objects from S3 and save to disk

            s3_key = bucket.get_key(s3_key_name)

            filename = s3_key_name.split("/")[-1]

            # Make the subfolder if it does not exist yet
            try:
                os.mkdir(self.INPUT_DIR + os.sep + subfolder_name)
            except:
                pass

            filename_plus_path = (self.INPUT_DIR
                                  + os.sep + subfolder_name
                                  + os.sep + filename)
            mode = "wb"
            f = open(filename_plus_path, mode)
            s3_key.get_contents_to_file(f)
            f.close()

    def upload_article_zip_to_s3(self):
        """
        Upload PMC zip file to S3
        """
        bucket_name = self.publish_bucket

        # Connect to S3 and bucket
        s3_conn = S3Connection(self.settings.aws_access_key_id, self.settings.aws_secret_access_key)
        bucket = s3_conn.lookup(bucket_name)

        for file_name in self.file_list(self.ZIP_DIR):
            s3_key_name = self.published_zip_folder + '/' + self.file_name_from_name(file_name)
            s3_key = boto.s3.key.Key(bucket)
            s3_key.key = s3_key_name
            s3_key.set_contents_from_filename(file_name, replace=True)

    def list_dir(self, dir_name):
        dir_list = os.listdir(dir_name)
        dir_list = map(lambda item: dir_name + os.sep + item, dir_list)
        return dir_list

    def folder_list(self, dir_name):
        dir_list = self.list_dir(dir_name)
        return list(filter(lambda item: os.path.isdir(item), dir_list))

    def file_list(self, dir_name):
        dir_list = self.list_dir(dir_name)
        return list(filter(lambda item: os.path.isfile(item), dir_list))

    def folder_name_from_name(self, input_dir, file_name):
        folder_name = file_name.split(input_dir)[1]
        folder_name = folder_name.split(os.sep)[1]
        return folder_name

    def file_name_from_name(self, file_name):
        name = file_name.split(os.sep)[-1]
        return name

    def file_extension(self, file_name):
        name = self.file_name_from_name(file_name)
        if name:
            if len(name.split('.')) > 1:
                return name.split('.')[-1]
            else:
                return None
        return None

    def unzip_or_move_file(self, file_name, to_dir, do_unzip=True):
        """
        If file extension is zip, then unzip contents
        If file the extension
        """
        if self.file_extension(file_name) == 'zip' and do_unzip is True:
            # Unzip
            if self.logger:
                self.logger.info("going to unzip " + file_name + " to " + to_dir)
            myzip = zipfile.ZipFile(file_name, 'r')
            myzip.extractall(to_dir)

        elif self.file_extension(file_name):
            # Copy
            if self.logger:
                self.logger.info("going to move and not unzip " + file_name + " to " + to_dir)
            shutil.copyfile(file_name, to_dir + os.sep + self.file_name_from_name(file_name))

    def approve_file(self, file_name):
        return True

    def unzip_article_files(self, file_list):

        for file_name in file_list:
            if self.approve_file(file_name):
                if self.logger:
                    self.logger.info("unzipping or moving file " + file_name)
                self.unzip_or_move_file(file_name, self.TMP_DIR)

    def stripped_file_name_map(self, file_names):
        "from a list of file names, build a map of old to new file name with the version removed"
        file_name_map = OrderedDict()
        for df in file_names:
            filename = df.split(os.sep)[-1]
            info = ArticleInfo(filename)
            prefix, extension = file_parts(filename)
            if info.versioned is True and info.version is not None:
                # Use part before the -v number
                part_without_version = prefix.split('-v')[0]
            else:
                # Not a versioned file, use the whole file prefix
                part_without_version = prefix
            renamed_filename = '.'.join([part_without_version, extension])
            file_name_map[filename] = renamed_filename
        return file_name_map

    def rename_files_remove_version_number(self):
        """
        Rename files to not include the version number, if present
        Pre-PPP files will not have a version number, for before PPP is launched
        """
        # Get a list of all files
        dirfiles = self.file_list(self.TMP_DIR)

        file_name_map = self.stripped_file_name_map(dirfiles)

        for old_name, new_name in file_name_map.items():
            if new_name is not None:
                shutil.move(self.TMP_DIR + os.sep + old_name, self.OUTPUT_DIR + os.sep + new_name)

        return file_name_map

    def verify_rename_files(self, file_name_map):
        """
        Each file name as key should have a non None value as its value
        otherwise the file did not get renamed to something new and the
        rename file process was not complete
        """
        verified = True
        renamed_list = []
        not_renamed_list = []
        for k, v in file_name_map.items():
            if v is None:
                verified = False
                not_renamed_list.append(k)
            else:
                renamed_list.append(k)

        return (verified, renamed_list, not_renamed_list)

    def convert_xml(self, xml_file, file_name_map):

        # Register namespaces
        xmlio.register_xmlns()

        root, doctype_dict = xmlio.parse(xml_file, return_doctype_dict=True)

        # Convert xlink href values
        total = xmlio.convert_xlink_href(root, file_name_map)
        # TODO - compare whether all file names were converted

        # Start the file output
        reparsed_string = xmlio.output(root, type=None, doctype_dict=doctype_dict)

        f = open(xml_file, 'wb')
        f.write(reparsed_string)
        f.close()

    def zip_revision_number(self, fid):
        """
        Look at previously supplied files and determine the
        next revision number
        """
        revision = None

        bucket_name = self.publish_bucket
        prefix = self.published_zip_folder + '/'

        # Connect to S3 and bucket
        s3_conn = S3Connection(self.settings.aws_access_key_id, self.settings.aws_secret_access_key)
        bucket = s3_conn.lookup(bucket_name)

        s3_key_names = s3lib.get_s3_key_names_from_bucket(
            bucket=bucket,
            prefix=prefix)

        s3_key_name = s3lib.latest_pmc_zip_revision(fid, s3_key_names)

        if s3_key_name:
            # Found an existing PMC zip file, look for a revision number
            revision_match = re.match(r'.*r(.*)\.zip$', s3_key_name)
            if revision_match is None:
                # There is a zip but no revision number, use 1
                revision = 1
            else:
                # Use the latest revision plus 1
                revision = int(revision_match.group(1)) + 1

        return revision

    def new_zip_filename(self, journal, volume, fid, revision=None):

        filename = journal
        filename = filename + '-' + str(volume).zfill(2)
        filename = filename + '-' + str(fid).zfill(5)
        if revision:
            filename = filename + '.r' + str(revision)
        filename += '.zip'
        return filename

    def create_new_zip(self, zip_file_name):

        if self.logger:
            self.logger.info("creating new PMC zip file named " + zip_file_name)

        new_zipfile = zipfile.ZipFile(self.ZIP_DIR + os.sep + zip_file_name,
                                      'w', zipfile.ZIP_DEFLATED, allowZip64=True)

        dirfiles = self.file_list(self.OUTPUT_DIR)

        for df in dirfiles:
            filename = df.split(os.sep)[-1]
            new_zipfile.write(df, filename)

        new_zipfile.close()

    def profile_article(self, document):
        """
        Temporary, profile the article by folder names in test data set
        In real code we still want this to return the same values
        """
        # Temporary setting of version values from directory names

        soup = self.article_soup(self.article_xml_file())

        # elife id / doi id / manuscript id
        fid = parser.doi(soup).split('.')[-1]

        # article status
        if parser.is_poa(soup) is True:
            status = 'poa'
        else:
            status = 'vor'

        # version
        version = self.version_number(document)

        # volume
        volume = parser.volume(soup)

        return (fid, status, version, volume)

    def version_number(self, document):
        version = None
        m = re.search(r'-v([0-9]*?)[\.|-]', document)
        if m is not None:
            version = m.group(1)
        return version

    def article_xml_file(self):
        """
        Two directories the XML file might be in depending on the step
        """
        file_name = None

        for file_name in self.file_list(self.TMP_DIR):
            if file_name.endswith('.xml'):
                return file_name
        if not file_name:
            for file_name in self.file_list(self.OUTPUT_DIR):
                if file_name.endswith('.xml'):
                    return file_name

        return file_name

    def article_soup(self, xml_filename):
        return parser.parse_document(xml_filename)

    def create_activity_directories(self):
        """
        Create the directories in the activity tmp_dir
        """
        try:
            os.mkdir(self.TMP_DIR)
            os.mkdir(self.INPUT_DIR)
            os.mkdir(self.JUNK_DIR)
            os.mkdir(self.ZIP_DIR)
            os.mkdir(self.EPS_DIR)
            os.mkdir(self.TIF_DIR)
            os.mkdir(self.OUTPUT_DIR)

        except OSError:
            pass
