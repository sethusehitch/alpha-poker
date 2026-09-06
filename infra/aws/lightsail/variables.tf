variable "aws_profile" {
  description = "Local AWS CLI profile used by Terraform."
  type        = string
  default     = "default"
}

variable "aws_region" {
  description = "AWS region for the Lightsail instance."
  type        = string
  default     = "us-west-2"
}

variable "availability_zone" {
  description = "Lightsail availability zone."
  type        = string
  default     = "us-west-2a"
}

variable "environment" {
  description = "Environment tag."
  type        = string
  default     = "prototype"
}

variable "instance_name" {
  description = "Unique Lightsail instance name."
  type        = string
  default     = "alpha-poker-prototype"
}

variable "bundle_id" {
  description = "Lightsail plan. medium_3_0 is 2 vCPU, 4 GB RAM, and 80 GB SSD."
  type        = string
  default     = "medium_3_0"
}

variable "blueprint_id" {
  description = "Lightsail operating system blueprint."
  type        = string
  default     = "ubuntu_24_04"
}

variable "admin_cidr" {
  description = "Single trusted IPv4 CIDR allowed to use SSH, normally the deployer's current public IP with /32."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr must be a valid, restricted CIDR and cannot be 0.0.0.0/0."
  }
}

variable "admin_ssh_public_key" {
  description = "Public SSH key installed for the deployment operator. The private key remains local."
  type        = string

  validation {
    condition     = can(regex("^(ssh-ed25519|ssh-rsa) ", var.admin_ssh_public_key))
    error_message = "admin_ssh_public_key must be an OpenSSH public key."
  }
}

variable "snapshot_time_utc" {
  description = "UTC hour for Lightsail automatic snapshots."
  type        = string
  default     = "10:00"

  validation {
    condition     = can(regex("^(?:[01][0-9]|2[0-3]):00$", var.snapshot_time_utc))
    error_message = "snapshot_time_utc must use HH:00 in UTC."
  }
}

variable "domain_name" {
  description = "Primary Route 53 domain for the Alpha Poker site."
  type        = string
  default     = "alphapoker.io"

  validation {
    condition     = can(regex("^[a-z0-9.-]+$", var.domain_name))
    error_message = "domain_name must be a lowercase DNS name."
  }
}
