# Step Functions for Pipeline Orchestration

resource "aws_sfn_state_machine" "pipeline_orchestrator" {
  name     = "${var.environment}-genomic-pipeline-orchestrator"
  role_arn = aws_iam_role.stepfunctions.arn

  definition = jsonencode({
    Comment = "Genomic Cancer Detection Pipeline Orchestrator"
    StartAt = "DataManager"
    States = {
      DataManager = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.data_manager_lambda_arn
          Payload = {
            "patient_id.$" = "$.patient_id"
            "fastq_r1.$"   = "$.fastq_r1"
            "fastq_r2.$"   = "$.fastq_r2"
          }
        }
        Next = "Parabricks"
        Retry = [{
          ErrorEquals     = ["States.ALL"]
          IntervalSeconds = 2
          MaxAttempts     = 3
          BackoffRate     = 2.0
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          ResultPath  = "$.error"
          Next        = "PipelineFailed"
        }]
      }
      Parabricks = {
        Type     = "Task"
        Resource = "arn:aws:ecs:runTask.sync"
        Parameters = {
          Cluster        = var.ecs_cluster_arn
          TaskDefinition = var.parabricks_task_definition_arn
          LaunchType     = "FARGATE"
          NetworkConfiguration = {
            AwsvpcConfiguration = {
              Subnets        = var.subnet_ids
              SecurityGroups = [var.security_group_id]
              AssignPublicIp = "ENABLED"
            }
          }
          Overrides = {
            ContainerOverrides = [{
              Name = "parabricks"
              Environment = [
                {
                  Name  = "FASTQ_R1"
                  Value.$ = "$.fastq_r1_s3"
                },
                {
                  Name  = "FASTQ_R2"
                  Value.$ = "$.fastq_r2_s3"
                }
              ]
            }]
          }
        }
        Next = "VCFAnalysis"
        Retry = [{
          ErrorEquals     = ["States.ALL"]
          IntervalSeconds = 60
          MaxAttempts     = 2
          BackoffRate     = 2.0
        }]
      }
      VCFAnalysis = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.vcf_analysis_lambda_arn
          Payload = {
            "vcf_s3.$" = "$.vcf_s3"
            "patient_id.$" = "$.patient_id"
          }
        }
        Next = "LLMTraining"
      }
      LLMTraining = {
        Type     = "Choice"
        Choices = [{
          Variable      = "$.train_llm"
          BooleanEquals = true
          Next          = "TrainModel"
        }]
        Default = "Prediction"
      }
      TrainModel = {
        Type     = "Task"
        Resource = "arn:aws:ecs:runTask.sync"
        Parameters = {
          Cluster        = var.ecs_cluster_arn
          TaskDefinition = var.llm_training_task_definition_arn
          LaunchType     = "EC2"
          NetworkConfiguration = {
            AwsvpcConfiguration = {
              Subnets        = var.subnet_ids
              SecurityGroups = [var.security_group_id]
            }
          }
        }
        Next = "Prediction"
      }
      Prediction = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.prediction_lambda_arn
          Payload = {
            "variants.$" = "$.variants"
            "patient_id.$" = "$.patient_id"
            "model_path.$" = "$.model_path"
          }
        }
        Next = "ReportGenerator"
      }
      ReportGenerator = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.report_generator_lambda_arn
          Payload = {
            "patient_id.$" = "$.patient_id"
            "results.$" = "$.prediction_results"
          }
        }
        End = true
      }
      PipelineFailed = {
        Type = "Fail"
        Error = "PipelineExecutionFailed"
        Cause = "One or more pipeline steps failed"
      }
    }
  })

  tags = {
    Name = "${var.environment}-genomic-pipeline-orchestrator"
  }
}

# IAM Role for Step Functions
resource "aws_iam_role" "stepfunctions" {
  name = "${var.environment}-genomic-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "stepfunctions" {
  name = "${var.environment}-genomic-stepfunctions-policy"
  role = aws_iam_role.stepfunctions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
          "ecs:RunTask",
          "ecs:StopTask",
          "ecs:DescribeTasks",
          "iam:PassRole"
        ]
        Resource = "*"
      }
    ]
  })
}




