"""Base class for all agents in the Agentic AI system."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


class AgentStatus(Enum):
    """Status of an agent."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class AgentResult:
    """Result from an agent execution."""
    success: bool
    status: AgentStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for all agents in the system."""

    def __init__(self, agent_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize base agent.

        Args:
            agent_name: Name of the agent
            config: Optional configuration dictionary
        """
        self.agent_name = agent_name
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self.result: Optional[AgentResult] = None
        self.logger = logger.bind(agent=agent_name)

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute the agent's main task.

        Args:
            context: Context dictionary with input data and previous results

        Returns:
            AgentResult with execution results
        """
        pass

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """
        Validate input context.

        Args:
            context: Context dictionary

        Returns:
            True if valid, False otherwise
        """
        return True

    def pre_execute(self, context: Dict[str, Any]) -> None:
        """
        Pre-execution hook.

        Args:
            context: Context dictionary
        """
        self.status = AgentStatus.RUNNING
        self.logger.info(f"Agent {self.agent_name} starting execution")

    def post_execute(self, result: AgentResult) -> None:
        """
        Post-execution hook.

        Args:
            result: Execution result
        """
        if result.success:
            self.status = AgentStatus.COMPLETED
            self.logger.info(f"Agent {self.agent_name} completed successfully")
        else:
            self.status = AgentStatus.FAILED
            self.logger.error(f"Agent {self.agent_name} failed: {result.error}")

    def run(self, context: Dict[str, Any]) -> AgentResult:
        """
        Run the agent with validation and hooks.

        Args:
            context: Context dictionary

        Returns:
            AgentResult
        """
        start_time = datetime.now()

        try:
            # Validate input
            if not self.validate_input(context):
                return AgentResult(
                    success=False,
                    status=AgentStatus.FAILED,
                    error="Input validation failed"
                )

            # Pre-execute hook
            self.pre_execute(context)

            # Execute main task
            result = self.execute(context)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time

            # Post-execute hook
            self.post_execute(result)

            self.result = result
            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.status = AgentStatus.FAILED
            error_msg = f"Agent {self.agent_name} raised exception: {e}"
            self.logger.error(error_msg)

            result = AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                error=error_msg,
                execution_time=execution_time
            )
            self.result = result
            return result

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the agent.

        Returns:
            Status dictionary
        """
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "has_result": self.result is not None,
            "result_success": self.result.success if self.result else None,
            "execution_time": self.result.execution_time if self.result else None,
        }




