from starter.objects import Starter, default_workflow_params
from provider import utils

"""
Amazon SWF PublishPOA starter
"""


class starter_PublishPOA(Starter):

    def get_workflow_params(self):
        workflow_params = default_workflow_params(self.settings)
        workflow_params['workflow_id'] = "PublishPOA"
        workflow_params['workflow_name'] = "PublishPOA"
        workflow_params['workflow_version'] = "1"
        workflow_params['execution_start_to_close_timeout'] = str(60 * 35)
        return workflow_params

    def start(self, settings):
        """method for backwards compatibility"""
        self.settings = settings
        self.instantiate_logger()
        self.start_workflow()

    def start_workflow(self):

        self.connect_to_swf()

        workflow_params = self.get_workflow_params()

        # start a workflow execution
        self.logger.info('Starting workflow: %s', workflow_params.get('workflow_id'))
        try:
            self.start_swf_workflow_execution(workflow_params)
        except:
            message = (
                'Exception starting workflow execution for workflow_id %s' %
                workflow_params.get('workflow_id'))
            self.logger.exception(message)


if __name__ == "__main__":

    ENV = utils.console_start_env()
    SETTINGS = utils.get_settings(ENV)

    STARTER = starter_PublishPOA(SETTINGS)

    STARTER.start_workflow()
