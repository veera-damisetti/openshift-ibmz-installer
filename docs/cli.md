# CLI reference

The main entry point is **ocp-ibmz-install**. Run it from the project root.

**Note:** You can skip `create manifests` and run only `create cluster`; if manifests are not already present, `create cluster` will generate them (e.g. from `inputs.yaml` or interactive prompts) as part of the run.

---

## Global behavior

- **Help:** Use `-h` or `--help` on the app or any command (e.g. `./ocp-ibmz-install -h`, `./ocp-ibmz-install create -h`, `./ocp-ibmz-install create manifests -h`).
- **Log level:** Every command supports `--log-level` / `-l` with one of: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Default is `INFO`. Case-insensitive. Invalid values are rejected.
- **Console logging:** Messages are printed to stderr with level-based colors (DEBUG=cyan, INFO=green, WARNING=yellow, ERROR=red, CRITICAL=red background).
- **File logging:** All log records are also appended to `.ocp_ibmz_install.log` in the project root at DEBUG level, with timestamp and level.
- **Quiet libraries:** `zhmcclient`, `urllib3`, `paramiko`, and `asyncio` loggers are set to WARNING to reduce noise.

---

## create manifests

Generate `agent-config.yaml`, `install-config.yaml`, and related manifests from your configuration. **Optional:** you can skip this and run `create cluster` only; manifest generation will be done as part of `create cluster` when needed.

```bash
./ocp-ibmz-install create manifests [--log-level LEVEL]
```

**Options:**

| Option | Short | Default | Description |
|--------|--------|---------|-------------|
| `--log-level` | `-l` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

**Behavior:**

- If **inputs.yaml** is not present in the project root, the CLI switches to **interactive mode**: it prompts for all required inputs, writes `inputs.yaml`, then loads it and continues.
- If **inputs.yaml** exists, it is loaded and validated (mandatory fields and formats via `ConfigValidator`). Validation failures are reported and the command exits without generating manifests.
- **Secrets** (HMC, FTP, bastion, pull secret) are read from environment variables or prompted. If not all secrets are found in the environment, the CLI writes a **.secrets** file in the project root for later use and logs a recommendation to use environment variables instead.
- **Credential checks:** Before generating manifests, the CLI validates SSH access to the bastion host, HMC credentials, and FTP credentials. If any check fails, the command exits with an error.
- **Machine network CIDR** is computed from `infra.ip.control_nodes`, `infra.ip.compute_nodes`, and bastion IP. An SSH key pair is generated or reused (`~/.ssh/ocp-ibmz-install`) and the public key is embedded in `install-config.yaml`.
- **Output:** Manifests are written under a directory named after your cluster (`cluster.name`), e.g. `<cluster_name>/install-config.yaml`, `<cluster_name>/agent-config.yaml` (for ABI). Pull secret and SSH key are written into `install-config.yaml` after template render.

**Output files:** `install-config.yaml` always; `agent-config.yaml` when using ABI (no compute nodes).

See [Validations](validations.md) for checks performed during this step.

---

## create cluster

Create the Red Hat OpenShift cluster using generated manifests. If `inputs.yaml` or the required manifests are missing, manifest generation is run first (interactive or from `inputs.yaml`), then cluster creation proceeds.

```bash
./ocp-ibmz-install create cluster [--log-level LEVEL]
```

**Options:**

| Option | Short | Default | Description |
|--------|--------|---------|-------------|
| `--log-level` | `-l` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

**Behavior:**

- **Inputs:** If `inputs.yaml` is missing, the CLI runs manifest generation (interactive mode), then loads `inputs.yaml`. If `inputs.yaml` exists, it is loaded.
- **Manifests:** If `agent-config.yaml` or `install-config.yaml` are not found under `<cluster_name>/`, the CLI runs manifest generation, then continues.
- **Secrets:** Loaded from `.secrets` in the project root if present, otherwise from environment or prompts via `secrets_reader()`. Config and secrets are merged.
- **Bastion:** Connects to the bastion host via SSH, retrieves the gateway IP, then configures the bastion: creates workdir, configures DNS, HAProxy, and HTTP server.
- **Assets:** Downloads the OpenShift installer for the configured version, sends manifests to the bastion, runs `openshift-install` to generate boot artifacts, and copies the agent rootfs image to the HTTP server path.
- **HMC and param files:** Connects to the HMC, generates param files for each control_nodes partition, sends them to the bastion; if compute_nodes are defined, does the same for compute nodes. Param files are removed locally after upload.
- **FTP:** Prepares the FTP directory structure on the bastion and uploads boot-artifacts to the FTP server.
- **Boot:** Orchestrates node boot (control then compute if present) via the boot manager, then waits for installation completion.
- **Post-install:** Runs post-install tasks on the bastion. On success, the cluster is ready and can be accessed with `oc` from the bastion.
- **Timing:** Logs total execution time at the end.

---

## delete cluster

Destroy the Red Hat OpenShift cluster and clean up resources. Requires `inputs.yaml` in the project root.

```bash
./ocp-ibmz-install delete cluster [--log-level LEVEL]
```

**Options:**

| Option | Short | Default | Description |
|--------|--------|---------|-------------|
| `--log-level` | `-l` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

**Behavior:**

- **Inputs:** If `inputs.yaml` is not found, the command exits with an error asking you to ensure `inputs.yaml` is present.
- **Secrets:** Loaded from `.secrets` if present, otherwise from environment or prompts. Config and secrets are merged.
- **Bastion:** Connects to the bastion host via SSH.
- **HMC:** Connects to the HMC and resets boot configuration for all cluster partitions (control_nodes and compute_nodes), stopping the partitions.
- **FTP:** Cleans up cluster artifacts from the FTP server.
- **Bastion cleanup:** Removes cluster-related configurations, files, and stops related services on the bastion.
- **Timing:** Logs total execution time at the end.

---

## Command summary

| Command | Purpose |
|--------|---------|
| `create manifests` | Generate install/agent manifests; validate config and credentials; optional step. |
| `create cluster` | Full cluster creation: bastion setup, assets, param files, FTP, boot, post-install. |
| `delete cluster` | Stop partitions (HMC), clean FTP and bastion. |

---

Back to [Main documentation](README.md).
