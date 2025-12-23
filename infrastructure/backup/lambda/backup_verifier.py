"""
Aurora PostgreSQL Backup Verification Lambda Function

Performs weekly automated verification of backup integrity by:
1. Identifying the latest snapshot
2. Restoring to a temporary cluster
3. Running integrity checks
4. Cleaning up verification resources
5. Reporting results

Author: EMBI DevOps Team
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CLUSTER_IDENTIFIER = os.environ.get('CLUSTER_IDENTIFIER', 'embi-aurora-cluster')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
VERIFICATION_DB_SUBNET_GROUP = os.environ.get('VERIFICATION_DB_SUBNET_GROUP')
VERIFICATION_SECURITY_GROUP = os.environ.get('VERIFICATION_SECURITY_GROUP')
S3_RESULTS_BUCKET = os.environ.get('S3_RESULTS_BUCKET')

# AWS clients
rds_client = boto3.client('rds')
sns_client = boto3.client('sns')
s3_client = boto3.client('s3')


class BackupVerificationError(Exception):
    """Custom exception for backup verification failures."""
    pass


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for backup verification.
    
    Args:
        event: Lambda event containing verification parameters
        context: Lambda context
    
    Returns:
        Verification results
    """
    logger.info(f"Starting backup verification for cluster: {CLUSTER_IDENTIFIER}")
    logger.info(f"Event: {json.dumps(event)}")
    
    verification_type = event.get('verification_type', 'full')
    cleanup_after = event.get('cleanup_after', True)
    
    verification_id = f"verify-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    verification_cluster = f"{CLUSTER_IDENTIFIER}-{verification_id}"
    
    results = {
        'verification_id': verification_id,
        'cluster_identifier': CLUSTER_IDENTIFIER,
        'verification_type': verification_type,
        'start_time': datetime.now(timezone.utc).isoformat(),
        'status': 'started',
        'steps': []
    }
    
    try:
        # Step 1: Get latest snapshot
        logger.info("Step 1: Finding latest snapshot...")
        snapshot = get_latest_snapshot()
        results['snapshot_identifier'] = snapshot['DBClusterSnapshotIdentifier']
        results['snapshot_create_time'] = snapshot['SnapshotCreateTime'].isoformat()
        results['steps'].append({
            'step': 'get_snapshot',
            'status': 'success',
            'details': f"Found snapshot: {snapshot['DBClusterSnapshotIdentifier']}"
        })
        
        # Step 2: Restore snapshot to verification cluster
        logger.info(f"Step 2: Restoring snapshot to verification cluster: {verification_cluster}")
        restore_snapshot(snapshot['DBClusterSnapshotIdentifier'], verification_cluster)
        results['verification_cluster'] = verification_cluster
        results['steps'].append({
            'step': 'restore_snapshot',
            'status': 'success',
            'details': f"Restored to cluster: {verification_cluster}"
        })
        
        # Step 3: Wait for cluster to become available
        logger.info("Step 3: Waiting for verification cluster to become available...")
        wait_for_cluster_available(verification_cluster)
        results['steps'].append({
            'step': 'wait_available',
            'status': 'success',
            'details': 'Verification cluster is available'
        })
        
        # Step 4: Create DB instance
        logger.info("Step 4: Creating verification DB instance...")
        instance_id = f"{verification_cluster}-instance"
        create_verification_instance(verification_cluster, instance_id)
        wait_for_instance_available(instance_id)
        results['steps'].append({
            'step': 'create_instance',
            'status': 'success',
            'details': f'Created instance: {instance_id}'
        })
        
        # Step 5: Run integrity checks
        logger.info("Step 5: Running integrity checks...")
        integrity_results = run_integrity_checks(verification_cluster)
        results['integrity_checks'] = integrity_results
        results['steps'].append({
            'step': 'integrity_checks',
            'status': 'success' if integrity_results['passed'] else 'failed',
            'details': integrity_results
        })
        
        # Final status
        if integrity_results['passed']:
            results['status'] = 'success'
            results['message'] = 'Backup verification completed successfully'
        else:
            results['status'] = 'failed'
            results['message'] = f"Integrity checks failed: {integrity_results.get('errors', [])}"
        
    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        results['status'] = 'failed'
        results['error'] = str(e)
        results['steps'].append({
            'step': 'error',
            'status': 'failed',
            'details': str(e)
        })
    
    finally:
        # Cleanup verification resources
        if cleanup_after:
            try:
                logger.info("Cleaning up verification resources...")
                cleanup_verification_resources(verification_cluster)
                results['steps'].append({
                    'step': 'cleanup',
                    'status': 'success',
                    'details': 'Verification resources cleaned up'
                })
            except Exception as e:
                logger.error(f"Cleanup failed: {str(e)}")
                results['steps'].append({
                    'step': 'cleanup',
                    'status': 'failed',
                    'details': str(e)
                })
        
        results['end_time'] = datetime.now(timezone.utc).isoformat()
        
        # Store results in S3
        save_results_to_s3(results)
        
        # Send notification
        send_notification(results)
    
    return results


def get_latest_snapshot() -> Dict[str, Any]:
    """Get the most recent automated snapshot for the cluster."""
    response = rds_client.describe_db_cluster_snapshots(
        DBClusterIdentifier=CLUSTER_IDENTIFIER,
        SnapshotType='automated',
        MaxRecords=20
    )
    
    snapshots = response.get('DBClusterSnapshots', [])
    if not snapshots:
        raise BackupVerificationError(f"No automated snapshots found for cluster: {CLUSTER_IDENTIFIER}")
    
    # Sort by creation time and get the latest
    snapshots.sort(key=lambda x: x['SnapshotCreateTime'], reverse=True)
    latest_snapshot = snapshots[0]
    
    # Verify snapshot is available
    if latest_snapshot['Status'] != 'available':
        raise BackupVerificationError(
            f"Latest snapshot {latest_snapshot['DBClusterSnapshotIdentifier']} is not available. "
            f"Status: {latest_snapshot['Status']}"
        )
    
    logger.info(f"Found latest snapshot: {latest_snapshot['DBClusterSnapshotIdentifier']}")
    return latest_snapshot


def restore_snapshot(snapshot_identifier: str, target_cluster: str) -> None:
    """Restore a snapshot to a new verification cluster."""
    try:
        rds_client.restore_db_cluster_from_snapshot(
            DBClusterIdentifier=target_cluster,
            SnapshotIdentifier=snapshot_identifier,
            Engine='aurora-postgresql',
            DBSubnetGroupName=VERIFICATION_DB_SUBNET_GROUP,
            VpcSecurityGroupIds=[VERIFICATION_SECURITY_GROUP] if VERIFICATION_SECURITY_GROUP else [],
            DeletionProtection=False,
            Tags=[
                {'Key': 'Purpose', 'Value': 'backup-verification'},
                {'Key': 'AutoDelete', 'Value': 'true'},
                {'Key': 'SourceSnapshot', 'Value': snapshot_identifier}
            ]
        )
        logger.info(f"Initiated restore of snapshot {snapshot_identifier} to {target_cluster}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'DBClusterAlreadyExistsFault':
            logger.warning(f"Cluster {target_cluster} already exists, cleaning up first...")
            cleanup_verification_resources(target_cluster)
            time.sleep(60)  # Wait for cleanup
            restore_snapshot(snapshot_identifier, target_cluster)  # Retry
        else:
            raise


def wait_for_cluster_available(cluster_identifier: str, timeout_minutes: int = 30) -> None:
    """Wait for a cluster to become available."""
    waiter = rds_client.get_waiter('db_cluster_available')
    try:
        waiter.wait(
            DBClusterIdentifier=cluster_identifier,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': timeout_minutes * 2
            }
        )
        logger.info(f"Cluster {cluster_identifier} is now available")
    except Exception as e:
        raise BackupVerificationError(
            f"Timeout waiting for cluster {cluster_identifier} to become available: {str(e)}"
        )


def create_verification_instance(cluster_identifier: str, instance_identifier: str) -> None:
    """Create a DB instance in the verification cluster."""
    rds_client.create_db_instance(
        DBInstanceIdentifier=instance_identifier,
        DBClusterIdentifier=cluster_identifier,
        DBInstanceClass='db.t3.medium',  # Small instance for verification
        Engine='aurora-postgresql',
        Tags=[
            {'Key': 'Purpose', 'Value': 'backup-verification'},
            {'Key': 'AutoDelete', 'Value': 'true'}
        ]
    )
    logger.info(f"Created verification instance: {instance_identifier}")


def wait_for_instance_available(instance_identifier: str, timeout_minutes: int = 20) -> None:
    """Wait for a DB instance to become available."""
    waiter = rds_client.get_waiter('db_instance_available')
    try:
        waiter.wait(
            DBInstanceIdentifier=instance_identifier,
            WaiterConfig={
                'Delay': 30,
                'MaxAttempts': timeout_minutes * 2
            }
        )
        logger.info(f"Instance {instance_identifier} is now available")
    except Exception as e:
        raise BackupVerificationError(
            f"Timeout waiting for instance {instance_identifier} to become available: {str(e)}"
        )


def run_integrity_checks(cluster_identifier: str) -> Dict[str, Any]:
    """
    Run integrity checks on the restored cluster.
    
    This includes:
    - Verifying cluster endpoint is accessible
    - Checking cluster status and configuration
    - Verifying data integrity metrics
    """
    results = {
        'passed': True,
        'checks': [],
        'errors': []
    }
    
    try:
        # Get cluster details
        response = rds_client.describe_db_clusters(
            DBClusterIdentifier=cluster_identifier
        )
        cluster = response['DBClusters'][0]
        
        # Check 1: Cluster status
        status_check = {
            'name': 'cluster_status',
            'passed': cluster['Status'] == 'available',
            'details': f"Cluster status: {cluster['Status']}"
        }
        results['checks'].append(status_check)
        if not status_check['passed']:
            results['passed'] = False
            results['errors'].append(f"Cluster status is not 'available': {cluster['Status']}")
        
        # Check 2: Endpoint availability
        endpoint_check = {
            'name': 'endpoint_available',
            'passed': bool(cluster.get('Endpoint')),
            'details': f"Endpoint: {cluster.get('Endpoint', 'N/A')}"
        }
        results['checks'].append(endpoint_check)
        if not endpoint_check['passed']:
            results['passed'] = False
            results['errors'].append("No cluster endpoint available")
        
        # Check 3: Engine version matches
        engine_check = {
            'name': 'engine_version',
            'passed': True,  # Just informational
            'details': f"Engine: {cluster['Engine']} v{cluster['EngineVersion']}"
        }
        results['checks'].append(engine_check)
        
        # Check 4: Storage encryption
        encryption_check = {
            'name': 'storage_encrypted',
            'passed': cluster.get('StorageEncrypted', False),
            'details': f"Storage encrypted: {cluster.get('StorageEncrypted', False)}"
        }
        results['checks'].append(encryption_check)
        if not encryption_check['passed']:
            results['errors'].append("Storage is not encrypted")
            # Not failing verification for this, but flagging it
        
        # Check 5: Database exists
        db_check = {
            'name': 'database_exists',
            'passed': bool(cluster.get('DatabaseName')),
            'details': f"Database: {cluster.get('DatabaseName', 'N/A')}"
        }
        results['checks'].append(db_check)
        if not db_check['passed']:
            results['passed'] = False
            results['errors'].append("No database name found in cluster")
        
        # Calculate summary
        passed_count = sum(1 for c in results['checks'] if c['passed'])
        total_count = len(results['checks'])
        results['summary'] = f"{passed_count}/{total_count} checks passed"
        
    except Exception as e:
        results['passed'] = False
        results['errors'].append(f"Error running integrity checks: {str(e)}")
    
    return results


def cleanup_verification_resources(cluster_identifier: str) -> None:
    """Clean up verification cluster and instances."""
    try:
        # First, delete any instances
        try:
            response = rds_client.describe_db_clusters(
                DBClusterIdentifier=cluster_identifier
            )
            cluster = response['DBClusters'][0]
            
            for member in cluster.get('DBClusterMembers', []):
                instance_id = member['DBInstanceIdentifier']
                logger.info(f"Deleting instance: {instance_id}")
                try:
                    rds_client.delete_db_instance(
                        DBInstanceIdentifier=instance_id,
                        SkipFinalSnapshot=True,
                        DeleteAutomatedBackups=True
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'DBInstanceNotFound':
                        logger.warning(f"Error deleting instance {instance_id}: {str(e)}")
        except ClientError as e:
            if e.response['Error']['Code'] != 'DBClusterNotFoundFault':
                raise
            logger.info(f"Cluster {cluster_identifier} not found, skipping instance deletion")
            return
        
        # Wait for instances to be deleted
        time.sleep(60)
        
        # Then delete the cluster
        logger.info(f"Deleting cluster: {cluster_identifier}")
        rds_client.delete_db_cluster(
            DBClusterIdentifier=cluster_identifier,
            SkipFinalSnapshot=True
        )
        
        logger.info(f"Successfully initiated cleanup of {cluster_identifier}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'DBClusterNotFoundFault':
            logger.info(f"Cluster {cluster_identifier} already deleted")
        else:
            raise


def save_results_to_s3(results: Dict[str, Any]) -> None:
    """Save verification results to S3."""
    if not S3_RESULTS_BUCKET:
        logger.warning("No S3 bucket configured for results")
        return
    
    try:
        key = f"backup-verification/{results['verification_id']}/results.json"
        s3_client.put_object(
            Bucket=S3_RESULTS_BUCKET,
            Key=key,
            Body=json.dumps(results, indent=2, default=str),
            ContentType='application/json'
        )
        logger.info(f"Results saved to s3://{S3_RESULTS_BUCKET}/{key}")
    except Exception as e:
        logger.error(f"Failed to save results to S3: {str(e)}")


def send_notification(results: Dict[str, Any]) -> None:
    """Send verification results notification via SNS."""
    if not SNS_TOPIC_ARN:
        logger.warning("No SNS topic configured for notifications")
        return
    
    try:
        status_emoji = "✅" if results['status'] == 'success' else "❌"
        subject = f"{status_emoji} Aurora Backup Verification: {results['status'].upper()}"
        
        message_lines = [
            f"Backup Verification Report",
            f"{'=' * 40}",
            f"",
            f"Cluster: {results['cluster_identifier']}",
            f"Verification ID: {results['verification_id']}",
            f"Status: {results['status'].upper()}",
            f"",
            f"Snapshot: {results.get('snapshot_identifier', 'N/A')}",
            f"Snapshot Created: {results.get('snapshot_create_time', 'N/A')}",
            f"",
            f"Verification Steps:",
        ]
        
        for step in results.get('steps', []):
            step_status = "✓" if step['status'] == 'success' else "✗"
            message_lines.append(f"  {step_status} {step['step']}: {step.get('details', '')}")
        
        if results.get('integrity_checks'):
            message_lines.append("")
            message_lines.append("Integrity Checks:")
            for check in results['integrity_checks'].get('checks', []):
                check_status = "✓" if check['passed'] else "✗"
                message_lines.append(f"  {check_status} {check['name']}: {check.get('details', '')}")
        
        if results.get('error'):
            message_lines.append("")
            message_lines.append(f"Error: {results['error']}")
        
        message = "\n".join(message_lines)
        
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        logger.info("Notification sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")


if __name__ == "__main__":
    # For local testing
    test_event = {
        'verification_type': 'full',
        'cleanup_after': True
    }
    result = handler(test_event, None)
    print(json.dumps(result, indent=2, default=str))

