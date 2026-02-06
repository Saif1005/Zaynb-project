"""FastAPI routes unifiées pour local et AWS."""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional
import os
import boto3
import json
import uuid
from datetime import datetime
from pathlib import Path
import tempfile
from loguru import logger

from src.api.models import PatientRequest, PipelineResponse, PipelineStatus
from src.aws.s3_manager import get_s3_manager
from config.aws_config import aws_config
from config.logging_config import logging_config

# Setup logging
logging_config.setup_logging()

# Detect environment
USE_AWS = os.getenv("USE_AWS", "false").lower() == "true"

# Initialize AWS clients if in AWS mode
if USE_AWS:
    s3_manager = get_s3_manager()
    dynamodb = boto3.client('dynamodb', region_name=aws_config.region)
    sfn_client = boto3.client('stepfunctions', region_name=aws_config.region)
    from src.agents.orchestrator_aws import AWSOrchestratorAgent
else:
    # Local mode
    pipeline_executions = {}
    from src.agents.orchestrator import OrchestratorAgent

# Configuration
STATE_MACHINE_ARN = os.getenv("STEP_FUNCTIONS_ARN")
DYNAMODB_TABLE = f"genomic-pipeline-executions-{aws_config.region}"

# Initialize FastAPI app
app = FastAPI(
    title="Genomic Cancer Detection Pipeline API",
    description="API Agentic AI pour pipeline de détection de cancer" + (" (AWS)" if USE_AWS else " (Local)"),
    version="1.0.0"
)


@app.post("/api/v1/pipeline/upload", response_model=PipelineResponse)
async def upload_and_process(
    background_tasks: BackgroundTasks,
    patient_id: str,
    fastq_r1: UploadFile = File(...),
    fastq_r2: Optional[UploadFile] = File(None),
    train_llm: bool = False,
):
    """
    Upload FASTQ files and start pipeline via Step Functions (AWS) or directly (local).
    """
    execution_id = str(uuid.uuid4())
    
    try:
        # Upload files to S3
        s3_key_r1 = f"patients/{patient_id}/input/{fastq_r1.filename}"
        s3_key_r2 = f"patients/{patient_id}/input/{fastq_r2.filename}" if fastq_r2 else None
        
        # Save uploaded file temporarily and upload to S3
        with tempfile.NamedTemporaryFile(delete=False) as tmp_r1:
            content_r1 = await fastq_r1.read()
            tmp_r1.write(content_r1)
            tmp_r1.flush()
            
            if USE_AWS:
                fastq_r1_s3 = s3_manager.upload_file(
                    tmp_r1.name,
                    s3_key_r1,
                    bucket_name=aws_config.s3_input_bucket
                )
            else:
                fastq_r1_s3 = tmp_r1.name
        
        fastq_r2_s3 = None
        if fastq_r2:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_r2:
                content_r2 = await fastq_r2.read()
                tmp_r2.write(content_r2)
                tmp_r2.flush()
                
                if USE_AWS:
                    fastq_r2_s3 = s3_manager.upload_file(
                        tmp_r2.name,
                        s3_key_r2,
                        bucket_name=aws_config.s3_input_bucket
                    )
                else:
                    fastq_r2_s3 = tmp_r2.name
        
        # Store execution
        if USE_AWS:
            # Store in DynamoDB
            dynamodb.put_item(
                TableName=DYNAMODB_TABLE,
                Item={
                    "execution_id": {"S": execution_id},
                    "patient_id": {"S": patient_id},
                    "status": {"S": "started"},
                    "fastq_r1_s3": {"S": fastq_r1_s3},
                    "fastq_r2_s3": {"S": fastq_r2_s3 if fastq_r2_s3 else ""},
                    "train_llm": {"BOOL": train_llm},
                    "created_at": {"S": datetime.now().isoformat()},
                }
            )
        else:
            # Store in memory
            pipeline_executions[execution_id] = {
                "patient_id": patient_id,
                "status": "started",
                "fastq_r1_path": fastq_r1_s3,
                "fastq_r2_path": fastq_r2_s3,
                "train_llm": train_llm,
            }
        
        # Start pipeline execution
        if USE_AWS and STATE_MACHINE_ARN:
            # AWS mode: Use Step Functions
            orchestrator = AWSOrchestratorAgent(config={"state_machine_arn": STATE_MACHINE_ARN})
            result = orchestrator.execute({
                "patient_id": patient_id,
                "fastq_r1_s3": fastq_r1_s3,
                "fastq_r2_s3": fastq_r2_s3,
                "train_llm": train_llm,
                "instance_id": os.getenv("INSTANCE_ID", aws_config.ec2_instance_type),
            })
            
            if result.success:
                dynamodb.update_item(
                    TableName=DYNAMODB_TABLE,
                    Key={"execution_id": {"S": execution_id}},
                    UpdateExpression="SET execution_arn = :arn",
                    ExpressionAttributeValues={":arn": {"S": result.data["execution_arn"]}}
                )
        else:
            # Local mode: Run directly
            background_tasks.add_task(
                execute_pipeline_local,
                execution_id,
                patient_id,
                fastq_r1_s3,
                fastq_r2_s3,
                train_llm,
            )
        
        return PipelineResponse(
            success=True,
            patient_id=patient_id,
            status="started",
            execution_time=0.0,
            results={"execution_id": execution_id}
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/status/{execution_id}", response_model=PipelineStatus)
async def get_pipeline_status(execution_id: str):
    """Get status from DynamoDB (AWS) or memory (local)."""
    try:
        if USE_AWS:
            # AWS mode: Get from DynamoDB
            response = dynamodb.get_item(
                TableName=DYNAMODB_TABLE,
                Key={"execution_id": {"S": execution_id}}
            )
            
            if "Item" not in response:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            item = response["Item"]
            execution_arn = item.get("execution_arn", {}).get("S")
            
            # Get Step Functions status if available
            step_status = None
            if execution_arn:
                orchestrator = AWSOrchestratorAgent()
                step_status = orchestrator.get_execution_status(execution_arn)
            
            return PipelineStatus(
                patient_id=item["patient_id"]["S"],
                status=item["status"]["S"],
                current_step=step_status.get("status") if step_status else None,
                progress=50.0,
            )
        else:
            # Local mode: Get from memory
            if execution_id not in pipeline_executions:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            execution = pipeline_executions[execution_id]
            return PipelineStatus(
                patient_id=execution["patient_id"],
                status=execution.get("status", "unknown"),
                current_step=execution.get("current_step"),
                progress=execution.get("progress", 0.0),
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/result/{execution_id}", response_model=PipelineResponse)
async def get_pipeline_result(execution_id: str):
    """Get final result from DynamoDB (AWS) or memory (local)."""
    try:
        if USE_AWS:
            # AWS mode: Get from DynamoDB
            response = dynamodb.get_item(
                TableName=DYNAMODB_TABLE,
                Key={"execution_id": {"S": execution_id}}
            )
            
            if "Item" not in response:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            item = response["Item"]
            
            if item["status"]["S"] != "completed":
                raise HTTPException(status_code=400, detail="Pipeline not completed yet")
            
            results = json.loads(item.get("results", {}).get("S", "{}"))
            
            return PipelineResponse(
                success=item.get("success", {}).get("BOOL", False),
                patient_id=item["patient_id"]["S"],
                status=item["status"]["S"],
                execution_time=float(item.get("execution_time", {}).get("N", "0")),
                results=results,
                report_path=item.get("report_path", {}).get("S"),
            )
        else:
            # Local mode: Get from memory
            if execution_id not in pipeline_executions:
                raise HTTPException(status_code=404, detail="Execution not found")
            
            execution = pipeline_executions[execution_id]
            
            if execution["status"] != "completed":
                raise HTTPException(status_code=400, detail="Pipeline not completed yet")
            
            return PipelineResponse(
                success=execution.get("success", False),
                patient_id=execution["patient_id"],
                status=execution["status"],
                execution_time=execution.get("execution_time", 0.0),
                results=execution.get("results"),
                report_path=execution.get("report_path"),
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def execute_pipeline_local(
    execution_id: str,
    patient_id: str,
    fastq_r1_path: str,
    fastq_r2_path: Optional[str],
    train_llm: bool,
):
    """Execute pipeline in background (local mode)."""
    try:
        pipeline_executions[execution_id]["status"] = "running"
        
        context = {
            "patient_id": patient_id,
            "fastq_r1": fastq_r1_path,
            "fastq_r2": fastq_r2_path,
            "instance_id": os.getenv("INSTANCE_ID"),
            "ssh_key": os.getenv("SSH_KEY_PATH"),
            "train_llm": train_llm,
        }
        
        config = {
            "instance_id": os.getenv("INSTANCE_ID"),
            "ssh_key": os.getenv("SSH_KEY_PATH"),
            "auto_train": train_llm,
        }
        
        orchestrator = OrchestratorAgent(config=config)
        result = orchestrator.run(context)
        
        pipeline_executions[execution_id].update({
            "status": "completed" if result.success else "failed",
            "success": result.success,
            "execution_time": result.execution_time,
            "results": result.data.get("results"),
            "report_path": result.data.get("report_path"),
            "error": result.error,
        })
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        pipeline_executions[execution_id].update({
            "status": "failed",
            "success": False,
            "error": str(e),
        })


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Genomic Cancer Detection Pipeline API",
        "version": "1.0.0",
        "mode": "AWS" if USE_AWS else "Local",
        "region": aws_config.region if USE_AWS else None,
        "endpoints": {
            "upload": "/api/v1/pipeline/upload",
            "status": "/api/v1/pipeline/status/{execution_id}",
            "result": "/api/v1/pipeline/result/{execution_id}",
        }
    }
