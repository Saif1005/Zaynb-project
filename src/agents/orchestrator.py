"""Orchestrator Agent - Main coordinator for the Agentic AI pipeline."""

from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.agents.data_manager import DataManagerAgent
from src.agents.parabricks_agent import ParabricksAgent
from src.agents.vcf_analysis_agent import VCFAnalysisAgent
from src.agents.llm_training_agent import LLMTrainingAgent
from src.agents.prediction_agent import PredictionAgent
from src.agents.report_agent import ReportGeneratorAgent


class OrchestratorAgent(BaseAgent):
    """Main orchestrator that coordinates all agents in the pipeline."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize orchestrator agent.

        Args:
            config: Configuration dictionary
        """
        super().__init__("Orchestrator", config)
        
        # Initialize sub-agents
        self.data_manager = DataManagerAgent(config)
        self.parabricks_agent = ParabricksAgent(config)
        self.vcf_analysis_agent = VCFAnalysisAgent(config)
        self.llm_training_agent = LLMTrainingAgent(config)
        self.prediction_agent = PredictionAgent(config)
        self.report_agent = ReportGeneratorAgent(config)
        
        self.agents = [
            self.data_manager,
            self.parabricks_agent,
            self.vcf_analysis_agent,
            self.llm_training_agent,
            self.prediction_agent,
            self.report_agent,
        ]

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate input context."""
        required_fields = ["patient_id"]
        
        # Check for FASTQ files (either local paths or S3 URIs)
        has_fastq = (
            "fastq_r1" in context or 
            "fastq_r1_path" in context or
            "fastq_r1_s3" in context
        )
        
        if not has_fastq:
            self.logger.error("Missing FASTQ files in context")
            return False
        
        for field in required_fields:
            if field not in context:
                self.logger.error(f"Missing required field: {field}")
                return False
        
        return True

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute the complete pipeline by coordinating all agents.

        Args:
            context: Context with patient_id, FASTQ files, etc.

        Returns:
            AgentResult with complete pipeline results
        """
        pipeline_start = datetime.now()
        pipeline_results = {
            "patient_id": context.get("patient_id"),
            "pipeline_start": pipeline_start.isoformat(),
            "steps": {},
            "final_status": "unknown",
        }

        try:
            # STEP 1: Data Manager Agent - Upload and validate data
            self.logger.info("=" * 60)
            self.logger.info("STEP 1: Data Manager - Upload and Validation")
            self.logger.info("=" * 60)
            
            data_result = self.data_manager.run(context)
            pipeline_results["steps"]["data_manager"] = {
                "status": data_result.status.value,
                "success": data_result.success,
                "execution_time": data_result.execution_time,
            }
            
            if not data_result.success:
                return AgentResult(
                    success=False,
                    status=AgentStatus.FAILED,
                    data=pipeline_results,
                    error=f"Data Manager failed: {data_result.error}"
                )
            
            # Update context with data manager results
            context.update(data_result.data)

            # STEP 2: Parabricks Agent - Run genomic pipeline
            self.logger.info("=" * 60)
            self.logger.info("STEP 2: Parabricks - Genomic Pipeline")
            self.logger.info("=" * 60)
            
            parabricks_result = self.parabricks_agent.run(context)
            pipeline_results["steps"]["parabricks"] = {
                "status": parabricks_result.status.value,
                "success": parabricks_result.success,
                "execution_time": parabricks_result.execution_time,
            }
            
            if not parabricks_result.success:
                return AgentResult(
                    success=False,
                    status=AgentStatus.FAILED,
                    data=pipeline_results,
                    error=f"Parabricks failed: {parabricks_result.error}"
                )
            
            context.update(parabricks_result.data)

            # STEP 3: VCF Analysis Agent - Analyze variants
            self.logger.info("=" * 60)
            self.logger.info("STEP 3: VCF Analysis - Variant Analysis")
            self.logger.info("=" * 60)
            
            vcf_result = self.vcf_analysis_agent.run(context)
            pipeline_results["steps"]["vcf_analysis"] = {
                "status": vcf_result.status.value,
                "success": vcf_result.success,
                "execution_time": vcf_result.execution_time,
            }
            
            if not vcf_result.success:
                return AgentResult(
                    success=False,
                    status=AgentStatus.FAILED,
                    data=pipeline_results,
                    error=f"VCF Analysis failed: {vcf_result.error}"
                )
            
            context.update(vcf_result.data)

            # STEP 4: LLM Training Agent - Prepare data and train if needed
            self.logger.info("=" * 60)
            self.logger.info("STEP 4: LLM Training - Model Training")
            self.logger.info("=" * 60)
            
            llm_result = self.llm_training_agent.run(context)
            pipeline_results["steps"]["llm_training"] = {
                "status": llm_result.status.value,
                "success": llm_result.success,
                "execution_time": llm_result.execution_time,
            }
            
            # LLM training is optional, continue even if it fails
            if llm_result.success:
                context.update(llm_result.data)

            # STEP 5: Prediction Agent - Predict cancer
            self.logger.info("=" * 60)
            self.logger.info("STEP 5: Prediction - Cancer Prediction")
            self.logger.info("=" * 60)
            
            prediction_result = self.prediction_agent.run(context)
            pipeline_results["steps"]["prediction"] = {
                "status": prediction_result.status.value,
                "success": prediction_result.success,
                "execution_time": prediction_result.execution_time,
            }
            
            if not prediction_result.success:
                return AgentResult(
                    success=False,
                    status=AgentStatus.FAILED,
                    data=pipeline_results,
                    error=f"Prediction failed: {prediction_result.error}"
                )
            
            context.update(prediction_result.data)

            # STEP 6: Report Generator Agent - Generate final report
            self.logger.info("=" * 60)
            self.logger.info("STEP 6: Report Generator - Final Report")
            self.logger.info("=" * 60)
            
            report_result = self.report_agent.run(context)
            pipeline_results["steps"]["report"] = {
                "status": report_result.status.value,
                "success": report_result.success,
                "execution_time": report_result.execution_time,
            }
            
            # Report generation is optional
            if report_result.success:
                context.update(report_result.data)

            # Finalize pipeline results
            pipeline_end = datetime.now()
            total_time = (pipeline_end - pipeline_start).total_seconds()
            
            pipeline_results["pipeline_end"] = pipeline_end.isoformat()
            pipeline_results["total_execution_time"] = total_time
            pipeline_results["final_status"] = "completed"
            pipeline_results["results"] = context.get("prediction_results", {})
            pipeline_results["report_path"] = context.get("report_path")

            self.logger.info("=" * 60)
            self.logger.info("Pipeline completed successfully!")
            self.logger.info(f"Total time: {total_time:.2f} seconds")
            self.logger.info("=" * 60)

            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data=pipeline_results,
                execution_time=total_time
            )

        except Exception as e:
            pipeline_end = datetime.now()
            total_time = (pipeline_end - pipeline_start).total_seconds()
            
            pipeline_results["pipeline_end"] = pipeline_end.isoformat()
            pipeline_results["total_execution_time"] = total_time
            pipeline_results["final_status"] = "failed"
            
            error_msg = f"Pipeline failed: {e}"
            self.logger.error(error_msg)
            
            return AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                data=pipeline_results,
                error=error_msg,
                execution_time=total_time
            )

    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get status of all agents in the pipeline.

        Returns:
            Dictionary with status of all agents
        """
        return {
            "orchestrator": self.get_status(),
            "agents": {agent.agent_name: agent.get_status() for agent in self.agents}
        }








