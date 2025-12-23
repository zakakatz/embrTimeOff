# Aurora PostgreSQL Backup Restoration Procedures

## Overview

This document provides step-by-step procedures for restoring Aurora PostgreSQL backups, including point-in-time recovery and cross-region disaster recovery scenarios.

**Recovery Objectives:**
- **RPO (Recovery Point Objective):** 5 minutes
- **RTO (Recovery Time Objective):** 4 hours
- **Backup Retention:** 30 days

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Point-in-Time Recovery (PITR)](#point-in-time-recovery-pitr)
3. [Snapshot Restoration](#snapshot-restoration)
4. [Cross-Region Disaster Recovery](#cross-region-disaster-recovery)
5. [Data Export Recovery](#data-export-recovery)
6. [Validation Checklist](#validation-checklist)
7. [Troubleshooting](#troubleshooting)

---

## Quick Reference

### Estimated Restoration Times

| Scenario | Database Size | Estimated Time |
|----------|---------------|----------------|
| PITR (same region) | < 100 GB | 30-60 minutes |
| PITR (same region) | 100-500 GB | 1-2 hours |
| Snapshot restore | < 100 GB | 30-45 minutes |
| Snapshot restore | 100-500 GB | 1-2 hours |
| Cross-region DR | < 100 GB | 2-3 hours |
| Cross-region DR | 100-500 GB | 3-4 hours |

### Contact Information

- **DBA On-Call:** dba-oncall@company.com
- **DevOps On-Call:** devops-oncall@company.com
- **AWS Support:** Enterprise Support Case

---

## Point-in-Time Recovery (PITR)

### When to Use
- Accidental data deletion
- Data corruption within the last 30 days
- Need to recover to a specific moment in time

### Prerequisites
- AWS CLI configured with appropriate permissions
- Target VPC and subnet group available
- Security groups configured

### Procedure

#### Step 1: Determine Recovery Point

```bash
# List available recovery window
aws rds describe-db-clusters \
  --db-cluster-identifier embi-aurora-cluster \
  --query 'DBClusters[0].{EarliestRestorableTime:EarliestRestorableTime,LatestRestorableTime:LatestRestorableTime}'
```

#### Step 2: Restore to Point in Time

```bash
# Set recovery timestamp (ISO 8601 format)
RECOVERY_TIME="2024-01-15T14:30:00Z"
NEW_CLUSTER="embi-aurora-pitr-$(date +%Y%m%d%H%M)"

# Restore cluster
aws rds restore-db-cluster-to-point-in-time \
  --source-db-cluster-identifier embi-aurora-cluster \
  --db-cluster-identifier $NEW_CLUSTER \
  --restore-to-time $RECOVERY_TIME \
  --db-subnet-group-name embi-db-subnet-group \
  --vpc-security-group-ids sg-xxxxxxxxx \
  --tags Key=Purpose,Value=pitr-recovery Key=OriginalCluster,Value=embi-aurora-cluster
```

#### Step 3: Wait for Cluster Availability

```bash
# Monitor cluster status
aws rds wait db-cluster-available \
  --db-cluster-identifier $NEW_CLUSTER

# Get cluster endpoint
aws rds describe-db-clusters \
  --db-cluster-identifier $NEW_CLUSTER \
  --query 'DBClusters[0].Endpoint'
```

#### Step 4: Create Database Instance

```bash
# Create instance in restored cluster
aws rds create-db-instance \
  --db-instance-identifier ${NEW_CLUSTER}-instance-1 \
  --db-cluster-identifier $NEW_CLUSTER \
  --db-instance-class db.r6g.large \
  --engine aurora-postgresql

# Wait for instance
aws rds wait db-instance-available \
  --db-instance-identifier ${NEW_CLUSTER}-instance-1
```

#### Step 5: Validate Data

```bash
# Connect to restored database and validate
psql -h $NEW_CLUSTER.cluster-xxxxx.us-east-1.rds.amazonaws.com \
  -U embi_admin -d embi \
  -c "SELECT COUNT(*) FROM employees;"
```

#### Step 6: Switch Application Traffic (if applicable)

```python
# Update application configuration
# 1. Update connection string in AWS Secrets Manager or Parameter Store
# 2. Restart application pods/instances
# 3. Verify connectivity
```

---

## Snapshot Restoration

### When to Use
- Disaster recovery from a known good state
- Creating test/staging environments
- Database migration

### Procedure

#### Step 1: List Available Snapshots

```bash
# List automated snapshots
aws rds describe-db-cluster-snapshots \
  --db-cluster-identifier embi-aurora-cluster \
  --snapshot-type automated \
  --query 'DBClusterSnapshots[*].{ID:DBClusterSnapshotIdentifier,Time:SnapshotCreateTime,Status:Status}' \
  --output table

# List manual snapshots
aws rds describe-db-cluster-snapshots \
  --db-cluster-identifier embi-aurora-cluster \
  --snapshot-type manual \
  --query 'DBClusterSnapshots[*].{ID:DBClusterSnapshotIdentifier,Time:SnapshotCreateTime,Status:Status}' \
  --output table
```

#### Step 2: Restore from Snapshot

```bash
SNAPSHOT_ID="rds:embi-aurora-cluster-2024-01-15-03-00"
NEW_CLUSTER="embi-aurora-restored-$(date +%Y%m%d%H%M)"

aws rds restore-db-cluster-from-snapshot \
  --db-cluster-identifier $NEW_CLUSTER \
  --snapshot-identifier $SNAPSHOT_ID \
  --engine aurora-postgresql \
  --db-subnet-group-name embi-db-subnet-group \
  --vpc-security-group-ids sg-xxxxxxxxx \
  --tags Key=Purpose,Value=snapshot-recovery
```

#### Step 3: Create Instance and Validate

Follow Steps 3-6 from PITR procedure above.

---

## Cross-Region Disaster Recovery

### When to Use
- Primary region failure
- Regional disaster event
- Compliance requirement for geographic redundancy

### Estimated Time: 3-4 hours

### Procedure

#### Step 1: Assess Primary Region Status

```bash
# Check primary region health
aws rds describe-db-clusters \
  --region us-east-1 \
  --db-cluster-identifier embi-aurora-cluster
```

#### Step 2: List DR Region Backups

```bash
# List replicated backups in DR region
aws rds describe-db-cluster-automated-backups \
  --region us-west-2 \
  --db-cluster-resource-id cluster-XXXXXXXXX
```

#### Step 3: Restore in DR Region

```bash
# Get the source DB cluster ARN
SOURCE_ARN="arn:aws:rds:us-east-1:123456789012:cluster:embi-aurora-cluster"
NEW_CLUSTER="embi-aurora-dr-$(date +%Y%m%d%H%M)"

# Restore from cross-region backup
aws rds restore-db-cluster-to-point-in-time \
  --region us-west-2 \
  --source-db-cluster-identifier $SOURCE_ARN \
  --db-cluster-identifier $NEW_CLUSTER \
  --use-latest-restorable-time \
  --db-subnet-group-name embi-db-subnet-group-dr \
  --vpc-security-group-ids sg-yyyyyyyyy
```

#### Step 4: Update DNS and Application Configuration

```bash
# Update Route 53 record (if using DNS failover)
aws route53 change-resource-record-sets \
  --hosted-zone-id ZXXXXXXXXXXXXX \
  --change-batch file://dns-failover.json

# Update application configuration
aws ssm put-parameter \
  --name "/embi/production/database/endpoint" \
  --value "$NEW_CLUSTER.cluster-xxxxx.us-west-2.rds.amazonaws.com" \
  --type SecureString \
  --overwrite
```

#### Step 5: Validate DR Environment

```bash
# Run health checks
curl https://api.embi.com/health

# Verify database connectivity
psql -h $NEW_CLUSTER.cluster-xxxxx.us-west-2.rds.amazonaws.com \
  -U embi_admin -d embi \
  -c "SELECT COUNT(*) FROM employees; SELECT NOW();"
```

---

## Data Export Recovery

### When to Use
- Recovering specific data (not full database)
- Long-term archived data beyond 30 days
- Compliance data retrieval

### Procedure

#### Step 1: List Available Exports

```bash
# List exports in S3
aws s3 ls s3://embi-aurora-backup-exports-123456789012/exports/ --recursive
```

#### Step 2: Download and Restore Export

```bash
# Download export
aws s3 cp s3://embi-aurora-backup-exports-123456789012/exports/2024-01-15/ ./restore/ --recursive

# Import using pg_restore
pg_restore -h localhost -U embi_admin -d embi_restore ./restore/export.dump
```

---

## Validation Checklist

After any restoration, verify the following:

### Database Level
- [ ] Cluster status is "available"
- [ ] Instance status is "available"
- [ ] Endpoint is accessible
- [ ] Correct engine version
- [ ] Storage encryption is enabled

### Data Level
- [ ] Row counts match expected values
- [ ] Recent data is present (check timestamps)
- [ ] All tables exist
- [ ] Foreign key constraints are intact
- [ ] Indexes are present and valid

### Application Level
- [ ] Application can connect to database
- [ ] Authentication is working
- [ ] API health checks pass
- [ ] Critical business functions work

### Security Level
- [ ] Security groups are correctly configured
- [ ] KMS encryption is enabled
- [ ] IAM roles are properly attached
- [ ] Audit logging is enabled

---

## Troubleshooting

### Common Issues

#### Issue: Cluster stuck in "creating" state
```bash
# Check for events
aws rds describe-events \
  --source-identifier $CLUSTER_ID \
  --source-type db-cluster \
  --duration 60
```

#### Issue: Cannot connect to restored database
```bash
# Verify security groups
aws ec2 describe-security-groups \
  --group-ids sg-xxxxxxxxx

# Verify subnet routing
aws ec2 describe-route-tables \
  --filters "Name=association.subnet-id,Values=subnet-xxxxxxx"
```

#### Issue: Restoration fails with KMS error
```bash
# Verify KMS key access
aws kms describe-key --key-id alias/embi-aurora-backup

# Check key policy allows RDS
aws kms get-key-policy --key-id alias/embi-aurora-backup --policy-name default
```

### Emergency Contacts

| Role | Contact | Response Time |
|------|---------|---------------|
| DBA On-Call | dba-oncall@company.com | 15 minutes |
| DevOps On-Call | devops-oncall@company.com | 15 minutes |
| AWS TAM | tam@aws.amazon.com | 1 hour |
| Management | engineering-leads@company.com | 30 minutes |

---

## Appendix: Automated Restoration Script

```python
#!/usr/bin/env python3
"""
Automated Aurora restoration script.
Usage: python restore_aurora.py --type pitr --time "2024-01-15T14:30:00Z"
"""

import argparse
import boto3
import time
from datetime import datetime

def restore_pitr(source_cluster: str, target_cluster: str, restore_time: str):
    rds = boto3.client('rds')
    
    print(f"Starting PITR restoration to {target_cluster}...")
    
    rds.restore_db_cluster_to_point_in_time(
        SourceDBClusterIdentifier=source_cluster,
        DBClusterIdentifier=target_cluster,
        RestoreToTime=restore_time,
        DBSubnetGroupName='embi-db-subnet-group',
        Tags=[{'Key': 'Purpose', 'Value': 'pitr-recovery'}]
    )
    
    print("Waiting for cluster to become available...")
    waiter = rds.get_waiter('db_cluster_available')
    waiter.wait(DBClusterIdentifier=target_cluster)
    
    print(f"Cluster {target_cluster} is now available")
    return target_cluster

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=['pitr', 'snapshot'], required=True)
    parser.add_argument('--time', help='Restore time (ISO 8601)')
    parser.add_argument('--snapshot', help='Snapshot identifier')
    args = parser.parse_args()
    
    # Implementation continues...
```

---

*Last Updated: January 2024*
*Document Owner: DevOps Team*
*Review Schedule: Quarterly*

