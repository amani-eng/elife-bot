import random
import time
import json
from provider import process
from optparse import OptionParser
from S3utility.s3_notification_info import S3NotificationInfo
from S3utility.s3_sqs_message import S3SQSMessage
import boto.sqs
from boto.sqs.message import Message
import log
import os
import yaml
import re
import newrelic.agent

# Add parent directory for imports, so activity classes can use elife-api-prototype
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.sys.path.insert(0, parentdir)

"""
Amazon SQS worker
"""

class QueueWorker:
    def __init__(self, settings, logger=None):
        self.settings = settings
        if logger:
            self.logger = logger
        else:
            self.create_log()
        self.conn = None
        # queues for reading and writing
        self.queue = None
        self.out_queue = None

    def create_log(self):
        # Log
        identity = "queue_worker_%s" % os.getpid()
        log_file = "queue_worker.log"
        # logFile = None
        self.logger = log.logger(log_file, self.settings.setLevel, identity)

    def connect(self):
        "connect to the queue service"
        if not self.conn:
            self.conn = boto.sqs.connect_to_region(
                self.settings.sqs_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key)

    def queues(self):
        "get the queues"
        self.connect()
        if not self.queue:
            self.queue = self.conn.get_queue(self.settings.S3_monitor_queue)
            self.queue.set_message_class(S3SQSMessage)
        if not self.out_queue:
            self.out_queue = self.conn.get_queue(self.settings.workflow_starter_queue)

    def work(self, flag):
        "read messages from the queue"

        # Simple connect to the queues
        self.queues()

        rules = self.load_rules()
        application = newrelic.agent.application()

        # Poll for an activity task indefinitely
        if self.queue is not None:
            while flag.green():

                self.logger.info('reading message')
                queue_message = self.queue.read(30)
                # TODO : check for more-than-once delivery
                # ( Dynamo conditional write? http://tinyurl.com/of3tmop )

                if queue_message is None:
                    self.logger.info('no messages available')
                else:
                    with newrelic.agent.BackgroundTask(application, name=queue_message.notification_type, group='queue_worker.py'):
                        self.logger.info('got message id: %s' % queue_message.id)
                        if queue_message.notification_type == 'S3Event':
                            info = S3NotificationInfo.from_S3SQSMessage(queue_message)
                            self.logger.info("S3NotificationInfo: %s", info.to_dict())
                            workflow_name = get_starter_name(rules, info)
                            if workflow_name is None:
                                self.logger.info("Could not handle file %s in bucket %s" % (info.file_name, info.bucket_name))
                                return False

                            # build message
                            message = {
                                'workflow_name': workflow_name,
                                'workflow_data': info.to_dict()
                            }

                            # send workflow initiation message
                            m = Message()
                            m.set_body(json.dumps(message))
                            self.out_queue.write(m)

                            # cancel incoming message
                            self.logger.info("cancelling message")
                            self.queue.delete_message(queue_message)
                            self.logger.info("message cancelled")
                        else:
                            # TODO : log
                            pass
                time.sleep(10)

            self.logger.info("graceful shutdown")

        else:
            self.logger.error('error obtaining queue')


    def load_rules(self):
        # load the rules from the YAML file
        stream = file('newFileWorkflows.yaml', 'r')
        return yaml.load(stream)


    def get_starter_name(self, rules, info):
        for rule_name in rules:
            rule = rules[rule_name]
            if re.match(rule['bucket_name_pattern'], info.bucket_name) and \
                    re.match(rule['file_name_pattern'], info.file_name):
                return rule['starter_name']
            pass


def reload_module(module_name):
    """
    Given an module name,
    attempt to reload the module
    """
    try:
        reload(eval(module_name))
    except:
        pass

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-e", "--env", default="dev", action="store", type="string", dest="env",
                      help="set the environment to run, either dev or live")
    (options, args) = parser.parse_args()
    if options.env:
        ENV = options.env
    settings_lib = __import__('settings')
    settings = settings_lib.get_settings(ENV)
    queue_worker = QueueWorker(settings)
    process.monitor_interrupt(lambda flag: queue_worker.work(flag))
