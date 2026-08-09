variable "aws_region" {
  description = "Bank-approved AWS region."
  type        = string
  default     = "af-south-1"
}

variable "environment" {
  description = "Controlled environment name."
  type        = string
  validation {
    condition     = contains(["dev", "test", "controlled", "production"], var.environment)
    error_message = "environment must be dev, test, controlled or production"
  }
}

variable "vpc_id" {
  description = "Bank-managed VPC with approved inspection and egress."
  type        = string
}

variable "private_subnet_ids" {
  description = "At least three private subnets across availability zones."
  type        = list(string)
  validation {
    condition     = length(var.private_subnet_ids) >= 3
    error_message = "At least three private subnets are required."
  }
}

variable "private_route_table_ids" {
  description = "Private route tables for the S3 gateway endpoint."
  type        = list(string)
  default     = []
}

variable "database_name" {
  type    = string
  default = "wallet_twin"
}

variable "database_master_username" {
  type    = string
  default = "wallet_platform_admin"
}

variable "object_retention_days" {
  type    = number
  default = 2555
}

variable "audit_retention_days" {
  type    = number
  default = 2555
}

variable "organization_trail" {
  description = "Enable only when applied from the AWS Organizations management or delegated administrator account."
  type        = bool
  default     = false
}

variable "eks_admin_role_arns" {
  description = "Federated bank platform roles; never individual IAM users."
  type        = set(string)
}
