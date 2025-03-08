# infra/azure/main.tf

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "k8s" {
  name     = "${var.cluster_name}-rg"
  location = var.location

  tags = {
    environment = var.environment
    project     = "k8s-cluster-manager"
  }
}

resource "azurerm_virtual_network" "k8s" {
  name                = "${var.cluster_name}-network"
  location            = azurerm_resource_group.k8s.location
  resource_group_name = azurerm_resource_group.k8s.name
  address_space       = ["10.1.0.0/16"]

  tags = {
    environment = var.environment
    project     = "k8s-cluster-manager"
  }
}

resource "azurerm_subnet" "k8s" {
  name                 = "${var.cluster_name}-subnet"
  resource_group_name  = azurerm_resource_group.k8s.name
  virtual_network_name = azurerm_virtual_network.k8s.name
  address_prefixes     = ["10.1.0.0/24"]
}

resource "azurerm_kubernetes_cluster" "k8s" {
  name                = var.cluster_name
  location            = azurerm_resource_group.k8s.location
  resource_group_name = azurerm_resource_group.k8s.name
  dns_prefix          = var.cluster_name

  default_node_pool {
    name            = "default"
    node_count      = var.worker_min_count
    vm_size         = var.worker_instance_type
    os_disk_size_gb = 30
    vnet_subnet_id  = azurerm_subnet.k8s.id
    
    enable_auto_scaling = true
    min_count           = var.worker_min_count
    max_count           = var.worker_max_count
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    network_policy    = "calico"
  }

  role_based_access_control_enabled = true

  tags = {
    environment = var.environment
    project     = "k8s-cluster-manager"
  }
}

# Output the kube config
resource "local_file" "kubeconfig" {
  content  = azurerm_kubernetes_cluster.k8s.kube_config_raw
  filename = "${path.module}/kubeconfig_${var.cluster_name}"
}
