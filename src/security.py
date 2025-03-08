#!/usr/bin/env python3
"""
Security module for Kubernetes clusters.
Implements security hardening and scanning for Kubernetes clusters.
"""

import os
import subprocess
import logging
import yaml
import json
from typing import Dict, Any, List, Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("k8s-security")


class ClusterSecurity:
    """Implements security for Kubernetes clusters."""
    
    def __init__(self, kubeconfig: str):
        """
        Initialize the security manager.
        
        Args:
            kubeconfig: Path to kubeconfig file
        """
        self.kubeconfig = kubeconfig
        self.deployments_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "deployments"
        )
    
    def apply_network_policies(self, namespace: str = "default") -> bool:
        """
        Apply default network policies to restrict pod communication.
        
        Args:
            namespace: Kubernetes namespace
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Applying network policies to namespace {namespace}")
        
        try:
            # Default deny all ingress traffic
            default_deny_ingress = """
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}
  policyTypes:
  - Ingress
"""
            
            # Allow internal namespace communication
            allow_namespace_internal = """
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-namespace-internal
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: %s
""" % namespace
            
            # Write policies to files
            policies_dir = os.path.join(self.deployments_dir, "security", "network-policies")
            os.makedirs(policies_dir, exist_ok=True)
            
            with open(os.path.join(policies_dir, "default-deny-ingress.yaml"), 'w') as f:
                f.write(default_deny_ingress)
            
            with open(os.path.join(policies_dir, "allow-namespace-internal.yaml"), 'w') as f:
                f.write(allow_namespace_internal)
            
            # Label the namespace to match our selector
            subprocess.run(
                ["kubectl", "label", "namespace", namespace, f"name={namespace}", "--overwrite",
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            # Apply network policies
            subprocess.run(
                ["kubectl", "apply", "-f", os.path.join(policies_dir, "default-deny-ingress.yaml"),
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            subprocess.run(
                ["kubectl", "apply", "-f", os.path.join(policies_dir, "allow-namespace-internal.yaml"),
                 "--namespace", namespace,
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            logger.info("Network policies applied successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply network policies: {str(e)}")
            return False
    
    def apply_pod_security_policies(self) -> bool:
        """
        Apply Pod Security Standards.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Applying Pod Security Standards")
        
        try:
            # Create a namespace for demonstration
            demo_namespace = "restricted-pods"
            
            # Check if namespace exists
            result = subprocess.run(
                ["kubectl", "get", "namespace", demo_namespace, 
                 f"--kubeconfig={self.kubeconfig}"],
                capture_output=True,
                check=False
            )
            
            if result.returncode != 0:
                # Create namespace
                subprocess.run(
                    ["kubectl", "create", "namespace", demo_namespace, 
                     f"--kubeconfig={self.kubeconfig}"],
                    check=True
                )
            
            # Label the namespace with Pod Security Standards
            subprocess.run(
                ["kubectl", "label", "--overwrite", "namespace", demo_namespace,
                 "pod-security.kubernetes.io/enforce=restricted",
                 "pod-security.kubernetes.io/audit=restricted",
                 "pod-security.kubernetes.io/warn=restricted",
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            logger.info(f"Pod Security Standards applied to namespace {demo_namespace}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply Pod Security Standards: {str(e)}")
            return False
    
    def setup_container_scanning(self, namespace: str = "security") -> bool:
        """
        Set up container image scanning with Trivy.
        
        Args:
            namespace: Kubernetes namespace for Trivy
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Setting up Trivy container scanning in namespace {namespace}")
        
        try:
            # Create namespace if it doesn't exist
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
            
            # Trivy operator deployment
            trivy_operator = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trivy-operator
  namespace: %s
spec:
  replicas: 1
  selector:
    matchLabels:
      app: trivy-operator
  template:
    metadata:
      labels:
        app: trivy-operator
    spec:
      containers:
      - name: trivy-operator
        image: aquasec/trivy-operator:0.1.5
        args:
          - "--target-namespaces=default"
          - "--log-level=info"
        env:
          - name: OPERATOR_NAMESPACE
            valueFrom:
              fieldRef:
                fieldPath: metadata.namespace
          - name: OPERATOR_TARGET_NAMESPACES
            value: default
        resources:
          limits:
            cpu: 1
            memory: 1Gi
          requests:
            cpu: 200m
            memory: 100Mi
""" % namespace
            
            # Write Trivy operator to file
            trivy_dir = os.path.join(self.deployments_dir, "security", "trivy")
            os.makedirs(trivy_dir, exist_ok=True)
            
            with open(os.path.join(trivy_dir, "trivy-operator.yaml"), 'w') as f:
                f.write(trivy_operator)
            
            # Apply Trivy operator
            subprocess.run(
                ["kubectl", "apply", "-f", os.path.join(trivy_dir, "trivy-operator.yaml"),
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            logger.info("Trivy container scanning set up successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up container scanning: {str(e)}")
            return False
    
    def run_kube_bench(self) -> Dict[str, Any]:
        """
        Run CIS Kubernetes Benchmark checks using kube-bench.
        
        Returns:
            Dict: Results of kube-bench scan
        """
        logger.info("Running kube-bench CIS benchmark checks")
        
        try:
            # Deploy kube-bench as a job
            kube_bench_job = """
apiVersion: batch/v1
kind: Job
metadata:
  name: kube-bench
spec:
  template:
    metadata:
      labels:
        app: kube-bench
    spec:
      hostPID: true
      containers:
      - name: kube-bench
        image: aquasec/kube-bench:latest
        command: ["kube-bench", "--json"]
        volumeMounts:
        - name: var-lib-kubelet
          mountPath: /var/lib/kubelet
          readOnly: true
        - name: etc-systemd
          mountPath: /etc/systemd
          readOnly: true
        - name: etc-kubernetes
          mountPath: /etc/kubernetes
          readOnly: true
        securityContext:
          privileged: true
      restartPolicy: Never
      volumes:
      - name: var-lib-kubelet
        hostPath:
          path: /var/lib/kubelet
      - name: etc-systemd
        hostPath:
          path: /etc/systemd
      - name: etc-kubernetes
        hostPath:
          path: /etc/kubernetes
"""
            
            # Write job to file
            kube_bench_dir = os.path.join(self.deployments_dir, "security", "kube-bench")
            os.makedirs(kube_bench_dir, exist_ok=True)
            
            with open(os.path.join(kube_bench_dir, "kube-bench-job.yaml"), 'w') as f:
                f.write(kube_bench_job)
            
            # Apply job
            subprocess.run(
                ["kubectl", "apply", "-f", os.path.join(kube_bench_dir, "kube-bench-job.yaml"),
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            # Wait for job to complete
            logger.info("Waiting for kube-bench job to complete...")
            subprocess.run(
                ["kubectl", "wait", "--for=condition=complete", "job/kube-bench", "--timeout=300s",
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            # Get logs from the job
            result = subprocess.run(
                ["kubectl", "logs", "job/kube-bench", 
                 f"--kubeconfig={self.kubeconfig}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse JSON output
            try:
                benchmark_results = json.loads(result.stdout)
                logger.info("CIS benchmark checks completed")
                return benchmark_results
            except json.JSONDecodeError:
                logger.warning("Failed to parse kube-bench output as JSON")
                return {"error": "Failed to parse output", "raw_output": result.stdout}
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to run kube-bench: {str(e)}")
            return {"error": str(e)}
    
    def apply_rbac_policies(self) -> bool:
        """
        Apply best-practice RBAC policies.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Applying RBAC policies")
        
        try:
            # Create a set of example RBAC policies for a read-only user
            rbac_policies = """
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: readonly-user
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: readonly-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "secrets", "namespaces"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["batch"]
  resources: ["jobs", "cronjobs"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: readonly-binding
subjects:
- kind: ServiceAccount
  name: readonly-user
  namespace: default
roleRef:
  kind: ClusterRole
  name: readonly-role
  apiGroup: rbac.authorization.k8s.io
"""
            
            # Write RBAC policies to file
            rbac_dir = os.path.join(self.deployments_dir, "security", "rbac")
            os.makedirs(rbac_dir, exist_ok=True)
            
            with open(os.path.join(rbac_dir, "readonly-rbac.yaml"), 'w') as f:
                f.write(rbac_policies)
            
            # Apply RBAC policies
            subprocess.run(
                ["kubectl", "apply", "-f", os.path.join(rbac_dir, "readonly-rbac.yaml"),
                 f"--kubeconfig={self.kubeconfig}"],
                check=True
            )
            
            logger.info("RBAC policies applied successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply RBAC policies: {str(e)}")
            return False
    
    def generate_security_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive security report.
        
        Returns:
            Dict: Security report findings
        """
        logger.info("Generating security report")
        
        report = {
            "timestamp": subprocess.run(
                ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip(),
            "cluster_info": {},
            "benchmark_results": {},
            "vulnerabilities": {},
            "recommendations": []
        }
        
        try:
            # Get cluster info
            version_result = subprocess.run(
                ["kubectl", "version", "--short", 
                 f"--kubeconfig={self.kubeconfig}"],
                capture_output=True,
                text=True,
                check=True
            )
            report["cluster_info"]["version"] = version_result.stdout
            
            # Get node count
            nodes_result = subprocess.run(
                ["kubectl", "get", "nodes", "--no-headers", 
                 f"--kubeconfig={self.kubeconfig}"],
                capture_output=True,
                text=True,
                check=True
            )
            report["cluster_info"]["node_count"] = len(nodes_result.stdout.splitlines())
            
            # Run CIS benchmark checks
            report["benchmark_results"] = self.run_kube_bench()
            
            # Add recommendations based on findings
            report["recommendations"] = [
                "Enable Pod Security Standards for all namespaces",
                "Implement network policies to restrict pod-to-pod communication",
                "Regularly scan container images for vulnerabilities",
                "Implement least-privilege RBAC policies",
                "Enable audit logging for all API server requests"
            ]
            
            logger.info("Security report generated successfully")
            return report
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate security report: {str(e)}")
            return {"error": str(e)}


if __name__ == "__main__":
    # This can be used as a standalone script or imported as a module
    import argparse
    
    parser = argparse.ArgumentParser(description="Kubernetes Cluster Security")
    parser.add_argument("--kubeconfig", required=True, help="Path to kubeconfig file")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Harden command
    harden_parser = subparsers.add_parser("harden", help="Apply security hardening")
    
    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Run security scan")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate security report")
    
    args = parser.parse_args()
    
    security = ClusterSecurity(args.kubeconfig)
    
    if args.command == "harden":
        # Apply security hardening
        security.apply_network_policies()
        security.apply_pod_security_policies()
        security.apply_rbac_policies()
        print("Security hardening applied")
    elif args.command == "scan":
        # Run security scan
        security.setup_container_scanning()
        results = security.run_kube_bench()
        print(json.dumps(results, indent=2))
    elif args.command == "report":
        # Generate security report
        report = security.generate_security_report()
        print(json.dumps(report, indent=2))
    else:
        parser.print_help()
