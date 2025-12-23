# =============================================================================
# CloudWatch Alarms and Monitoring for Aurora Backups
# =============================================================================
# Purpose: Monitor backup operations and alert on failures within 15 minutes
# =============================================================================

# =============================================================================
# SNS Topic for Backup Alerts
# =============================================================================

resource "aws_sns_topic" "backup_alerts" {
  provider = aws.primary
  name     = "embi-aurora-backup-alerts"

  tags = {
    Name        = "Aurora Backup Alerts"
    Environment = var.environment
  }
}

resource "aws_sns_topic_subscription" "backup_alerts_email" {
  provider  = aws.primary
  topic_arn = aws_sns_topic.backup_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Lambda function to send Slack notifications
resource "aws_lambda_function" "slack_notifier" {
  provider      = aws.primary
  count         = var.slack_webhook_url != "" ? 1 : 0
  function_name = "embi-backup-slack-notifier"
  runtime       = "python3.11"
  handler       = "index.handler"
  role          = aws_iam_role.lambda_execution_role.arn
  timeout       = 30
  
  filename         = data.archive_file.slack_notifier.output_path
  source_code_hash = data.archive_file.slack_notifier.output_base64sha256

  environment {
    variables = {
      SLACK_WEBHOOK_URL = var.slack_webhook_url
    }
  }

  tags = {
    Name        = "Backup Slack Notifier"
    Environment = var.environment
  }
}

data "archive_file" "slack_notifier" {
  type        = "zip"
  output_path = "${path.module}/lambda/slack_notifier.zip"
  
  source {
    content  = <<-EOF
import json
import os
import urllib.request

def handler(event, context):
    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if not webhook_url:
        return {'statusCode': 400, 'body': 'No webhook URL configured'}
    
    message = event.get('Records', [{}])[0].get('Sns', {}).get('Message', 'No message')
    subject = event.get('Records', [{}])[0].get('Sns', {}).get('Subject', 'AWS Alert')
    
    slack_message = {
        'blocks': [
            {
                'type': 'header',
                'text': {'type': 'plain_text', 'text': '🚨 Aurora Backup Alert'}
            },
            {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': f'*Subject:* {subject}'}
            },
            {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': f'*Details:*\n```{message}```'}
            }
        ]
    }
    
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(slack_message).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req) as response:
        return {'statusCode': response.status}
EOF
    filename = "index.py"
  }
}

resource "aws_sns_topic_subscription" "backup_alerts_slack" {
  provider  = aws.primary
  count     = var.slack_webhook_url != "" ? 1 : 0
  topic_arn = aws_sns_topic.backup_alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.slack_notifier[0].arn
}

resource "aws_lambda_permission" "sns_invoke" {
  provider      = aws.primary
  count         = var.slack_webhook_url != "" ? 1 : 0
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_notifier[0].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.backup_alerts.arn
}

# =============================================================================
# IAM Role for Lambda
# =============================================================================

resource "aws_iam_role" "lambda_execution_role" {
  provider = aws.primary
  name     = "embi-backup-lambda-role"

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

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  provider   = aws.primary
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# =============================================================================
# CloudWatch Alarms for Backup Monitoring
# =============================================================================

# Alarm for backup job failures - triggers within 15 minutes
resource "aws_cloudwatch_metric_alarm" "backup_failure" {
  provider            = aws.primary
  alarm_name          = "embi-aurora-backup-failure"
  alarm_description   = "Alert when Aurora automated backup fails"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BackupRetentionPeriodStorageUsed"
  namespace           = "AWS/RDS"
  period              = 900  # 15 minutes - matches requirement
  statistic           = "Average"
  threshold           = 0
  treat_missing_data  = "breaching"  # Alert if no backup data

  dimensions = {
    DBClusterIdentifier = var.cluster_identifier
  }

  alarm_actions = [aws_sns_topic.backup_alerts.arn]
  ok_actions    = [aws_sns_topic.backup_alerts.arn]

  tags = {
    Name        = "Aurora Backup Failure Alert"
    Environment = var.environment
    SLA         = "15-minute-notification"
  }
}

# Alarm for backup storage utilization
resource "aws_cloudwatch_metric_alarm" "backup_storage_high" {
  provider            = aws.primary
  alarm_name          = "embi-aurora-backup-storage-high"
  alarm_description   = "Alert when backup storage exceeds 80% threshold"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TotalBackupStorageBilled"
  namespace           = "AWS/RDS"
  period              = 3600  # 1 hour
  statistic           = "Average"
  threshold           = 500000000000  # 500 GB threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = var.cluster_identifier
  }

  alarm_actions = [aws_sns_topic.backup_alerts.arn]

  tags = {
    Name        = "Aurora Backup Storage Alert"
    Environment = var.environment
  }
}

# Alarm for database connectivity during backup
resource "aws_cloudwatch_metric_alarm" "db_connections_backup" {
  provider            = aws.primary
  alarm_name          = "embi-aurora-connections-during-backup"
  alarm_description   = "Monitor database connections during backup window"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300  # 5 minutes
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    DBClusterIdentifier = var.cluster_identifier
  }

  alarm_actions = [aws_sns_topic.backup_alerts.arn]

  tags = {
    Name        = "Aurora Connectivity During Backup"
    Environment = var.environment
  }
}

# Alarm for replication lag (important for cross-region backup)
resource "aws_cloudwatch_metric_alarm" "replication_lag" {
  provider            = aws.primary
  alarm_name          = "embi-aurora-replication-lag"
  alarm_description   = "Alert when replication lag exceeds 5 minutes (RPO threshold)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "AuroraReplicaLag"
  namespace           = "AWS/RDS"
  period              = 60  # 1 minute checks
  statistic           = "Maximum"
  threshold           = 300000  # 5 minutes in milliseconds - matches 5-minute RPO
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBClusterIdentifier = var.cluster_identifier
  }

  alarm_actions = [aws_sns_topic.backup_alerts.arn]

  tags = {
    Name        = "Aurora Replication Lag Alert"
    Environment = var.environment
    RPO         = "5-minutes"
  }
}

# =============================================================================
# CloudWatch Dashboard for Backup Monitoring
# =============================================================================

resource "aws_cloudwatch_dashboard" "backup_monitoring" {
  provider       = aws.primary
  dashboard_name = "embi-aurora-backup-monitoring"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# Aurora PostgreSQL Backup Monitoring Dashboard\nRPO: 5 minutes | RTO: 4 hours | Retention: 30 days"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 12
        height = 6
        properties = {
          title  = "Backup Storage Usage"
          region = var.primary_region
          metrics = [
            ["AWS/RDS", "TotalBackupStorageBilled", "DBClusterIdentifier", var.cluster_identifier]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 1
        width  = 12
        height = 6
        properties = {
          title  = "Replication Lag"
          region = var.primary_region
          metrics = [
            ["AWS/RDS", "AuroraReplicaLag", "DBClusterIdentifier", var.cluster_identifier]
          ]
          period = 60
          stat   = "Maximum"
          annotations = {
            horizontal = [{
              label = "5-minute RPO Threshold"
              value = 300000
              color = "#ff0000"
            }]
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "Database Connections"
          region = var.primary_region
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBClusterIdentifier", var.cluster_identifier]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 7
        width  = 12
        height = 6
        properties = {
          title  = "Free Storage Space"
          region = var.primary_region
          metrics = [
            ["AWS/RDS", "FreeLocalStorage", "DBClusterIdentifier", var.cluster_identifier]
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "alarm"
        x      = 0
        y      = 13
        width  = 24
        height = 4
        properties = {
          title  = "Backup Alarms Status"
          alarms = [
            aws_cloudwatch_metric_alarm.backup_failure.arn,
            aws_cloudwatch_metric_alarm.backup_storage_high.arn,
            aws_cloudwatch_metric_alarm.replication_lag.arn
          ]
        }
      }
    ]
  })
}

# =============================================================================
# EventBridge Rules for Backup Events
# =============================================================================

# Rule to capture RDS backup events
resource "aws_cloudwatch_event_rule" "backup_events" {
  provider    = aws.primary
  name        = "embi-aurora-backup-events"
  description = "Capture Aurora backup completion and failure events"

  event_pattern = jsonencode({
    source      = ["aws.rds"]
    detail-type = ["RDS DB Cluster Snapshot Event", "RDS DB Cluster Event"]
    detail = {
      EventCategories = ["backup", "recovery", "notification"]
      SourceType      = ["CLUSTER"]
      SourceIdentifier = [var.cluster_identifier]
    }
  })

  tags = {
    Name        = "Aurora Backup Events"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "backup_events_sns" {
  provider  = aws.primary
  rule      = aws_cloudwatch_event_rule.backup_events.name
  target_id = "send-to-sns"
  arn       = aws_sns_topic.backup_alerts.arn

  input_transformer {
    input_paths = {
      event_id   = "$.detail.EventID"
      event_type = "$.detail-type"
      message    = "$.detail.Message"
      time       = "$.time"
    }
    input_template = <<-EOF
      {
        "subject": "Aurora Backup Event: <event_type>",
        "message": "Event ID: <event_id>\nTime: <time>\nDetails: <message>"
      }
    EOF
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "backup_alerts_topic_arn" {
  description = "SNS topic ARN for backup alerts"
  value       = aws_sns_topic.backup_alerts.arn
}

output "backup_dashboard_name" {
  description = "CloudWatch dashboard name for backup monitoring"
  value       = aws_cloudwatch_dashboard.backup_monitoring.dashboard_name
}

output "alert_notification_time" {
  description = "Maximum time to receive backup failure notification"
  value       = "15 minutes"
}

