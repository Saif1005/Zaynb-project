"""Orchestrateur AWS — délègue au pipeline multi-agent ou Step Functions."""

import json
import os
from typing import Dict, Any, Optional

import boto3
from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.agents.orchestrator import OrchestratorAgent
from config.aws_config import aws_config
from config.llm_config import get_biollm_model_and_path


class AWSOrchestratorAgent(BaseAgent):
    """
    Lance le pipeline sur EC2 via OrchestratorAgent ou Step Functions.

    Si STEP_FUNCTIONS_ARN est défini, démarre une exécution Step Functions.
    Sinon, exécute OrchestratorAgent directement (mode EC2 worker).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("AWSOrchestrator", config)
        self.state_machine_arn = (
            (config or {}).get("state_machine_arn")
            or os.getenv("STEP_FUNCTIONS_ARN")
        )
        self.region = aws_config.region
        self.sfn = boto3.client("stepfunctions", region_name=self.region)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        return "patient_id" in context

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        if self.state_machine_arn:
            return self._start_step_functions(context)
        return self._run_orchestrator(context)

    def _start_step_functions(self, context: Dict[str, Any]) -> AgentResult:
        try:
            response = self.sfn.start_execution(
                stateMachineArn=self.state_machine_arn,
                input=json.dumps(context, default=str),
            )
            arn = response["executionArn"]
            logger.info(f"Step Functions started: {arn}")
            return AgentResult(
                success=True,
                status=AgentStatus.RUNNING,
                data={"execution_arn": arn, "mode": "step_functions"},
            )
        except Exception as e:
            logger.error(f"Step Functions failed: {e}")
            return AgentResult(success=False, status=AgentStatus.FAILED, error=str(e))

    def _run_orchestrator(self, context: Dict[str, Any]) -> AgentResult:
        model_name, model_path = get_biollm_model_and_path()
        config = {
            "instance_id": context.get("instance_id") or os.getenv("EC2_INSTANCE_ID"),
            "ssh_key": context.get("ssh_key") or os.getenv("SSH_KEY_PATH"),
            "auto_train": context.get("train_llm", False),
            "model_name": context.get("model_name", model_name),
            "model_path": context.get("model_path", model_path),
        }
        context.setdefault("model_name", config["model_name"])
        context.setdefault("model_path", config["model_path"])
        orchestrator = OrchestratorAgent(config=config)
        return orchestrator.run(context)

    def get_execution_status(self, execution_arn: str) -> Dict[str, Any]:
        """Statut d'une exécution Step Functions."""
        try:
            resp = self.sfn.describe_execution(executionArn=execution_arn)
            return {
                "status": resp.get("status", "UNKNOWN"),
                "startDate": str(resp.get("startDate", "")),
                "stopDate": str(resp.get("stopDate", "")),
            }
        except Exception as e:
            logger.error(f"describe_execution failed: {e}")
            return {"status": "ERROR", "error": str(e)}
