import os
import json
from provider.storage_provider import storage_context
from provider.execution_context import get_session
import provider.digest_provider as digest_provider
import provider.lax_provider as lax_provider
from .activity import Activity


"""
activity_IngestDigestToEndpoint.py activity
"""


class activity_IngestDigestToEndpoint(Activity):
    def __init__(self, settings, logger, conn=None, token=None, activity_task=None):
        super(activity_IngestDigestToEndpoint, self).__init__(
            settings, logger, conn, token, activity_task)

        self.name = "IngestDigestToEndpoint"
        self.pretty_name = "Ingest Digest to API endpoint"
        self.version = "1"
        self.default_task_heartbeat_timeout = 30
        self.default_task_schedule_to_close_timeout = 60 * 5
        self.default_task_schedule_to_start_timeout = 30
        self.default_task_start_to_close_timeout = 60 * 5
        self.description = ("Send Digest JSON to an API endpoint," +
                            " to be run when a research article is ingested")

        # Local directory settings
        self.temp_dir = os.path.join(self.get_tmp_dir(), "tmp_dir")
        self.input_dir = os.path.join(self.get_tmp_dir(), "input_dir")

        # Create output directories
        self.create_activity_directories()

        # Track the success of some steps
        self.approve_status = None

    def do_activity(self, data=None):
        self.logger.info("data: %s" % json.dumps(data, sort_keys=True, indent=4))

        try:
            run = data["run"]
            session = get_session(self.settings, data, run)
            version = session.get_value("version")
            article_id = session.get_value("article_id")
            status = session.get_value("status")
            run_type = session.get_value("run_type")

            self.emit_monitor_event(self.settings, article_id, version, run,
                                    self.pretty_name, "start",
                                    "Starting ingest digest to endpoint for " + article_id)
        except Exception as exception:
            self.logger.exception("Exception when getting the session for Starting ingest digest " +
                                  " to endpoint. Details: %s", str(exception))
            return self.ACTIVITY_PERMANENT_FAILURE

        # Approve for ingestion
        self.approve_status, errors = self.approve(article_id, status, version, run_type)

        # bucket name
        bucket_name = self.settings.bot_bucket

        self.emit_monitor_event(self.settings, article_id, version, run,
                                self.pretty_name, "end",
                                "Finished ingest digest to endpoint for " + article_id)

        return self.ACTIVITY_SUCCESS

    def approve(self, article_id, status, version, run_type):
        "should we ingest based on some basic attributes"
        approve_status = True
        approve_errors = []

        # check by status
        return_status, errors = approve_by_status(self.logger, article_id, status)
        if return_status is False:
            approve_status = return_status
            approve_errors += errors

        # check silent corrections
        return_status, errors = approve_by_run_type(
            self.settings, self.logger, article_id, run_type, version)
        if return_status is False:
            approve_status = return_status
            approve_errors += errors

        return approve_status, approve_errors

    def create_activity_directories(self):
        """
        Create the directories in the activity tmp_dir
        """
        for dir_name in [self.temp_dir, self.input_dir]:
            try:
                os.mkdir(dir_name)
            except OSError:
                pass


def approve_by_status(logger, article_id, status):
    "determine approval status by article status value"
    approve_status = None
    errors = []
    # PoA do not ingest digests
    if status == "poa":
        approve_status = False
        message = ("\nNot ingesting digest for PoA article {article_id}".format(
            article_id=article_id
        ))
        logger.info(message)
        errors.append(message)
    return approve_status, errors


def approve_by_run_type(settings, logger, article_id, run_type, version):
    approve_status = None
    errors = []
    # VoR and is a silent correction, consult Lax for if it is not the highest version
    if run_type == "silent-correction":
        highest_version = lax_provider.article_highest_version(article_id, settings)
        try:
            if int(version) < int(highest_version):
                approve_status = False
                message = (
                    "\nNot ingesting digest for silent correction {article_id}" +
                    " version {version} is less than highest version {highest}").format(
                        article_id=article_id,
                        version=version,
                        highest=highest_version)
                errors.append(message)
                logger.info(message)
        except TypeError as exception:
            approve_status = False
            message = (
                "\nException converting version to int for {article_id}, {exc}").format(
                    article_id=article_id,
                    exc=str(exception))
            errors.append(message)
            logger.exception(message.lstrip())
    return approve_status, errors
