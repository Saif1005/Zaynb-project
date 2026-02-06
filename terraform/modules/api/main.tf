# API Module - ECS Fargate for FastAPI

resource "aws_ecs_cluster" "api_cluster" {
  name = "${var.environment}-genomic-api-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.environment}-genomic-api-cluster"
  }
}

# ECS Task Definition for API
resource "aws_ecs_task_definition" "api_task" {
  family                   = "${var.environment}-genomic-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512  # 0.5 vCPU
  memory                   = 1024  # 1 GB
  execution_role_arn       = var.execution_role_arn
  task_role_arn           = var.task_role_arn

  container_definitions = jsonencode([
    {
      name  = "api"
      image = var.api_image_uri

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "AWS_REGION"
          value = var.region
        },
        {
          name  = "ENVIRONMENT"
          value = var.environment
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api_logs.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])

  tags = {
    Name = "${var.environment}-genomic-api-task"
  }
}

# ECS Service
resource "aws_ecs_service" "api_service" {
  name            = "${var.environment}-genomic-api-service"
  cluster         = aws_ecs_cluster.api_cluster.id
  task_definition = aws_ecs_task_definition.api_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.api_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api_tg.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.api_listener]
}

# Application Load Balancer
resource "aws_lb" "api_lb" {
  name               = "${var.environment}-genomic-api-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.api_lb_sg.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false

  tags = {
    Name = "${var.environment}-genomic-api-lb"
  }
}

# Target Group
resource "aws_lb_target_group" "api_tg" {
  name     = "${var.environment}-genomic-api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/"
    protocol            = "HTTP"
    matcher             = "200"
  }

  tags = {
    Name = "${var.environment}-genomic-api-tg"
  }
}

# Listener
resource "aws_lb_listener" "api_listener" {
  load_balancer_arn = aws_lb.api_lb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_tg.arn
  }
}

# Security Groups
resource "aws_security_group" "api_sg" {
  name        = "${var.environment}-genomic-api-sg"
  description = "Security group for API ECS tasks"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-genomic-api-sg"
  }
}

resource "aws_security_group" "api_lb_sg" {
  name        = "${var.environment}-genomic-api-lb-sg"
  description = "Security group for API load balancer"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-genomic-api-lb-sg"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/ecs/${var.environment}-genomic-api"
  retention_in_days = 7

  tags = {
    Name = "${var.environment}-genomic-api-logs"
  }
}

