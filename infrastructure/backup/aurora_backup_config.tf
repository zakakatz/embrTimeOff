# =============================================================================
# Aurora PostgreSQL Backup Configuration
# =============================================================================
# Purpose: Configure automated backups with point-in-time recovery for Aurora
# PostgreSQL cluster with cross-region replication for disaster recovery.
#
# Requirements:
# - 30-day retention policy for automated backups
# - 5-minute RPO (Recovery Point Objective)
# - 4-hour RTO (Recovery Time Objective)
# - Cross-region backup replication
# =============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  default     = "production"
}

variable "primary_region" {
  description = "Primary AWS region for the Aurora cluster"
  type        = string
  default     = "us-east-1"
}

variable "dr_region" {
  description = "Disaster recovery AWS region for cross-region backup"
  type        = string
  default     = "us-west-2"
}

variable "cluster_identifier" {
  description = "Aurora cluster identifier"
  type        = string
  default     = "embi-aurora-cluster"
}

variable "backup_retention_period" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 30  # 30-day retention policy
}

variable "preferred_backup_window" {
  description = "Daily time range for automated backups (UTC)"
  type        = string
  default     = "03:00-05:00"  # 3-5 AM UTC for minimal impact
}

variable "alert_email" {
  description = "Email address for backup alerts"
  type        = string
  default     = "ops-team@company.com"
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  sensitive   = true
  default     = ""
}

# =============================================================================
# Providers
# =============================================================================

provider "aws" {
  alias  = "primary"
  region = var.primary_region
}

provider "aws" {
  alias  = "dr"
  region = var.dr_region
}

# =============================================================================
# KMS Keys for Backup Encryption
# =============================================================================

# Primary region KMS key for backup encryption
resource "aws_kms_key" "backup_key_primary" {
  provider    = aws.primary
  description = "KMS key for Aurora backup encryption in primary region"
  
  enable_key_rotation = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow RDS to use key"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "embi-aurora-backup-key-${var.primary_region}"
    Environment = var.environment
    Purpose     = "Aurora backup encryption"
  }
}

resource "aws_kms_alias" "backup_key_primary_alias" {
  provider      = aws.primary
  name          = "alias/embi-aurora-backup-${var.primary_region}"
  target_key_id = aws_kms_key.backup_key_primary.key_id
}

# DR region KMS key for cross-region backup encryption
resource "aws_kms_key" "backup_key_dr" {
  provider    = aws.dr
  description = "KMS key for Aurora backup encryption in DR region"
  
  enable_key_rotation = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow RDS to use key"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "embi-aurora-backup-key-${var.dr_region}"
    Environment = var.environment
    Purpose     = "Aurora backup encryption DR"
  }
}

resource "aws_kms_alias" "backup_key_dr_alias" {
  provider      = aws.dr
  name          = "alias/embi-aurora-backup-${var.dr_region}"
  target_key_id = aws_kms_key.backup_key_dr.key_id
}

# =============================================================================
# Aurora Cluster Configuration with Enhanced Backup Settings
# =============================================================================

# Note: This assumes the Aurora cluster already exists. 
# These settings show the backup-specific configuration that should be applied.

resource "aws_rds_cluster" "aurora_cluster" {
  provider                  = aws.primary
  cluster_identifier        = var.cluster_identifier
  engine                    = "aurora-postgresql"
  engine_version            = "15.4"
  database_name             = "embi"
  master_username           = "embi_admin"
  manage_master_user_password = true
  
  # Backup Configuration
  backup_retention_period      = var.backup_retention_period  # 30 days
  preferred_backup_window      = var.preferred_backup_window   # 03:00-05:00 UTC
  copy_tags_to_snapshot        = true
  deletion_protection          = true
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${var.cluster_identifier}-final-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  # Encryption
  storage_encrypted = true
  kms_key_id        = aws_kms_key.backup_key_primary.arn
  
  # Enhanced monitoring for backup operations
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  
  # Point-in-Time Recovery enabled automatically with backup retention
  # Aurora supports continuous backup with PITR within the retention period
  
  # Backtrack for fast recovery (Aurora-specific feature)
  backtrack_window = 259200  # 72 hours in seconds
  
  tags = {
    Name        = var.cluster_identifier
    Environment = var.environment
    BackupRPO   = "5-minutes"
    BackupRTO   = "4-hours"
    Compliance  = "SOC2"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# =============================================================================
# Cross-Region Automated Backup Replication
# =============================================================================

# Enable cross-region automated backup replication for DR
resource "aws_db_instance_automated_backups_replication" "cross_region_backup" {
  provider           = aws.dr
  source_db_instance_arn = aws_rds_cluster.aurora_cluster.arn
  kms_key_id         = aws_kms_key.backup_key_dr.arn
  retention_period   = var.backup_retention_period

  depends_on = [
    aws_rds_cluster.aurora_cluster
  ]
}

# =============================================================================
# S3 Bucket for Manual Exports and Long-term Retention
# =============================================================================

resource "aws_s3_bucket" "backup_exports" {
  provider = aws.primary
  bucket   = "embi-aurora-backup-exports-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "Aurora Backup Exports"
    Environment = var.environment
    Purpose     = "Long-term backup storage"
  }
}

resource "aws_s3_bucket_versioning" "backup_exports_versioning" {
  provider = aws.primary
  bucket   = aws_s3_bucket.backup_exports.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup_exports_encryption" {
  provider = aws.primary
  bucket   = aws_s3_bucket.backup_exports.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.backup_key_primary.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# Lifecycle policy for backup cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "backup_lifecycle" {
  provider = aws.primary
  bucket   = aws_s3_bucket.backup_exports.id

  rule {
    id     = "backup-lifecycle"
    status = "Enabled"

    # Move to Intelligent-Tiering after 30 days
    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }

    # Move to Glacier after 90 days
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Move to Deep Archive after 365 days
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    # Delete after 7 years (2555 days) for compliance
    expiration {
      days = 2555
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# Block public access to backup bucket
resource "aws_s3_bucket_public_access_block" "backup_exports_public_access" {
  provider = aws.primary
  bucket   = aws_s3_bucket.backup_exports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {
  provider = aws.primary
}

data "aws_region" "current" {
  provider = aws.primary
}

# =============================================================================
# Outputs
# =============================================================================

output "aurora_cluster_arn" {
  description = "ARN of the Aurora cluster"
  value       = aws_rds_cluster.aurora_cluster.arn
}

output "backup_retention_days" {
  description = "Backup retention period in days"
  value       = var.backup_retention_period
}

output "backup_window" {
  description = "Preferred backup window"
  value       = var.preferred_backup_window
}

output "backup_kms_key_primary" {
  description = "KMS key ARN for primary region backups"
  value       = aws_kms_key.backup_key_primary.arn
}

output "backup_kms_key_dr" {
  description = "KMS key ARN for DR region backups"
  value       = aws_kms_key.backup_key_dr.arn
}

output "backup_exports_bucket" {
  description = "S3 bucket for backup exports"
  value       = aws_s3_bucket.backup_exports.bucket
}

output "dr_region" {
  description = "Disaster recovery region"
  value       = var.dr_region
}

output "recovery_objectives" {
  description = "Recovery objectives"
  value = {
    rpo_minutes = 5   # Recovery Point Objective
    rto_hours   = 4   # Recovery Time Objective
  }
}

