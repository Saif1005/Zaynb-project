"""Pydantic models for API requests and responses."""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class PatientRequest(BaseModel):
    """Request model for patient data upload."""
    patient_id: str = Field(..., description="Patient identifier")
    metadata: Optional[dict] = Field(None, description="Additional patient metadata")


class PipelineResponse(BaseModel):
    """Response model for pipeline execution."""
    success: bool
    patient_id: str
    status: str
    execution_time: float
    results: Optional[dict] = None
    report_path: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PipelineStatus(BaseModel):
    """Status model for pipeline execution."""
    patient_id: str
    status: str
    current_step: Optional[str] = None
    progress: float = Field(0.0, ge=0.0, le=100.0)
    steps_completed: List[str] = Field(default_factory=list)
    steps_remaining: List[str] = Field(default_factory=list)
    estimated_time_remaining: Optional[float] = None








