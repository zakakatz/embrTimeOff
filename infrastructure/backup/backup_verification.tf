# =============================================================================
# Automated Backup Verification System
# =============================================================================
# Purpose: Weekly automated verification of backup integrity and restorability
# =============================================================================

# =============================================================================
# Lambda Function for Backup Verification
# =============================================================================

resource "aws_lambda_function" "backup_verifier" {
  provider      = aws.primary
  function_name = "embi-aurora-backup-verifier"
  runtime       = "python3.11"
  handler       = "backup_verifier.handler"
  role          = aws_iam_role.backup_verifier_role.arn
  timeout       = 900  # 15 minutes - backup verification can take time
  memory_size   = 512

  filename         = data.archive_file.backup_verifier.output_path
  source_code_hash = data.archive_file.backup_verifier.output_base64sha256

  environment {
    variables = {
      CLUSTER_IDENTIFIER = var.cluster_identifier
      SNS_TOPIC_ARN      = aws_sns_topic.backup_alerts.arn
      VERIFICATION_DB_SUBNET_GROUP = aws_db_subnet_group.verification.name
      VERIFICATION_SECURITY_GROUP  = aws_security_group.verification.id
      S3_RESULTS_BUCKET  = aws_s3_bucket.backup_exports.bucket
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.verification.id]
  }

  tags = {
    Name        = "Backup Verifier"
    Environment = var.environment
    Purpose     = "Weekly backup integrity verification"
  }
}

data "archive_file" "backup_verifier" {
  type        = "zip"
  output_path = "${path.module}/lambda/backup_verifier.zip"
  
  source {
    content  = file("${path.module}/lambda/backup_verifier.py")
    filename = "backup_verifier.py"
  }
}

# =============================================================================
# Verification Infrastructure
# =============================================================================

resource "aws_db_subnet_group" "verification" {
  provider   = aws.primary
  name       = "embi-backup-verification"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name        = "Backup Verification Subnet Group"
    Environment = var.environment
  }
}

resource "aws_security_group" "verification" {
  provider    = aws.primary
  name        = "embi-backup-verification-sg"
  description = "Security group for backup verification instances"
  vpc_id      = var.vpc_id

  # Allow PostgreSQL traffic within VPC
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "Backup Verification SG"
    Environment = var.environment
  }
}

# =============================================================================
# IAM Role for Backup Verifier Lambda
# =============================================================================

resource "aws_iam_role" "backup_verifier_role" {
  provider = aws.primary
  name     = "embi-backup-verifier-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "backup_verifier_policy" {
  provider = aws.primary
  name     = "backup-verifier-policy"
  role     = aws_iam_role.backup_verifier_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusterSnapshots",
          "rds:RestoreDBClusterFromSnapshot",
          "rds:DeleteDBCluster",
          "rds:CreateDBInstance",
          "rds:DeleteDBInstance",
          "rds:DescribeDBClusters",
          "rds:DescribeDBInstances",
          "rds:ModifyDBCluster",
          "rds:AddTagsToResource"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.backup_alerts.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.backup_exports.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AssignPrivateIpAddresses",
          "ec2:UnassignPrivateIpAddresses"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.backup_key_primary.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# =============================================================================
# CloudWatch Events for Weekly Verification
# =============================================================================

resource "aws_cloudwatch_event_rule" "weekly_verification" {
  provider            = aws.primary
  name                = "embi-weekly-backup-verification"
  description         = "Trigger weekly backup verification"
  schedule_expression = "cron(0 6 ? * SUN *)"  # Every Sunday at 6 AM UTC

  tags = {
    Name        = "Weekly Backup Verification"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "weekly_verification_target" {
  provider  = aws.primary
  rule      = aws_cloudwatch_event_rule.weekly_verification.name
  target_id = "backup-verifier"
  arn       = aws_lambda_function.backup_verifier.arn

  input = jsonencode({
    verification_type = "full"
    cleanup_after     = true
  })
}

resource "aws_lambda_permission" "allow_eventbridge" {
  provider      = aws.primary
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backup_verifier.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_verification.arn
}

# =============================================================================
# Variables for Verification Infrastructure
# =============================================================================

variable "vpc_id" {
  description = "VPC ID for verification infrastructure"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for verification instances"
  type        = list(string)
}

# =============================================================================
# Outputs
# =============================================================================

output "backup_verifier_function_arn" {
  description = "ARN of the backup verifier Lambda function"
  value       = aws_lambda_function.backup_verifier.arn
}

output "verification_schedule" {
  description = "Schedule for weekly backup verification"
  value       = "Every Sunday at 6:00 AM UTC"
}

