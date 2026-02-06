variable "environment" {
  description = "Environment name"
  type        = string
}

variable "data_manager_lambda_arn" {
  description = "Data Manager Lambda function ARN"
  type        = string
}

variable "vcf_analysis_lambda_arn" {
  description = "VCF Analysis Lambda function ARN"
  type        = string
}

variable "prediction_lambda_arn" {
  description = "Prediction Lambda function ARN"
  type        = string
}

variable "report_generator_lambda_arn" {
  description = "Report Generator Lambda function ARN"
  type        = string
}

variable "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  type        = string
}

variable "parabricks_task_definition_arn" {
  description = "Parabricks ECS task definition ARN"
  type        = string
}

variable "llm_training_task_definition_arn" {
  description = "LLM Training ECS task definition ARN"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID"
  type        = string
}








