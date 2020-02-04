import os
# Add parent directory for imports
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.sys.path.insert(0, parentdir)

import boto.swf
import log
import json
import random
from optparse import OptionParser


"""
Amazon SWF PackagePOA starter
"""

class starter_PackagePOA():

    def start(self, settings, document):
        # Log
        identity = "starter_PackagePOA_%s" % int(random.random() * 1000)
        logFile = "starter.log"
        #logFile = None
        logger = log.logger(logFile, settings.setLevel, identity)
        logger.info("input: document=%s", document)

        # Simple connect
        conn = boto.swf.layer1.Layer1(settings.aws_access_key_id, settings.aws_secret_access_key)

        doc = {"document": document}

        logger.info("doc: %s", doc)

        # Start a workflow execution
        workflow_id = "PackagePOA_%s" % (document)
        workflow_name = "PackagePOA"
        workflow_version = "1"
        child_policy = None
        execution_start_to_close_timeout = None
        input = '{"data": ' + json.dumps(doc) + '}'

        try:
            logger.info('starting workflow_id: %s', workflow_id)
            response = conn.start_workflow_execution(
                settings.domain, workflow_id,
                workflow_name, workflow_version,
                settings.default_task_list,
                child_policy,
                execution_start_to_close_timeout,
                input)

            logger.info('got response: \n%s' %
                        json.dumps(response, sort_keys=True, indent=4))

        except boto.swf.exceptions.SWFWorkflowExecutionAlreadyStartedError:
            # There is already a running workflow with that ID, cannot start another
            message = (
                'SWFWorkflowExecutionAlreadyStartedError: There is already ' +
                'a running workflow with ID %s' % workflow_id)
            print(message)
            logger.info(message)


if __name__ == "__main__":

    document = None

    # Add options
    parser = OptionParser()
    parser.add_option("-e", "--env", default="dev", action="store", type="string",
                      dest="env", help="set the environment to run, either dev or live")
    parser.add_option("-f", "--file", default=None, action="store", type="string",
                      dest="document", help="specify the S3 object name of the POA zip file")

    (options, args) = parser.parse_args()
    if options.env:
        ENV = options.env
    if options.document:
        document = options.document

    import settings as settingsLib
    settings = settingsLib.get_settings(ENV)

    o = starter_PackagePOA()

    o.start(settings=settings, document=document)
