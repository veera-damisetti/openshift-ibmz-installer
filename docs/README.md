# OpenShift IBM Z Installer — Documentation

---

## Overview

This project installs **Red Hat OpenShift on IBM Z** using **DPM LPARs as nodes**. It helps you provision a Red Hat OpenShift cluster where control-plane and compute nodes run as LPARs (Logical Partitions). You provide configuration (cluster name, base domain, HMC, partitions, IPs, bastion, FTP, etc.), and the tool generates the required install manifests and drives the cluster creation or teardown.

---

## CLI

The **ocp-ibmz-install** CLI is the main interface. Run it from the project root.

| Command | Purpose |
|--------|---------|
| `./ocp-ibmz-install create manifests ` | Generate required manifests (`agent-config.yaml`, `install-config.yaml`, etc.) from your inputs. |
| `./ocp-ibmz-install create cluster ` | Run the full cluster creation process (manifests are used or generated if missing). |
| `./ocp-ibmz-install delete cluster`  | Destroy the cluster and clean up resources. |

For options and details, see [CLI reference](cli.md).

---

## Process: steps to follow for creation

High-level steps to create a Red Hat OpenShift cluster:

1. **Create manifests (optional)**  
   Run:
   ```bash
   ./ocp-ibmz-install create manifests --log-level DEBUG
   ```
   This generates `agent-config.yaml`, `install-config.yaml`, and related manifests (and, if `inputs.yaml` is missing, prompts for inputs and writes `inputs.yaml`).  
   **You can skip this step.** If you skip it, **create cluster** will generate the manifests as part of its run when they are not already present (e.g. it will prompt for inputs or use existing `inputs.yaml` and then produce the manifests before continuing with cluster creation).

2. **Create cluster**  
   Run:
   ```bash
   ./ocp-ibmz-install create cluster --log-level DEBUG
   ```
   This performs the full cluster creation. If manifests do not exist yet, manifest generation is handled as part of this command, then creation proceeds.

3. **Delete cluster (when needed)**  
   Run:
   ```bash
   ./ocp-ibmz-install delete cluster --log-level DEBUG
   ```
   This destroys the cluster and all associated resources.

---

## Create manifests: inputs and template

To run **create manifests** (or **create cluster** when it generates manifests), you can either use a config file or let the CLI prompt you.

- **Option A — Config file:** Create `inputs.yaml` in the project root from the template. Copy `inputs.yaml.template` to `inputs.yaml`, then fill in the variables. See [Inputs reference](inputs-reference.md) for a description of each variable.
- **Option B — No `inputs.yaml`:** If you do **not** create `inputs.yaml`, the CLI enters **interactive mode**: it will prompt you for all inputs (cluster name, base domain, version, HMC, partitions, IPs, bastion, FTP, etc.) and then write `inputs.yaml` and generate the manifests.

**Template (`inputs.yaml.template`):**

```yaml
cluster:
  name: ''
  base_domain: ''
  version: ''

infra:
  hmc_host: 'x.x.x.x'
  partitions:
    control_nodes:
      - t313lp16
    compute_nodes: []
  ip:
    control_nodes:
      - x.x.x.x
    compute_nodes: []
  disk_type: fcp
  network_type: osa

bastion:
  ip: 'x.x.x.x'
  username: 'root'
  password: ''

ftp:
  host: 'x.x.x.x'
```

(Secrets are not stored in `inputs.yaml`; use environment variables or interactive prompts. See below.)

---

## Secrets: environment variables

Sensitive values (HMC, FTP, bastion credentials, pull secret) are read from environment variables or, if unset, prompted interactively. To avoid typing them each run, export the variables before running the CLI:

```bash
export HMC_USERNAME="your_hmc_username"
export HMC_PASSWORD="your_hmc_password"
export FTP_SERVER_USERNAME="your_ftp_username"
export FTP_PASSWORD="your_ftp_password"
export BASTION_USERNAME="root"
export BASTION_PASSWORD="your_bastion_password"
```

Pull secret: place the secret in a file and either put it at `./authfile` in the project root or set:

```bash
export PULLSECRET_PATH="/path/to/your/pull-secret.txt"
```

Then run `./ocp-ibmz-install create manifests` or `./ocp-ibmz-install create cluster` as needed.

---

## Quick links

| Topic | Description |
|-------|-------------|
| [CLI reference](cli.md) | Commands, options, and behavior |
| [Inputs reference](inputs-reference.md) | How to fill `inputs.yaml` — description of each variable |
| [Validations](validations.md) | All validations performed by the tool |
