data "aws_caller_identity" "current" {}
data "aws_vpc" "selected" { id = var.vpc_id }

locals {
  name = "wallet-twin-${var.environment}"
}

resource "aws_kms_key" "platform" {
  description             = "Envelope encryption for ${local.name}"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = false
}

resource "aws_kms_alias" "platform" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.platform.key_id
}

resource "aws_s3_bucket" "immutable" {
  bucket              = "${local.name}-${data.aws_caller_identity.current.account_id}"
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "immutable" {
  bucket = aws_s3_bucket.immutable.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_object_lock_configuration" "immutable" {
  bucket = aws_s3_bucket.immutable.id
  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.object_retention_days
    }
  }
  depends_on = [aws_s3_bucket_versioning.immutable]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "immutable" {
  bucket = aws_s3_bucket.immutable.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.platform.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "immutable" {
  bucket                  = aws_s3_bucket.immutable.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_db_subnet_group" "platform" {
  name       = local.name
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "database" {
  name        = "${local.name}-database"
  description = "PostgreSQL reachable only from EKS workloads"
  vpc_id      = var.vpc_id
  ingress {
    protocol        = "tcp"
    from_port       = 5432
    to_port         = 5432
    security_groups = [module.eks.node_security_group_id]
  }
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["127.0.0.1/32"]
  }
}

resource "aws_rds_cluster" "operational" {
  cluster_identifier                  = local.name
  engine                              = "aurora-postgresql"
  database_name                       = var.database_name
  master_username                     = var.database_master_username
  manage_master_user_password         = true
  master_user_secret_kms_key_id       = aws_kms_key.platform.arn
  storage_encrypted                   = true
  kms_key_id                          = aws_kms_key.platform.arn
  db_subnet_group_name                = aws_db_subnet_group.platform.name
  vpc_security_group_ids              = [aws_security_group.database.id]
  backup_retention_period             = 35
  preferred_backup_window             = "20:00-22:00"
  deletion_protection                 = true
  skip_final_snapshot                 = false
  final_snapshot_identifier           = "${local.name}-final"
  enabled_cloudwatch_logs_exports     = ["postgresql"]
  iam_database_authentication_enabled = true
  copy_tags_to_snapshot               = true
}

resource "aws_rds_cluster_instance" "operational" {
  count              = var.environment == "production" ? 2 : 1
  identifier         = "${local.name}-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.operational.id
  instance_class     = "db.r7g.large"
  engine             = aws_rds_cluster.operational.engine
}

resource "aws_security_group" "msk" {
  name   = "${local.name}-msk"
  vpc_id = var.vpc_id
  ingress {
    protocol        = "tcp"
    from_port       = 9098
    to_port         = 9098
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${local.name}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.platform.arn
}

resource "aws_msk_cluster" "events" {
  cluster_name           = local.name
  kafka_version          = "3.9.x"
  number_of_broker_nodes = 3
  enhanced_monitoring    = "PER_BROKER"

  broker_node_group_info {
    instance_type   = "kafka.m7g.large"
    client_subnets  = slice(var.private_subnet_ids, 0, 3)
    security_groups = [aws_security_group.msk.id]
    storage_info {
      ebs_storage_info { volume_size = 500 }
    }
  }

  client_authentication {
    sasl {
      iam = true
    }
  }
  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.platform.arn
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }
  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.23.0"

  name                                     = local.name
  kubernetes_version                       = "1.34"
  endpoint_public_access                   = false
  endpoint_private_access                  = true
  enabled_log_types                        = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cloudwatch_log_group_retention_in_days   = 365
  cloudwatch_log_group_kms_key_id          = aws_kms_key.platform.arn
  enable_irsa                              = true
  vpc_id                                   = var.vpc_id
  subnet_ids                               = var.private_subnet_ids
  authentication_mode                      = "API_AND_CONFIG_MAP"
  enable_cluster_creator_admin_permissions = false

  access_entries = {
    for index, arn in var.eks_admin_role_arns : "platform-${index}" => {
      principal_arn = arn
      policy_associations = {
        admin = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
  }

  eks_managed_node_groups = {
    system = {
      instance_types = ["m7g.large"]
      min_size       = 3
      desired_size   = 3
      max_size       = 12
      disk_size      = 100
      labels         = { workload = "wallet-twin" }
    }
  }
}
