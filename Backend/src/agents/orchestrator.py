"""Orchestrator Agent — Mistral 8B (Ollama) + harness déterministe."""

from datetime import datetime
from typing import Dict, Any, List, Optional

from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.agents.data_manager import DataManagerAgent
from src.agents.parabricks_agent import ParabricksAgent
from src.agents.vcf_analysis_agent import VCFAnalysisAgent
from src.agents.llm_training_agent import LLMTrainingAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.report_agent import ReportGeneratorAgent
from src.llm.ollama_client import OllamaClient
from src.schemas.pipeline import (
    AgentStepName,
    AgentStepResult,
    PipelineContext,
    PipelineState,
)
from src.utils.gpu_manager import get_gpu_manager


class OrchestratorAgent(BaseAgent):
    """Orchestrateur : Mistral (Ollama) planifie, exécution séquentielle stricte."""

    STEPS: List[AgentStepName] = [
        AgentStepName.DATA_MANAGER,
        AgentStepName.PARABRICKS,
        AgentStepName.VCF_ANALYSIS,
        AgentStepName.LLM_TRAINING,
        AgentStepName.PREDICTION,
        AgentStepName.REPORT,
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("Orchestrator", config)
        self.gpu = get_gpu_manager()
        self.ollama = OllamaClient()
        self.data_manager = DataManagerAgent(config)
        self.parabricks_agent = ParabricksAgent(config)
        self.vcf_analysis_agent = VCFAnalysisAgent(config)
        self.llm_training_agent = LLMTrainingAgent(config)
        self.prediction_agent = PredictionAgent(config)
        self.report_agent = ReportGeneratorAgent(config)
        self._agents = {
            AgentStepName.DATA_MANAGER: self.data_manager,
            AgentStepName.PARABRICKS: self.parabricks_agent,
            AgentStepName.VCF_ANALYSIS: self.vcf_analysis_agent,
            AgentStepName.LLM_TRAINING: self.llm_training_agent,
            AgentStepName.PREDICTION: self.prediction_agent,
            AgentStepName.REPORT: self.report_agent,
        }
        self._transition_log: List[Dict[str, Any]] = []

    def validate_input(self, context: Dict[str, Any]) -> bool:
        if not context.get("patient_id"):
            self.logger.error("patient_id manquant")
            return False
        has_fastq = any(
            context.get(k)
            for k in ("fastq_r1", "fastq_r1_s3", "fastq_r1_path")
        )
        if not has_fastq and not context.get("vcf_s3"):
            self.logger.error("FASTQ ou vcf_s3 requis")
            return False
        return True

    def _log_transition(self, agent: str, phase: str, duration_s: Optional[float] = None) -> None:
        entry = self.gpu.log_transition(agent, phase, duration_s)
        self._transition_log.append(entry)

    def _pre_step(self, step: AgentStepName) -> None:
        if step == AgentStepName.PARABRICKS:
            self.gpu.prepare_for_parabricks()
        elif step == AgentStepName.PREDICTION:
            self.gpu.prepare_for_biogpt()
        elif step == AgentStepName.LLM_TRAINING:
            self.gpu.suspend_ollama_models()
        self._log_transition(step.value, "START")

    def _post_step(self, step: AgentStepName, duration_s: float) -> None:
        if step == AgentStepName.PREDICTION and self.prediction_agent.inference_engine:
            self.prediction_agent.inference_engine.unload_model()
        self.gpu.after_agent_step(step.value, duration_s)

    def _run_step(
        self,
        step: AgentStepName,
        ctx: PipelineContext,
        optional: bool = False,
    ) -> AgentStepResult:
        t0 = datetime.now()
        self._pre_step(step)
        agent = self._agents[step]
        raw = agent.run(ctx.to_agent_dict())
        elapsed = (datetime.now() - t0).total_seconds()
        self._post_step(step, elapsed)

        if raw.success and raw.data:
            ctx.merge_agent_result(raw.data)
            ctx.steps_completed.append(step)

        state = PipelineState.COMPLETED if raw.success else PipelineState.FAILED
        if optional and not raw.success:
            state = PipelineState.SKIPPED

        return AgentStepResult(
            step=step,
            state=state,
            success=raw.success,
            execution_time=elapsed,
            error=raw.error,
            data=raw.data or {},
        )

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        pipeline_start = datetime.now()
        ctx = PipelineContext.from_agent_dict(context)
        ctx.state = PipelineState.RUNNING
        step_results: Dict[str, AgentStepResult] = {}
        skip_genomic = bool(ctx.vcf_s3)

        self._log_transition("orchestrator", "PIPELINE_START")
        plan = self.ollama.plan_pipeline(
            patient_id=ctx.patient_id,
            has_fastq=not skip_genomic,
            has_vcf=skip_genomic,
        )
        self.logger.info(f"Plan Mistral: {plan}")

        try:
            if not skip_genomic:
                for step in (AgentStepName.DATA_MANAGER, AgentStepName.PARABRICKS):
                    self.logger.info("=" * 60)
                    self.logger.info(f"STEP: {step.value}")
                    self.logger.info("=" * 60)
                    if not self.ollama.validate_step(step.value, f"patient={ctx.patient_id}"):
                        self.logger.warning(f"Mistral NO pour {step.value} — exécution forcée")
                    result = self._run_step(step, ctx)
                    step_results[step.value] = result
                    if not result.success:
                        ctx.state = PipelineState.FAILED
                        return self._fail(ctx, step_results, pipeline_start, result.error)
            else:
                for step in (AgentStepName.DATA_MANAGER, AgentStepName.PARABRICKS):
                    step_results[step.value] = AgentStepResult(
                        step=step,
                        state=PipelineState.SKIPPED,
                        success=True,
                        execution_time=0.0,
                    )

            for step, optional in (
                (AgentStepName.VCF_ANALYSIS, False),
                (AgentStepName.LLM_TRAINING, True),
                (AgentStepName.PREDICTION, False),
                (AgentStepName.REPORT, True),
            ):
                self.logger.info("=" * 60)
                self.logger.info(f"STEP: {step.value}")
                self.logger.info("=" * 60)
                result = self._run_step(step, ctx, optional=optional)
                step_results[step.value] = result
                if not result.success and not optional:
                    ctx.state = PipelineState.FAILED
                    return self._fail(ctx, step_results, pipeline_start, result.error)

            self.gpu.suspend_ollama_models()
            ctx.state = PipelineState.COMPLETED
            total = (datetime.now() - pipeline_start).total_seconds()
            self._log_transition("orchestrator", "PIPELINE_COMPLETE", total)

            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "patient_id": ctx.patient_id,
                    "pipeline_state": ctx.state.value,
                    "orchestrator_plan": plan,
                    "gpu_transitions": self._transition_log,
                    "steps": {k: v.model_dump() for k, v in step_results.items()},
                    "total_execution_time": total,
                    "results": ctx.prediction_results.model_dump() if ctx.prediction_results else {},
                    "report_path": ctx.report_path,
                    "report_s3": ctx.report_s3,
                    "vcf_s3": ctx.vcf_s3,
                    "bam_s3": ctx.bam_recal_s3 or ctx.bam_s3,
                },
                execution_time=total,
            )
        except Exception as e:
            ctx.state = PipelineState.FAILED
            return self._fail(ctx, step_results, pipeline_start, str(e))
        finally:
            self.gpu.suspend_ollama_models()
            self.gpu.empty_cuda_cache()

    def _fail(
        self,
        ctx: PipelineContext,
        steps: Dict[str, AgentStepResult],
        start: datetime,
        error: Optional[str],
    ) -> AgentResult:
        total = (datetime.now() - start).total_seconds()
        self._log_transition("orchestrator", "PIPELINE_FAILED", total)
        self.logger.error(f"Pipeline échoué: {error}")
        return AgentResult(
            success=False,
            status=AgentStatus.FAILED,
            data={
                "patient_id": ctx.patient_id,
                "pipeline_state": PipelineState.FAILED.value,
                "gpu_transitions": self._transition_log,
                "steps": {k: v.model_dump() for k, v in steps.items()},
                "total_execution_time": total,
            },
            error=error,
            execution_time=total,
        )

    def get_pipeline_status(self) -> Dict[str, Any]:
        return {
            "orchestrator": self.get_status(),
            "orchestrator_model": self.ollama.model,
            "vram": self.gpu.get_vram_stats(),
            "agents": {name.value: a.get_status() for name, a in self._agents.items()},
        }
