from workflow.objects import Workflow
from workflow.helper import define_workflow_step, define_workflow_step_15


class workflow_DepositCrossrefPeerReview(Workflow):

    def __init__(self, settings, logger, conn=None, token=None, decision=None,
                 maximum_page_size=100):
        super(workflow_DepositCrossrefPeerReview, self).__init__(
            settings, logger, conn, token, decision, maximum_page_size)

        # SWF Defaults
        self.name = "DepositCrossrefPeerReview"
        self.version = "1"
        self.description = "Workflow for depositing peer reviews to Crossref"
        self.default_execution_start_to_close_timeout = 60 * 20
        self.default_task_start_to_close_timeout = 30

        # Get the input from the JSON decision response
        data = self.get_input()

        # JSON format workflow definition, for now
        workflow_definition = {
            "name": self.name,
            "version": self.version,
            "task_list": self.settings.default_task_list,
            "input": data,

            "start":
                {
                    "requirements": None
                },

            "steps":
                [
                    define_workflow_step("PingWorker", data),
                    define_workflow_step_15("DepositCrossrefPeerReview", data),
                ],

            "finish":
                {
                    "requirements": None
                }
        }

        self.load_definition(workflow_definition)
