# OpenShift IBM Z Installer

This project provides a CLI ( **ocp-ibmz-install** ) for deploying **Red Hat OpenShift Container Platform** on **IBM zSystems / LinuxONE** (s390x) with **Dynamic Partition Manager (DPM) LPARs** as cluster nodes.
You provide a configuration file, and the CLI generates the required installation manifests and orchestrates the cluster lifecycle, including creation and teardown.


## Overview

The **ocp-ibmz-install** CLI supports:

- **Create manifests** — Generate `agent-config.yaml`, `install-config.yaml`, and related manifests from your inputs (cluster name, base domain, HMC, partitions, IPs, bastion, FTP, etc.). Optional: you can skip this and have manifests generated as part of create cluster.
- **Create cluster** — Run the full Red Hat OpenShift cluster creation using those manifests (or generate them first if missing).
- **Delete cluster** — Destroy the cluster and clean up all resources.

## Documentation

For prerequisites, step-by-step process, CLI reference, and validations, see:

[Main documentation](docs/README.md)
