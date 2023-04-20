# NEural TransmissionS (NETS) Lab JupyterHub deployment
This repository contains the Helm chart for the JupyterHub deployment at the [NEural TransmissionS (NETS) Lab](https://research.fit.edu/nets/) at the Florida Institute of Technology.

## Prerequisites
- Kubernetes cluster
- Helm 3.x
- Either one of these options for ingress
  - A load balancer (e.g. MetalLB or cloud provider load balancer)
  - A CloudFlare account with a domain and Zero Trust Dashboard enabled

## Configuration
1. Clone the repository
2. (Optional) If you are using CloudFlare Tunnel, copy the example secret file and fill in the values
```bash
# Clone the repository
git clone
cd nets-jupyterhub
# Copy the example secret file and edit it
cp secrets.yaml.example secrets.yaml
nano secrets.yaml
```
## Installation/Upgrade
```bash
helm dependency update
./upgrade.sh
```