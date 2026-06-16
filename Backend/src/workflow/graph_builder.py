"""Construction du graphe LangGraph déterministe — pipeline cancer du sein."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator

from src.agents.base_agent import AgentResult, AgentStatus
from src.agents.data_manager import DataManagerAgent
from src.agents.parabricks_agent import ParabricksAgent
from src.agents.vcf_analysis_agent import VCFAnalysisAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.report_agent import ReportGeneratorAgent
from src.schemas.pipeline import AgentStepName, PipelineContext, PipelineState
from src.utils.gpu_manager import get_gpu_manager
from src.utils.validators import resolve_fastq_r2_path, validate_fastq_paths_distinct, ValidationError

try:
    from langgraph.graph import StateGraph, END

    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    StateGraph = None  # type: ignore
    END = None  # type: ignore


DETERMINISTIC_SEQUENCE: List[AgentStepName] = [
    AgentStepName.DATA_MANAGER,
    AgentStepName.PARABRICKS,
    AgentStepName.VCF_ANALYSIS,
    AgentStepName.PREDICTION,
    AgentStepName.REPORT,
]

VCF_ONLY_SEQUENCE: List[AgentStepName] = [
    AgentStepName.VCF_ANALYSIS,
    AgentStepName.PREDICTION,
    AgentStepName.REPORT,
]

STEP_TO_NODE: Dict[AgentStepName, str] = {
    AgentStepName.DATA_MANAGER: "data_manager",
    AgentStepName.PARABRICKS: "parabricks",
    AgentStepName.VCF_ANALYSIS: "vcf_analysis",
    AgentStepName.PREDICTION: "prediction",
    AgentStepName.REPORT: "report",
}


class PipelineGraphState(BaseModel):
    """État global typé Pydantic — transfert inter-nœuds LangGraph."""

    context: PipelineContext
    current_step: Optional[str] = None
    steps_completed: List[str] = Field(default_factory=list)
    step_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    last_error: Optional[str] = None
    finished: bool = False
    gpu_transitions: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_paths(self) -> "PipelineGraphState":
        ctx = self.context
        if ctx.vcf_s3:
            return self
        r1 = ctx.fastq_r1_s3 or ctx.fastq_r1
        r2 = ctx.fastq_r2_s3 or ctx.fastq_r2
        if r1 and r2 and r1 == r2:
            raise ValueError(f"fastq_r1 et fastq_r2 identiques: {r1}")
        return self

    def to_graph_dict(self) -> Dict[str, Any]:
        return {
            "context": self.context.to_agent_dict(),
            "current_step": self.current_step,
            "steps_completed": list(self.steps_completed),
            "step_results": dict(self.step_results),
            "last_error": self.last_error,
            "finished": self.finished,
            "gpu_transitions": list(self.gpu_transitions),
        }

    @classmethod
    def from_graph_dict(cls, data: Dict[str, Any]) -> "PipelineGraphState":
        ctx_raw = data.get("context", {})
        return cls(
            context=PipelineContext.from_agent_dict(ctx_raw),
            current_step=data.get("current_step"),
            steps_completed=list(data.get("steps_completed", [])),
            step_results=dict(data.get("step_results", {})),
            last_error=data.get("last_error"),
            finished=bool(data.get("finished", False)),
            gpu_transitions=list(data.get("gpu_transitions", [])),
        )


class GenomicGraphRunner:
    """Exécuteur séquentiel des agents avec verrouillage VRAM."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.gpu = get_gpu_manager()
        self.on_step = self.config.get("on_step")
        self._agents = {
            AgentStepName.DATA_MANAGER: DataManagerAgent(config),
            AgentStepName.PARABRICKS: ParabricksAgent(config),
            AgentStepName.VCF_ANALYSIS: VCFAnalysisAgent(config),
            AgentStepName.PREDICTION: PredictionAgent(config),
            AgentStepName.REPORT: ReportGeneratorAgent(config),
        }

    def _sequence(self, ctx: PipelineContext) -> List[AgentStepName]:
        return VCF_ONLY_SEQUENCE if ctx.vcf_s3 else DETERMINISTIC_SEQUENCE

    def _pre_step(self, step: AgentStepName) -> None:
        if step == AgentStepName.PARABRICKS:
            self.gpu.prepare_for_parabricks()
        elif step == AgentStepName.PREDICTION:
            self.gpu.prepare_for_biogpt()

    def _post_step(self, step: AgentStepName, duration: float) -> None:
        if step == AgentStepName.PARABRICKS:
            self.gpu.release_after_parabricks()
        elif step == AgentStepName.PREDICTION:
            agent = self._agents[AgentStepName.PREDICTION]
            if getattr(agent, "inference_engine", None):
                agent.inference_engine.unload_model()
        self.gpu.after_agent_step(STEP_TO_NODE[step], duration)

    def run_step(self, state: PipelineGraphState, step: AgentStepName) -> PipelineGraphState:
        node = STEP_TO_NODE[step]
        ctx = state.context
        ctx.state = PipelineState.RUNNING
        t0 = datetime.now()

        self._pre_step(step)
        state.current_step = node
        if self.on_step:
            self.on_step(node, "running")
        self.gpu.log_transition(node, "START")

        agent = self._agents[step]
        agent_ctx = ctx.to_agent_dict()
        agent_ctx["steps_completed"] = list(state.steps_completed)
        agent_ctx["execution_time"] = sum(
            r.get("execution_time", 0) for r in state.step_results.values()
        )
        result: AgentResult = agent.run(agent_ctx)
        elapsed = (datetime.now() - t0).total_seconds()
        self._post_step(step, elapsed)

        transition = self.gpu.log_transition(node, "COMPLETE", elapsed)
        state.gpu_transitions.append(transition)
        if self.on_step:
            self.on_step(node, "completed", elapsed)

        if result.success and result.data:
            ctx.merge_agent_result(result.data)
            if step == AgentStepName.REPORT:
                ctx.extra["clinical_report"] = result.data.get("clinical_report")
            state.steps_completed.append(node)
            state.step_results[node] = {
                "success": True,
                "execution_time": elapsed,
                "data": result.data,
            }
            state.last_error = None
        else:
            state.last_error = result.error or f"{node} failed"
            state.finished = True
            ctx.state = PipelineState.FAILED
            state.step_results[node] = {
                "success": False,
                "execution_time": elapsed,
                "error": state.last_error,
            }
        state.context = ctx
        return state

    def run_all(self, initial_context: Dict[str, Any]) -> PipelineGraphState:
        payload = dict(initial_context)
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

        state = PipelineGraphState(context=PipelineContext.from_agent_dict(payload))
        for step in self._sequence(state.context):
            state = self.run_step(state, step)
            if state.last_error:
                break

        if not state.last_error:
            state.context.state = PipelineState.COMPLETED
            state.finished = True
        self.gpu.suspend_ollama_models()
        self.gpu.empty_cuda_cache()
        return state


def _make_node_fn(runner: GenomicGraphRunner, step: AgentStepName) -> Callable[[Dict], Dict]:
    def node(state_dict: Dict[str, Any]) -> Dict[str, Any]:
        gs = PipelineGraphState.from_graph_dict(state_dict)
        if gs.last_error or gs.finished:
            return gs.to_graph_dict()
        gs = runner.run_step(gs, step)
        return gs.to_graph_dict()

    return node


def build_genomic_graph(config: Optional[Dict[str, Any]] = None):
    """Construit le graphe LangGraph séquentiel déterministe."""
    if not HAS_LANGGRAPH:
        raise ImportError("LangGraph requis: pip install -r requirements-langchain.txt")

    runner = GenomicGraphRunner(config)
    g = StateGraph(dict)

    def route_sequence(state_dict: Dict[str, Any]) -> str:
        gs = PipelineGraphState.from_graph_dict(state_dict)
        if gs.last_error or gs.finished:
            return "end"
        seq = runner._sequence(gs.context)
        done = set(gs.steps_completed)
        for step in seq:
            node = STEP_TO_NODE[step]
            if node not in done:
                return node
        return "end"

    for step in DETERMINISTIC_SEQUENCE:
        node_name = STEP_TO_NODE[step]
        g.add_node(node_name, _make_node_fn(runner, step))

    g.set_entry_point(STEP_TO_NODE[AgentStepName.DATA_MANAGER])
    g.add_conditional_edges(
        STEP_TO_NODE[AgentStepName.DATA_MANAGER],
        route_sequence,
        {
            STEP_TO_NODE[AgentStepName.PARABRICKS]: STEP_TO_NODE[AgentStepName.PARABRICKS],
            STEP_TO_NODE[AgentStepName.VCF_ANALYSIS]: STEP_TO_NODE[AgentStepName.VCF_ANALYSIS],
            "end": END,
        },
    )
    g.add_conditional_edges(
        STEP_TO_NODE[AgentStepName.PARABRICKS],
        route_sequence,
        {
            STEP_TO_NODE[AgentStepName.VCF_ANALYSIS]: STEP_TO_NODE[AgentStepName.VCF_ANALYSIS],
            "end": END,
        },
    )
    g.add_conditional_edges(
        STEP_TO_NODE[AgentStepName.VCF_ANALYSIS],
        route_sequence,
        {
            STEP_TO_NODE[AgentStepName.PREDICTION]: STEP_TO_NODE[AgentStepName.PREDICTION],
            "end": END,
        },
    )
    g.add_conditional_edges(
        STEP_TO_NODE[AgentStepName.PREDICTION],
        route_sequence,
        {
            STEP_TO_NODE[AgentStepName.REPORT]: STEP_TO_NODE[AgentStepName.REPORT],
            "end": END,
        },
    )
    g.add_edge(STEP_TO_NODE[AgentStepName.REPORT], END)
    return g.compile()


def run_genomic_pipeline(
    context: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    use_langgraph: bool = True,
) -> PipelineGraphState:
    """Point d'entrée — graphe LangGraph ou exécution séquentielle directe."""
    runner = GenomicGraphRunner(config)
    if use_langgraph and HAS_LANGGRAPH and not context.get("vcf_s3"):
        try:
            graph = build_genomic_graph(config)
            final = graph.invoke({"context": context, "steps_completed": [], "finished": False})
            return PipelineGraphState.from_graph_dict(final)
        except Exception as e:
            logger.warning(f"LangGraph invoke fallback séquentiel: {e}")
    return runner.run_all(context)
