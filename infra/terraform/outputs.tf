output "eks_cluster_name" { value = module.eks.cluster_name }
output "immutable_bucket_arn" { value = aws_s3_bucket.immutable.arn }
output "msk_bootstrap_brokers_iam" {
  value     = aws_msk_cluster.events.bootstrap_brokers_sasl_iam
  sensitive = true
}

output "rds_cluster_endpoint" {
  value     = aws_rds_cluster.operational.endpoint
  sensitive = true
}
output "platform_kms_key_arn" { value = aws_kms_key.platform.arn }
output "audit_bucket_arn" { value = aws_s3_bucket.audit.arn }
output "cloudtrail_arn" { value = aws_cloudtrail.platform.arn }
output "genai_secret_arns" { value = { for provider, secret in aws_secretsmanager_secret.genai_provider : provider => secret.arn } }
output "manifest_signing_key_arn" { value = aws_kms_key.manifest_signing.arn }
