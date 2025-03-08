#!/usr/bin/env python3
"""
Monitoring module for Kubernetes clusters.
Sets up Prometheus and Grafana for monitoring cluster metrics.
"""

import os
import subprocess
import logging
import yaml
from typing import Dict, Any, Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("k8s-monitoring")


class ClusterMonitoring:
    """Sets up and manages monitoring for Kubernetes clusters."""
    
    def __init__(self, kubeconfig: str):
        """
        Initialize the monitoring manager.
        
        Args:
            kubeconfig: Path to kubeconfig file
        """
        self.kubeconfig = kubeconfig
        self.deployments_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "deployments"
        )
    
    def setup_prometheus(self, namespace: str = "monitoring") -> bool:
        """
        Set up Prometheus monitoring.
        
        Args:
            namespace: Kubernetes namespace for Prometheus
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Setting up Prometheus in namespace {namespace}")
        
        try:
            # Create namespace if it doesn't exist
            self._create_namespace(namespace)
            
            # Add Prometheus Helm repository
            subprocess.run(
                ["helm", "repo", "add", "prometheus-community", 
                 "https://prometheus-community.github.io/helm-charts"],
                check=True
            )
            
            subprocess.run(["helm", "repo", "update"], check=True)
            
            # Deploy Prometheus using Helm
            values_file = os.path.join(self.deployments_dir, "prometheus", "values.yaml")
            subprocess.run(
                ["helm", "upgrade", "--install", "prometheus", 
                 "prometheus-community/prometheus",
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}",
                 "-f", values_file],
                check=True
            )
            
            logger.info("Prometheus deployed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up Prometheus: {str(e)}")
            return False
    
    def setup_grafana(self, namespace: str = "monitoring") -> bool:
        """
        Set up Grafana for visualization.
        
        Args:
            namespace: Kubernetes namespace for Grafana
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Setting up Grafana in namespace {namespace}")
        
        try:
            # Create namespace if it doesn't exist
            self._create_namespace(namespace)
            
            # Add Grafana Helm repository
            subprocess.run(
                ["helm", "repo", "add", "grafana", "https://grafana.github.io/helm-charts"],
                check=True
            )
            
            subprocess.run(["helm", "repo", "update"], check=True)
            
            # Deploy Grafana using Helm
            values_file = os.path.join(self.deployments_dir, "grafana", "values.yaml")
            subprocess.run(
                ["helm", "upgrade", "--install", "grafana", 
                 "grafana/grafana",
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}",
                 "-f", values_file,
                 "--set", "service.type=LoadBalancer"],  # For easier access in demo
                check=True
            )
            
            # Configure Prometheus as a data source
            self._configure_grafana_datasource(namespace)
            
            # Import dashboards
            self._import_grafana_dashboards(namespace)
            
            logger.info("Grafana deployed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up Grafana: {str(e)}")
            return False
    
    def _create_namespace(self, namespace: str) -> None:
        """Create Kubernetes namespace if it doesn't exist."""
        try:
            # Check if namespace exists
            result = subprocess.run(
                ["kubectl", "get", "namespace", namespace, 
                 f"--kubeconfig={self.kubeconfig}"],
                capture_output=True,
                check=False
            )
            
            if result.returncode != 0:
                # Create namespace
                subprocess.run(
                    ["kubectl", "create", "namespace", namespace, 
                     f"--kubeconfig={self.kubeconfig}"],
                    check=True
                )
                logger.info(f"Created namespace: {namespace}")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error working with namespace {namespace}: {str(e)}")
            raise
    
    def _configure_grafana_datasource(self, namespace: str) -> None:
        """Configure Prometheus as a data source in Grafana."""
        datasource = {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "Prometheus",
                    "type": "prometheus",
                    "access": "proxy",
                    "url": f"http://prometheus-server.{namespace}.svc.cluster.local",
                    "isDefault": True,
                    "editable": False
                }
            ]
        }
        
        # Write datasource config to file
        datasource_file = os.path.join(self.deployments_dir, "grafana", "datasource.yaml")
        os.makedirs(os.path.dirname(datasource_file), exist_ok=True)
        
        with open(datasource_file, 'w') as f:
            yaml.dump(datasource, f)
        
        # Create ConfigMap for datasource
        subprocess.run(
            ["kubectl", "create", "configmap", "grafana-datasource",
             "--from-file=datasource.yaml=" + datasource_file,
             "--namespace", namespace,
             f"--kubeconfig={self.kubeconfig}"],
            check=True
        )
        
        logger.info("Configured Grafana datasource")
    
    def _import_grafana_dashboards(self, namespace: str) -> None:
        """Import default dashboards into Grafana."""
        # This would typically import JSON dashboard definitions
        # For simplicity, we'll just log this step
        logger.info("Importing Grafana dashboards")
    
    def get_monitoring_urls(self, namespace: str = "monitoring") -> Dict[str, str]:
        """
        Get URLs for monitoring services.
        
        Args:
            namespace: Kubernetes namespace with monitoring services
            
        Returns:
            Dict: URLs for Prometheus and Grafana
        """
        urls = {}
        
        try:
            # Get Prometheus URL
            result = subprocess.run(
                ["kubectl", "get", "svc", "prometheus-server", 
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}",
                 "-o", "jsonpath='{.status.loadBalancer.ingress[0].ip}'"],
                capture_output=True,
                text=True,
                check=True
            )
            
            prometheus_ip = result.stdout.strip("'")
            if prometheus_ip:
                urls["prometheus"] = f"http://{prometheus_ip}:9090"
            
            # Get Grafana URL
            result = subprocess.run(
                ["kubectl", "get", "svc", "grafana", 
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}",
                 "-o", "jsonpath='{.status.loadBalancer.ingress[0].ip}'"],
                capture_output=True,
                text=True,
                check=True
            )
            
            grafana_ip = result.stdout.strip("'")
            if grafana_ip:
                urls["grafana"] = f"http://{grafana_ip}:3000"
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get monitoring URLs: {str(e)}")
        
        return urls
    
    def setup_alerts(self, namespace: str = "monitoring") -> bool:
        """
        Set up alerting rules in Prometheus.
        
        Args:
            namespace: Kubernetes namespace with Prometheus
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Setting up alerting rules in namespace {namespace}")
        
        try:
            # Define basic alerting rules
            alerts = {
                "groups": [
                    {
                        "name": "kubernetes-alerts",
                        "rules": [
                            {
                                "alert": "HighCPUUsage",
                                "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode='idle'}[5m])) * 100) > 80",
                                "for": "5m",
                                "labels": {
                                    "severity": "warning"
                                },
                                "annotations": {
                                    "summary": "High CPU usage detected",
                                    "description": "CPU usage is above 80% for 5 minutes on {{ $labels.instance }}"
                                }
                            },
                            {
                                "alert": "HighMemoryUsage",
                                "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 80",
                                "for": "5m",
                                "labels": {
                                    "severity": "warning"
                                },
                                "annotations": {
                                    "summary": "High memory usage detected",
                                    "description": "Memory usage is above 80% for 5 minutes on {{ $labels.instance }}"
                                }
                            },
                            {
                                "alert": "KubernetesPodCrashLooping",
                                "expr": "increase(kube_pod_container_status_restarts_total[1h]) > 5",
                                "for": "10m",
                                "labels": {
                                    "severity": "warning"
                                },
                                "annotations": {
                                    "summary": "Pod is crash looping",
                                    "description": "Pod {{ $labels.pod }} in namespace {{ $labels.namespace }} is crash looping"
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Write alerts to file
            alerts_file = os.path.join(self.deployments_dir, "prometheus", "alerts.yaml")
            os.makedirs(os.path.dirname(alerts_file), exist_ok=True)
            
            with open(alerts_file, 'w') as f:
                yaml.dump(alerts, f)
            
            # Create ConfigMap for alerts
            subprocess.run(
                ["kubectl", "create", "configmap", "prometheus-alerts",
                 "--from-file=alerts.yaml=" + alerts_file,
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}",
                 "--dry-run=client", "-o", "yaml"],
                check=True,
                stdout=subprocess.PIPE
            ).stdout
            
            # Apply ConfigMap
            subprocess.run(
                ["kubectl", "apply", "-f", "-", 
                 "--namespace", namespace, 
                 f"--kubeconfig={self.kubeconfig}"],
                input=subprocess.run(
                    ["kubectl", "create", "configmap", "prometheus-alerts",
                     "--from-file=alerts.yaml=" + alerts_file,
                     "--namespace", namespace,
                     f"--kubeconfig={self.kubeconfig}",
                     "--dry-run=client", "-o", "yaml"],
                    check=True,
                    stdout=subprocess.PIPE
                ).stdout,
                check=True
            )
            
            # Update Prometheus with the new alerts
            # This is a simplified example - in production, you'd use a more robust approach
            subprocess.run(
                ["kubectl", "rollout", "restart", "deployment", "prometheus-server",
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            logger.info("Alerting rules set up successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up alerting rules: {str(e)}")
            return False
            
    def setup_autoscaling(self, namespace: str = "kube-system") -> bool:
        """
        Set up cluster autoscaling.
        
        Args:
            namespace: Kubernetes namespace for the metrics server
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Setting up cluster autoscaling")
        
        try:
            # Deploy metrics server if not already deployed
            result = subprocess.run(
                ["kubectl", "get", "deployment", "metrics-server", 
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}"],
                capture_output=True,
                check=False
            )
            
            if result.returncode != 0:
                # Apply metrics server
                subprocess.run(
                    ["kubectl", "apply", "-f", 
                     "https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
                     f"--kubeconfig={self.kubeconfig}"],
                    check=True
                )
                logger.info("Metrics Server deployed")
            
            # Create a sample Horizontal Pod Autoscaler
            hpa_yaml = """
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sample-hpa
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sample-deployment
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
"""
            
            # Write HPA to file
            hpa_file = os.path.join(self.deployments_dir, "autoscaling", "sample-hpa.yaml")
            os.makedirs(os.path.dirname(hpa_file), exist_ok=True)
            
            with open(hpa_file, 'w') as f:
                f.write(hpa_yaml)
            
            logger.info("Sample HPA configuration created at: %s", hpa_file)
            logger.info("Autoscaling setup completed")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up autoscaling: {str(e)}")
            return False


if __name__ == "__main__":
    # This can be used as a standalone script or imported as a module
    import argparse
    
    parser = argparse.ArgumentParser(description="Kubernetes Cluster Monitoring")
    parser.add_argument("--kubeconfig", required=True, help="Path to kubeconfig file")
    parser.add_argument("--namespace", default="monitoring", help="Namespace for monitoring tools")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up monitoring tools")
    
    # Get URLs command
    urls_parser = subparsers.add_parser("urls", help="Get monitoring tool URLs")
    
    args = parser.parse_args()
    
    monitoring = ClusterMonitoring(args.kubeconfig)
    
    if args.command == "setup":
        # Set up monitoring stack
        monitoring.setup_prometheus(args.namespace)
        monitoring.setup_grafana(args.namespace)
        monitoring.setup_alerts(args.namespace)
        monitoring.setup_autoscaling()
    elif args.command == "urls":
        # Get and display URLs
        urls = monitoring.get_monitoring_urls(args.namespace)
        for service, url in urls.items():
            print(f"{service}: {url}")
    else:
        parser.print_help()
