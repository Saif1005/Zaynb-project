"""Tests for agents."""

import pytest
from src.agents.base_agent import BaseAgent, AgentStatus, AgentResult
from src.agents.data_manager import DataManagerAgent


class TestBaseAgent:
    """Test base agent functionality."""
    
    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = BaseAgent("TestAgent")
        assert agent.agent_name == "TestAgent"
        assert agent.status == AgentStatus.IDLE
    
    def test_agent_status(self):
        """Test agent status tracking."""
        agent = BaseAgent("TestAgent")
        status = agent.get_status()
        assert status["agent_name"] == "TestAgent"
        assert status["status"] == "idle"


class TestDataManagerAgent:
    """Test Data Manager Agent."""
    
    def test_agent_creation(self):
        """Test Data Manager Agent creation."""
        agent = DataManagerAgent()
        assert agent.agent_name == "DataManager"
    
    def test_validate_input(self):
        """Test input validation."""
        agent = DataManagerAgent()
        # Should fail without patient_id
        assert not agent.validate_input({})
        # Should pass with fastq_r1
        assert agent.validate_input({"fastq_r1": "test.fastq.gz"})


if __name__ == "__main__":
    pytest.main([__file__])








