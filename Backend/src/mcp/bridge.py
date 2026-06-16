"""Pont MCP ↔ agents métier Zaynb."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from loguru import logger

from src.agents.data_manager import DataManagerAgent
from src.agents.parabricks_agent import ParabricksAgent
from src.agents.vcf_analysis_agent import VCFAnalysisAgent
from src.agents.llm_training_agent import LLMTrainingAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.report_agent import ReportGeneratorAgent
from src.schemas.pipeline import PipelineContext
from src.utils.gpu_manager import get_gpu_manager


class MCPToolBridge:
    """Exécute les tools MCP en déléguant aux agents + contexte partagé."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.gpu = get_gpu_manager()
        self.ctx = PipelineContext(patient_id="unknown")
        self._agents = {
            "data_manager": DataManagerAgent(config),
            "genomic_pipeline": ParabricksAgent(config),
            "vcf_analysis": VCFAnalysisAgent(config),
            "llm_training": LLMTrainingAgent(config),
            "prediction": PredictionAgent(config),
            "report": ReportGeneratorAgent(config),
        }

    def init_context(self, data: Dict[str, Any]) -> None:
        from src.utils.validators import resolve_fastq_r2_path, validate_fastq_paths_distinct

        payload = dict(data)
        if not payload.get("vcf_s3"):
            r1 = payload.get("fastq_r1_s3") or payload.get("fastq_r1")
            r2 = payload.get("fastq_r2_s3") or payload.get("fastq_r2")
            if r1:
                if not r2:
                    r2 = resolve_fastq_r2_path(r1, None)
                r1, r2 = validate_fastq_paths_distinct(r1, r2)
                payload["fastq_r1"] = r1
                payload["fastq_r2"] = r2
                payload["fastq_r1_s3"] = r1
                payload["fastq_r2_s3"] = r2
        self.ctx = PipelineContext.from_agent_dict(payload)

    def get_context_dict(self) -> Dict[str, Any]:
        return self.ctx.to_agent_dict()

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """Appel style MCP tools/call — retourne JSON string."""
        args = arguments or {}
        merged = {**self.ctx.to_agent_dict(), **args}
        self.ctx = PipelineContext.from_agent_dict(merged)

        if name == "genomic_pipeline":
            self.gpu.prepare_for_parabricks()
        elif name == "prediction":
            self.gpu.prepare_for_biogpt()

        agent_key = name
        agent = self._agents.get(agent_key)
        if agent is None:
            return json.dumps({"error": f"unknown tool: {name}"})

        logger.info(f"[MCP] tools/call name={name} patient={self.ctx.patient_id}")
        result = agent.run(self.ctx.to_agent_dict())

        if result.success and result.data:
            self.ctx.merge_agent_result(result.data)

        self.gpu.after_agent_step(name, result.execution_time)

        payload = {
            "tool": name,
            "success": result.success,
            "error": result.error,
            "execution_time": result.execution_time,
            "context": self.ctx.to_agent_dict(),
        }
        return json.dumps(payload, default=str)
