# Validations

This document describes all validations performed by **ocp-ibmz-install**, when they run, and what they check. See [CLI reference](cli.md) for command behavior.

---

## When validations run

| Context | Validations applied |
|--------|---------------------|
| **Interactive mode** (no `inputs.yaml`) | Input validations as you enter each value (cluster, infra, bastion, FTP, partitions, IPs). |
| **create manifests** (with `inputs.yaml`) | Config validation (`ConfigValidator`), then credential validation (SSH, HMC, FTP). |
| **create cluster** | Relies on existing valid config and manifests; loads config and secrets. |
| **delete cluster** | Requires `inputs.yaml`; no config validation beyond load + merge with secrets. |
| **All commands** | `--log-level` must be one of the allowed values. |

---

## 1. Interactive input validations

When `inputs.yaml` is missing and you run `create manifests` or `create cluster` (which triggers manifest generation), the CLI prompts for each value and validates as you go.

### Cluster

| Field | Rules |
|-------|--------|
| **Cluster name** | Required, non-empty. Must be **lowercase** only. |
| **Base domain** | Required. Must be **lowercase**. No spaces. At least one dot (e.g. `example.com`). Must not start or end with a dot. Each label (part between dots): non-empty, must not start or end with `-`, only letters, digits, or `-` (RFC 1035–style). |
| **Red Hat OpenShift version** | Required. (`https://mirror.openshift.com/pub/openshift-v4/s390x/clients/ocp/`), value must exist here (e.g. `4.21.0`, `stable-4.21`).  |

### Infra

| Field | Rules |
|-------|--------|
| **HMC hostname** | Required, non-empty. |
| **Control-plane partitions** | At least one partition required. Exactly **1 or 3** partitions (2 is not supported). No duplicate partition names. |
| **Compute partitions** | Optional. Only prompted when control-plane count is 3. No duplicate names; none may appear in control-plane list. |
| **Control-plane IPs** | Count must match control-plane partition count. Each must be valid IPv4. No duplicates. When multiple, all must share the same first two octets (same network). |
| **Compute IPs** | Only when compute partitions are given. Count must match compute partition count. Valid IPv4, no duplicates, no overlap with control-plane IPs, same network (first two octets) as control nodes. |
| **Disk type** | Required. One of: **FCP**, **DASD**. |
| **Network type** | Required. One of: **OSA**, **RoCE**. |

### Bastion and FTP

| Field | Rules |
|-------|--------|
| **Bastion IP** | Required. Valid IPv4. Must be in the same network as control (and compute) nodes (first two octets match). Must not be one of the control or compute IPs. |
| **FTP host** | Required. Valid IPv4. |

### Secrets (when prompted)

If not provided via environment variables, each of the following must be non-empty when prompted: **HMC username**, **HMC password**, **FTP username**, **FTP password**, **Bastion username**, **Bastion password**, **Pull secret** (or file via `authfile` / `PULLSECRET_PATH`).

---

## 2. Config validation (`inputs.yaml`)

When **create manifests** runs with an existing `inputs.yaml`, the loaded config is validated by **ConfigValidator** before any manifest generation or credential checks.

### Cluster

| Check | Rule |
|-------|------|
| `cluster.name` | Required. Must contain **only lowercase** letters. |
| `cluster.base_domain` | Required. Must be **lowercase**. Same format rules as interactive base domain (dot, no spaces, valid labels). |
| `cluster.version` | Required. If mirror is reachable, must exist on the Red Hat OpenShift mirror for s390x. |

### Infra

| Check | Rule |
|-------|------|
| `infra.hmc_host` | Required. |
| `infra.disk_type` | Required. |
| `infra.network_type` | Required. |
| `infra.partitions.control_nodes` | Must contain **either 1 or 3** partitions (not 2). |
| `infra.partitions.compute_nodes` | If present: not allowed when `control_nodes` count is 1. |
| Partition vs IP counts | `control_nodes` partition count must equal `infra.ip.control_nodes` count. If compute is used, `compute_nodes` partition count must equal `infra.ip.compute_nodes` count. |

### IP and network rules

| Check | Rule |
|-------|------|
| Control IPs | Every `infra.ip.control_nodes` entry must be valid IPv4. |
| Compute IPs | Every `infra.ip.compute_nodes` entry must be valid IPv4. |
| Bastion IP | `bastion.ip` required, must be valid IPv4. |
| FTP host | `ftp.host` required, must be valid IPv4. |
| No duplicate IPs | No duplicate IPs across control_nodes, compute_nodes, and bastion. |
| Same network | All control, compute, and bastion IPs must share the same first two octets. |

---

## 3. Credential (authentication) validation

After config validation passes, **create manifests** runs **AuthenticationValidator** before writing any manifests.

| Check | What is validated |
|-------|-------------------|
| **SSH (bastion)** | SSH login to bastion host using `bastion_username` and `bastion_password`. Connection must succeed. |
| **HMC** | Login to HMC at `infra.hmc_host` using `hmc_username` and `hmc_password`. Connection must succeed. |
| **FTP** | From the bastion, `lftp` is used to connect to `ftp.host` with `ftp_username` and `ftp_password`. If `lftp` is not installed, the validator may attempt to install it; FTP login must then succeed. |

If any of these fail, manifest generation stops and an error is reported.

---

## 4. Other runtime checks

| Check | When | Rule |
|-------|------|-----|
| **inputs.yaml load** | create manifests (file mode), create cluster, delete cluster | File must exist (except create cluster can trigger interactive + generation). YAML must be valid (`yaml.safe_load`). |
| **Template variables** | create manifests | Jinja2 uses `StrictUndefined`; every variable referenced in templates must be defined or rendering fails. |
| **Machine network CIDR** | create manifests | Derived from `infra.ip.control_nodes`, `infra.ip.compute_nodes`, and bastion IP; all must be valid IPv4. |
| **SSH key** | create manifests | Key pair generated or reused under `~/.ssh` (e.g. `ocp-ibmz-install`); failure (e.g. no `ssh-keygen`) stops the process. |
| **Log level** | All commands | `--log-level` / `-l` must be one of: **DEBUG**, **INFO**, **WARNING**, **ERROR**, **CRITICAL** (case-insensitive). |

---

## 5. Summary table

| Input / check | Required | Validation |
|---------------|----------|------------|
| cluster.name | Yes | Non-empty, lowercase only |
| cluster.base_domain | Yes | Lowercase, valid domain (dot, labels, no spaces) |
| cluster.version | Yes | Non-empty; must exist on mirror when reachable |
| infra.hmc_host | Yes | Non-empty |
| infra.disk_type | Yes | Present |
| infra.network_type | Yes | Present |
| infra.partitions.control_nodes | Yes | Length 1 or 3 |
| infra.partitions.compute_nodes | Conditional | Only when control_nodes count is 3; count must match compute IPs |
| infra.ip.control_nodes | Yes | Valid IPv4, count = control_nodes length, same /16 |
| infra.ip.compute_nodes | If compute used | Valid IPv4, count = compute_nodes length, same /16, no overlap with control |
| bastion.ip | Yes | Valid IPv4, same network, not a node IP |
| ftp.host | Yes | Valid IPv4 |
| Secrets (HMC, FTP, Bastion, pull) | Yes | Non-empty (env or prompt) |
| SSH to bastion | create manifests | Must succeed |
| HMC login | create manifests | Must succeed |
| FTP login | create manifests | Must succeed (from bastion) |
| Log level | All | One of DEBUG, INFO, WARNING, ERROR, CRITICAL |

---

[Main documentation](README.md)
