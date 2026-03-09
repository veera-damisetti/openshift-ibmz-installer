from pathlib import Path
import questionary
from questionary import Style
import yaml
import sys
import logging
import requests
import os
import cmd.common.helpers as helpers
import inspect

logger = logging.getLogger("ocp_ibmz_install")

STYLE = Style([
    ("qmark", "fg:red bold"),
    ("question", "bold"),
    ("pointer", "fg:#74ff00 bold"),
    ("highlighted", "fg:#74ff00 bold"),
    ("selected", "fg:#74ff00"),
    ("answer", "fg:#fcff00 bold"),
])

REPO_ROOT = Path(__file__).resolve().parents[2]


def get_prefix(ip):
    parts = ip.split(".")
    return ".".join(parts[:2])


def validate_base_domain(value: str):
    value = value.strip()
    if not value:
        return "Base domain cannot be empty"
    if value != value.lower():
        return "Base domain must be lowercase"
    if " " in value:
        return "Base domain must not contain spaces"
    if "." not in value:
        return "Base domain must contain a dot (example: example.com)"
    if value.startswith(".") or value.endswith("."):
        return "Base domain must not start or end with a dot"

    labels = value.split(".")
    for label in labels:
        if not label:
            return "Invalid base domain format"
        if label.startswith("-") or label.endswith("-"):
            return "Domain labels must not start or end with '-'"
        for ch in label:
            if not (ch.isalnum() or ch == "-"):
                return "Domain labels may contain only letters, digits, or '-'"
    return True

def fetch_valid_ocp_versions():
    url = "https://mirror.openshift.com/pub/openshift-v4/s390x/clients/ocp/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception:
        return None
    
    versions = set()
    for line in resp.text.splitlines():
        if 'href="' not in line:
            continue
        start = line.find('href="') + 6
        end = line.find('"', start)
        name = line[start:end].rstrip("/")
        if name and (name[0].isdigit() or name.startswith("stable")):
            versions.add(name)
    return versions


def ocp_version_validator(valid_versions):
    def validator(value):
        value = value.strip()
        if not value:
            return "Version cannot be empty"
        if valid_versions and value not in valid_versions:
            return "Version not found in OpenShift mirror"
        return True
    return validator

def input_reader():

    config_path = REPO_ROOT / "inputs.yaml"
    try:
        cluster_name = questionary.text(
            "Cluster name:",
            validate=lambda x: (
                "Cluster name cannot be empty"
                if not x.strip()
                else (
                    "Cluster name must be lowercase"
                    if x.strip() != x.strip().lower()
                    else True
                )
            ),
            style=STYLE
        ).ask()

        if cluster_name is None:
            sys.exit(1)

        base_domain = questionary.text(
            "Base domain:",
            validate=validate_base_domain,
            style=STYLE
        ).ask()

        if base_domain is None:
            sys.exit(1)
        valid_versions = fetch_valid_ocp_versions()
        version = questionary.text(
            "OpenShift version (e.g. 4.21.0 or stable-4.21 ):",
            validate=ocp_version_validator(valid_versions),
            style=STYLE
        ).ask()

        if version is None:
            sys.exit(1)

        hmc_host = questionary.text(
            "HMC hostname:",
            validate=lambda x: bool(x.strip()) or "HMC hostname is required",
            style=STYLE
        ).ask()

        if hmc_host is None:
            sys.exit(1)

        def validate_control_partitions(value):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            errors = []
            if not parts:
                errors.append("At least one control-plane partition is required")
            if len(parts) == 2:
                errors.append("2 control-plane nodes are not supported. Use 1 or 3.")

            seen = set()
            duplicates = set()
            for p in parts:
                if p in seen:
                    duplicates.add(p)
                seen.add(p)

            if duplicates:
                errors.append(
                    f"Duplicate partition(s): {', '.join(sorted(duplicates))}"
                )
            if errors:
                return ". ".join(errors)
            
            return True

        control_plane_partitions = questionary.text(
            "Control-plane partitions (comma-separated):",
            validate=validate_control_partitions,
            style=STYLE
        ).ask()

        if control_plane_partitions is None:
            sys.exit(1)

        control_list = [
            p.strip() for p in control_plane_partitions.split(",") if p.strip()
        ]

        compute_list = []
        if len(control_list) > 1:
            def validate_compute_partitions(value):
                parts = [p.strip() for p in value.split(",") if p.strip()]
                errors = []
                seen = set()
                duplicates = set()
                for p in parts:
                    if p in seen:
                        duplicates.add(p)
                    seen.add(p)

                if duplicates:
                    errors.append(
                        f"Duplicate compute partition(s): {', '.join(sorted(duplicates))}"
                    )
                overlap = set(parts) & set(control_list)

                if overlap:
                    errors.append(
                        f"Already used in control partitions: {', '.join(sorted(overlap))}"
                    )
                if errors:
                    return ". ".join(errors)

                return True

            compute_partitions = questionary.text(
                "Compute partitions (comma-separated):",
                validate=validate_compute_partitions,
                style=STYLE
            ).ask() or ""

            compute_list = [
                p.strip() for p in compute_partitions.split(",") if p.strip()
            ]

        def validate_control_ips(value):
            ips = [ip.strip() for ip in value.split(",") if ip.strip()]
            errors = []

            if len(ips) != len(control_list):
                errors.append(
                    f"Expected {len(control_list)} IPs but got {len(ips)}"
                )

            invalid = [ip for ip in ips if not helpers.ipv4_validator(ip)]

            if invalid:
                errors.append(
                    f"Invalid IPv4 address(es): {', '.join(invalid)}"
                )

            seen = set()
            duplicates = set()
            for ip in ips:
                if ip in seen:
                    duplicates.add(ip)
                seen.add(ip)

            if duplicates:
                errors.append(
                    f"Duplicate control-plane IP(s): {', '.join(sorted(duplicates))}"
                )

            if len(ips) > 1:
                prefixes = {get_prefix(ip) for ip in ips if helpers.ipv4_validator(ip)}
                if len(prefixes) > 1:
                    errors.append(
                        "All control-plane IPs must belong to the same network (first two octets must match)"
                    )
            if errors:
                return ". ".join(errors)
            return True

        control_plane_ips = questionary.text(
            f"Control-plane IPs (comma-separated) [required: {len(control_list)}]:",
            validate=validate_control_ips,
            style=STYLE
        ).ask()

        if control_plane_ips is None:
            sys.exit(1)

        control_ip_list = [
            ip.strip() for ip in control_plane_ips.split(",") if ip.strip()
        ]

        control_prefix = get_prefix(control_ip_list[0])

        compute_ip_list = []

        if len(control_list) > 1 and compute_list:

            def validate_compute_ips(value):

                ips = [ip.strip() for ip in value.split(",") if ip.strip()]

                errors = []

                if len(ips) != len(compute_list):
                    errors.append(
                        f"Expected {len(compute_list)} IPs but got {len(ips)}"
                    )

                invalid = [ip for ip in ips if not helpers.ipv4_validator(ip)]

                if invalid:
                    errors.append(
                        f"Invalid IPv4 address(es): {', '.join(invalid)}"
                    )

                seen = set()
                duplicates = set()

                for ip in ips:
                    if ip in seen:
                        duplicates.add(ip)
                    seen.add(ip)

                if duplicates:
                    errors.append(
                        f"Duplicate compute IP(s): {', '.join(sorted(duplicates))}"
                    )

                overlap = set(ips) & set(control_ip_list)

                if overlap:
                    errors.append(
                        f"Already used in control-plane IPs: {', '.join(sorted(overlap))}"
                    )

                wrong_prefix = [
                    ip for ip in ips
                    if helpers.ipv4_validator(ip) and get_prefix(ip) != control_prefix
                ]

                if wrong_prefix:
                    errors.append(
                        f"Compute IPs must belong to the same network as the control nodes (first two octets must match: {control_prefix}.x.x)"
                    )
                if errors:
                    return ". ".join(errors)
                return True

            compute_ips = questionary.text(
                f"Compute IPs (comma-separated) [required: {len(compute_list)}]:",
                validate=validate_compute_ips,
                style=STYLE
            ).ask() or ""

            compute_ip_list = [
                ip.strip() for ip in compute_ips.split(",") if ip.strip()
            ]

        disk_type = questionary.select(
            "Disk type:",
            choices=["FCP", "DASD"],
            style=STYLE,
        ).ask()

        if disk_type is None:
            sys.exit(1)

        network_type = questionary.select(
            "Network type:",
            choices=["OSA", "RoCE"],
            style=STYLE,
        ).ask()

        if network_type is None:
            sys.exit(1)

        def validate_bastion_ip(value):
            value = value.strip()
            if not value:
                return "Bastion IP is required"
            if not helpers.ipv4_validator(value):
                return "Invalid IPv4 address"
            if get_prefix(value) != control_prefix:
                return f"Bastion IP must be in the same network as control nodes and compute nodes (first two octets must match: {control_prefix}.x.x)"
            if value in control_ip_list or value in compute_ip_list:
                return "Bastion IP must not be part of control or compute IPs"
            return True

        bastion_ip = questionary.text(
            "Bastion IP address:",
            validate=validate_bastion_ip,
            style=STYLE
        ).ask()

        if bastion_ip is None:
            sys.exit(1)

        # FTP host validation 

        ftp_host = questionary.text(
            "FTP host:",
            validate=lambda x: (
                "FTP host is required"
                if not x.strip()
                else (
                    True if helpers.ipv4_validator(x.strip())
                    else "FTP host must be a valid IPv4 address"
                )
            ),
            style=STYLE
        ).ask()

        if ftp_host is None:
            sys.exit(1)

        config = {
            "cluster": {
                "name": cluster_name,
                "base_domain": base_domain,
                "version": version,
            },
            "infra": {
                "hmc_host": hmc_host,
                "disk_type": disk_type,
                "network_type": network_type,
                "partitions": {
                    "control_nodes": control_list,
                    "compute_nodes": compute_list,
                },
                "ip": {
                    "control_nodes": control_ip_list,
                    "compute_nodes": compute_ip_list,
                },
            },
            "bastion": {
                "ip": bastion_ip,
            },
            "ftp": {
                "host": ftp_host,
            },
        }

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False)

        print(f"inputs.yaml created at {config_path}")

    except (KeyboardInterrupt, EOFError):
        print("\nInput aborted by user. Exiting.")
        raise SystemExit(1)

def get_secret(env_name: str, prompt: str, secret: bool = False):
    value = os.getenv(env_name)
    if value and value.strip():
        return value.strip()

    if secret:
        value = questionary.password(
            prompt,
            validate=lambda x: bool(x.strip()) or f"{env_name} is required",
            style=STYLE
        ).ask()
    else:
        value = questionary.text(
            prompt,
            validate=lambda x: bool(x.strip()) or f"{env_name} is required",
            style=STYLE
        ).ask()

    if value is None:
        sys.exit(1)

    os.environ[env_name] = value.strip()
    return value.strip()


def secrets_reader():
    secrets = {}
    env_vars = [
        "HMC_USERNAME",
        "HMC_PASSWORD",
        "FTP_SERVER_USERNAME",
        "FTP_PASSWORD",
        "BASTION_USERNAME",
        "BASTION_PASSWORD",
    ]

    found_in_env = all(os.getenv(v) for v in env_vars)

    hmc_username = get_secret("HMC_USERNAME", "HMC username:")
    hmc_password = get_secret("HMC_PASSWORD", "HMC password:", secret=True)

    ftp_username = get_secret("FTP_SERVER_USERNAME", "FTP username:")
    ftp_password = get_secret("FTP_PASSWORD", "FTP password:", secret=True)

    bastion_username = get_secret("BASTION_USERNAME", "Bastion username:")
    bastion_password = get_secret("BASTION_PASSWORD", "Bastion password:", secret=True)

    caller = inspect.stack()[1].function
    if caller not in ["cluster", "destroy_cluster"]:
        pull_secret = get_pull_secret()
        secrets["pull_secret"] = pull_secret

    secrets["hmc_username"] = hmc_username
    secrets["hmc_password"] = hmc_password
    secrets["ftp_username"] = ftp_username
    secrets["ftp_password"] = ftp_password
    secrets["bastion_username"] = bastion_username
    secrets["bastion_password"] = bastion_password

    return secrets, found_in_env

def get_pull_secret():
    authfile = REPO_ROOT / "authfile"
    if authfile.exists() and authfile.is_file():
        return authfile.read_text(encoding="utf-8").strip()

    pullsecret_path = os.getenv("PULLSECRET_PATH")
    if pullsecret_path:
        path = Path(pullsecret_path)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8").strip()

        logger.error(f"PULLSECRET_PATH is set but file not found: {pullsecret_path}")
        sys.exit(1)

    pull_secret = questionary.password(
        "Paste OpenShift pull secret:",
        validate=lambda x: bool(x.strip()) or "Pull secret is required",
        style=STYLE
    ).ask()

    if pull_secret is None:
        sys.exit(1)

    return pull_secret.strip()