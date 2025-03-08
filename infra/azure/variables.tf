# infra/azure/variables.tf

variable "location" {
  description = "Azure region to deploy resources"
  type        = string
  default     = "eastus"
}

variable "cluster_name" {
  description = "Name of the AKS cluster"
  type        = string
  default     = "k8s-cluster-manager-demo"
}

variable "kubernetes_version" {
  description = "Kubernetes version to use for the AKS cluster"
  type        = string
  default     = "1.24"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "worker_instance_type" {
  description = "VM size for worker nodes"
  type        = string
  default     = "Standard_D2_v2"
}

variable "worker_min_count" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 2
}

variable "worker_max_count" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 5
}

