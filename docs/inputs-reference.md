# Inputs reference: how to fill `inputs.yaml`

This page describes every variable in `inputs.yaml`. Copy `inputs.yaml.template` to `inputs.yaml` in the project root and set the values below. If you **do not** create `inputs.yaml`, the CLI enters **interactive mode** and prompts you for each value, then writes `inputs.yaml` for you.

---

## Cluster

| Variable | Description |
|----------|-------------|
| `cluster.name` | **Required.** Short name for the cluster (e.g. `mycluster`)|
| `cluster.base_domain` | **Required.** Base DNS domain (e.g. `example.com`). Must be valid: at least one dot, no spaces, labels only letters/digits/hyphens. |
| `cluster.version` | **Required.** Red Hat OpenShift version (e.g. `4.21.0` or `stable-4.21`). Give a valid OCP version , or give `stable-<major-version>` to select latest stable version in that particular major version , or just give `stable` to select the latest available stable version.|

---

## Infra

| Variable | Description |
|----------|-------------|
| `infra.hmc_host` | **Required.** Hostname of the Hardware Management Console (HMC) for your IBM Z system. |
| `infra.partitions.control_nodes` | **Required.** List of LPAR names for control-plane nodes (e.g. `partition1,partition2`). |
| `infra.partitions.compute_nodes` | Optional. List of LPAR names for compute (worker) nodes. Empty for Agent Based Installer (ABI) with no workers. |
| `infra.ip.control_nodes` | **Required.** List of IPs for control-plane nodes, in the same order as `infra.partitions.control_plane`. |
| `infra.ip.compute_nodes` | Optional. List of IPs for compute nodes, in the same order as `infra.partitions.compute`. |
| `infra.disk_type` | **Required.** One of: `fcp` (Fibre Channel Protocol) or `dasd` (Direct Access Storage Device). |
| `infra.network_type` | **Required.** One of: `osa` (Open Systems Adapter) or `roce` (RDMA over Converged Ethernet). |

---

## Bastion

| Variable | Description |
|----------|-------------|
| `bastion.ip` | **Required.** IP of the bastion host. |

---

## FTP

| Variable | Description |
|----------|-------------|
| `ftp.host` | **Required.** IP of the FTP server used for installation  |

---

## Secrets (not in `inputs.yaml`)

Sensitive values are read from the environment or prompted at run time; they are not stored in `inputs.yaml`.

| Variable | Description |
|----------|-------------|
| `HMC_USERNAME` | HMC login username. |
| `HMC_PASSWORD` | HMC login password. |
| `FTP_SERVER_USERNAME` | FTP server username. |
| `FTP_PASSWORD` | FTP server password. |
| `BASTION_USERNAME` | Bastion login username. |
| `BASTION_PASSWORD` | Bastion login password. |
| `PULLSECRET_PATH` | Path to a file containing the Red Hat OpenShift pull secret. If unset, the CLI uses `./authfile` in the project root , if not found ,then prompts for the pull secret. |

Export snippet and full details: [Secrets: environment variables](README.md#secrets-environment-variables) in the main doc.

---

## Example: minimal `inputs.yaml`

```yaml
cluster:
  name: mycluster
  base_domain: example.com
  version: "4.21.0"

infra:
  hmc_host: "192.168.1.10"
  partitions:
    control_nodes:
      - lpar1
      - lpar2
      - lpar3
    compute_nodes: []
  ip:
    control_nodes:
      - "192.168.1.21"
      - "192.168.1.22"
      - "192.168.1.23"
    compute_nodes: []
  disk_type: FCP
  network_type: OSA

bastion:
  ip: "192.168.1.5"

ftp:
  host: "192.168.1.20"
```

---

[Main documentation](README.md)
