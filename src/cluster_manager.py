#!/usr/bin/env python3
"""
Kubernetes Cluster Manager - A tool for provisioning and managing Kubernetes clusters
across cloud providers.
"""

import os
import sys
import argparse
import subprocess
import json
import yaml
import logging
from typing import Dict, Any, List, Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("k8s-cluster-manager")


class ClusterManager:
    """Manages Kubernetes clusters across different cloud providers."""
    
    def __init__(self, provider: str, cluster_name: str, region: str, config_path: Optional[str] = None):
        """
        Initialize the cluster manager.
        
        Args:
            provider: Cloud provider (aws or azure)
            cluster_name: Name of the Kubernetes cluster
            region: Cloud provider region
            config_path: Path to configuration file (optional)
        """
        self.provider = provider.lower()
        self.cluster_name = cluster_name
        self.region = region
        self.config_path = config_path
        self.tf_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  "infra", self.provider)
        
        if self.provider not in ["aws", "azure"]:
            raise ValueError(f"Unsupported provider: {provider}. Use 'aws' or 'azure'")
        
        # Load configuration if provided
        self.config = {}
        if config_path:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
    
    def create_cluster(self) -> bool:
        """
        Create a new Kubernetes cluster.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Creating {self.provider} cluster: {self.cluster_name} in {self.region}")
        
        # Create terraform.tfvars file with variables
        tfvars_content = f"""
cluster_name = "{self.cluster_name}"
{self.provider}_region = "{self.region}" 
environment = "{self.config.get('environment', 'dev')}"
kubernetes_version = "{self.config.get('kubernetes_version', '1.24')}"
worker_min_count = {self.config.get('worker_min_count', 2)}
worker_max_count = {self.config.get('worker_max_count', 5)}
"""
        
        if self.provider == "aws":
            tfvars_content += f'worker_instance_type = "{self.config.get("worker_instance_type", "t3.medium")}"\n'
        else:  # azure
            tfvars_content += f'worker_instance_type = "{self.config.get("worker_instance_type", "Standard_D2_v2")}"\n'
        
        # Write tfvars file
        with open(os.path.join(self.tf_dir, "terraform.tfvars"), 'w') as f:
            f.write(tfvars_content)
        
        # Run Terraform commands
        try:
            # Initialize Terraform
            subprocess.run(["terraform", "init"], cwd=self.tf_dir, check=True)
            
            # Apply Terraform configuration
            subprocess.run(["terraform", "apply", "-auto-approve"], cwd=self.tf_dir, check=True)
            
            logger.info(f"Successfully created {self.provider} cluster: {self.cluster_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create cluster: {str(e)}")
            return False
    
    def delete_cluster(self) -> bool:
        """
        Delete an existing Kubernetes cluster.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Deleting {self.provider} cluster: {self.cluster_name}")
        
        try:
            # Run Terraform destroy
            subprocess.run(["terraform", "destroy", "-auto-approve"], cwd=self.tf_dir, check=True)
            
            logger.info(f"Successfully deleted {self.provider} cluster: {self.cluster_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete cluster: {str(e)}")
            return False
    
    def get_kubeconfig(self) -> str:
        """
        Get the kubeconfig path for the cluster.
        
        Returns:
            str: Path to kubeconfig file
        """
        kubeconfig_path = os.path.join(self.tf_dir, f"kubeconfig_{self.cluster_name}")
        
        if not os.path.exists(kubeconfig_path):
            logger.warning(f"Kubeconfig not found at {kubeconfig_path}")
        
        return kubeconfig_path
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Get the status of the Kubernetes cluster.
        
        Returns:
            Dict: Cluster status information
        """
        logger.info(f"Getting status for {self.provider} cluster: {self.cluster_name}")
        
        kubeconfig = self.get_kubeconfig()
        if not os.path.exists(kubeconfig):
            return {"status": "unknown", "error": "Kubeconfig not found"}
        
        try:
            # Get nodes
            result = subprocess.run(
                ["kubectl", "get", "nodes", "-o", "json", f"--kubeconfig={kubeconfig}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            nodes = json.loads(result.stdout)
            
            # Get cluster info
            result = subprocess.run(
                ["kubectl", "cluster-info", "dump", f"--kubeconfig={kubeconfig}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Return status info
            return {
                "status": "running",
                "provider": self.provider,
                "cluster_name": self.cluster_name,
                "region": self.region,
                "node_count": len(nodes.get("items", [])),
                "kubernetes_version": self._get_kubernetes_version(kubeconfig)
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get cluster status: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _get_kubernetes_version(self, kubeconfig: str) -> str:
        """Get Kubernetes version from cluster."""
        try:
            result = subprocess.run(
                ["kubectl", "version", "--short", f"--kubeconfig={kubeconfig}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse version from output
            for line in result.stdout.splitlines():
                if "Server Version" in line:
                    return line.split(":")[-1].strip()
            
            return "unknown"
            
        except subprocess.CalledProcessError:
            return "unknown"


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Kubernetes Cluster Manager")
    parser.add_argument("--provider", choices=["aws", "azure"], required=True,
                        help="Cloud provider (aws or azure)")
    parser.add_argument("--cluster-name", required=True, help="Name of the Kubernetes cluster")
    parser.add_argument("--region", required=True, help="Cloud provider region")
    parser.add_argument("--config", help="Path to configuration YAML file")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new Kubernetes cluster")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an existing Kubernetes cluster")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get the status of a Kubernetes cluster")
    
    args = parser.parse_args()
    
    # Create cluster manager
    manager = ClusterManager(
        provider=args.provider,
        cluster_name=args.cluster_name,
        region=args.region,
        config_path=args.config
    )
    
    # Execute command
    if args.command == "create":
        success = manager.create_cluster()
        sys.exit(0 if success else 1)
    elif args.command == "delete":
        success = manager.delete_cluster()
        sys.exit(0 if success else 1)
    elif args.command == "status":
        status = manager.get_cluster_status()
        print(json.dumps(status, indent=2))
        sys.exit(0 if status.get("status") != "error" else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
