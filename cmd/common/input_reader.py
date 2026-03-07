from pathlib import Path
import questionary
from questionary import Style
import yaml
import sys
import logging
import requests
import os

logger = logging.getLogger("ocp_ibmz_install")

# Styling for questionary prompts

STYLE = Style([
    ("qmark", "fg:#00afff bold"),
    ("question", "bold"),
    ("pointer", "fg:#00afff bold"),
    ("highlighted", "fg:#00afff bold"),
    ("selected", "fg:#00afff"),
    ("answer", "fg:#00afff bold"),
])
REPO_ROOT = Path(__file__).resolve().parents[2]

# Main function to read user inputs interactively and save to inputs.yaml
def input_reader():
    config_path = REPO_ROOT / "inputs.yaml"

    try:
        cluster_name = questionary.text(
            "Cluster name:",
            validate=lambda x: bool(x.strip()) or "Cluster name cannot be empty",
        ).ask()
        if cluster_name is None:
            sys.exit(1)

        base_domain = ask_base_domain()

        version = ask_ocp_version()

        hmc_host = questionary.text(
            "HMC host IP / hostname:",
            validate=lambda x: bool(x.strip()) or "HMC host is required",
        ).ask()
        if hmc_host is None:
            sys.exit(1)

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

        # ---- Partitions ----
        control_plane_partitions = questionary.text(
            "Control-plane partitions (comma-separated) e.g., partition1,partition2:",
        ).ask()
        if control_plane_partitions is None:
            sys.exit(1)

        compute_partitions = questionary.text(
            "Compute partitions (comma-separated, optional) e.g., partition3,partition4:",
        ).ask() or ""

        # ---- IPs ----
        control_plane_ips = questionary.text(
            "Control-plane IPs (comma-separated) e.g., ip1,ip2:",
        ).ask()
        if control_plane_ips is None:
            sys.exit(1)

        compute_ips = questionary.text(
            "Compute IPs (comma-separated, optional) e.g., ip3,ip4 :",
        ).ask() or ""

        # ---- Bastion ----
        bastion_ip = questionary.text(
            "Bastion IP address:",
            validate=lambda x: bool(x.strip()) or "Bastion IP is required",
        ).ask()
        if bastion_ip is None:
            sys.exit(1)

        # ---- FTP ----
        ftp_host = questionary.text(
            "FTP host:",
            validate=lambda x: bool(x.strip()) or "FTP host is required",
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
                    "control_nodes": [
                        p.strip() for p in control_plane_partitions.split(",") if p.strip()
                    ],
                    "compute_nodes": [
                        p.strip() for p in compute_partitions.split(",") if p.strip()
                    ],
                },
                "ip": {
                    "control_nodes": [
                        ip.strip() for ip in control_plane_ips.split(",") if ip.strip()
                    ],
                    "compute_nodes": [
                        ip.strip() for ip in compute_ips.split(",") if ip.strip()
                    ],
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
    
# Validate base domain input as per RFC 1035 and common domain name rules
def validate_base_domain(value: str):
    if not value or not value.strip():
        return "Base domain cannot be empty"

    value = value.strip()

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

# Ask user for base domain with validation, re-prompting until valid input is received or user cancels
def ask_base_domain():
    base_domain = questionary.text(
        "Base domain:",
    ).ask()

    if base_domain is None:
        sys.exit(1)

    validation = validate_base_domain(base_domain)
    if validation is True:
        return base_domain.strip().lower()

    logger.warning(validation)
    return ask_base_domain()

# Fetch available OpenShift versions from mirror
def fetch_valid_ocp_versions():
    url = "https://mirror.openshift.com/pub/openshift-v4/s390x/clients/ocp/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception:
        logger.warning(
            "Unable to get the available versions from OpenShift mirror, proceeding without validation."
        )
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

# Ask user for OpenShift version, validating against mirror versions if available, re-prompting until valid input is received or user cancels
def ask_ocp_version():
    valid_versions = fetch_valid_ocp_versions()

    while True:
        version = questionary.text(
            "OpenShift version (e.g. 4.21.0 or stable-4.21 ) :"
        ).ask()

        if version is None:
            sys.exit(0)

        if not valid_versions:
            return version

        if version in valid_versions:
            return version

        if version == '':
            logger.warning("Version cannot be empty. Please enter a valid Openshift version.")
        else:
            logger.warning(
                f"Version '{version}' not found in OpenShift mirror. Please enter a valid version."
            )

# Get secret value from environment variable or prompt user for input, exiting if value is not provided

def get_secret(env_name: str, prompt: str, secret: bool = False):
    value = os.getenv(env_name)
    if value and value.strip():
        return value.strip()

    if secret:
        value = questionary.password(
            prompt,
            validate=lambda x: bool(x.strip()) or f"{env_name} is required",
        ).ask()
    else:
        value = questionary.text(
            prompt,
            validate=lambda x: bool(x.strip()) or f"{env_name} is required",
        ).ask()

    if value is None:
        sys.exit(1)
     
    os.environ[env_name] = value.strip()
    return value.strip()

def secrets_reader():
    secrets = {}
    env_vars = ["HMC_USERNAME","HMC_PASSWORD","FTP_SERVER_USERNAME","FTP_PASSWORD","BASTION_USERNAME","BASTION_PASSWORD"]
    found_in_env = True
    for var in env_vars: 
        if not os.getenv(var):
            found_in_env = False
            break
    
    hmc_username = get_secret(
        "HMC_USERNAME",
        "HMC username:",
    )

    hmc_password = get_secret(
        "HMC_PASSWORD",
        "HMC password:",
        secret=True,
    )

    # ---- FTP ----
    ftp_username = get_secret(
        "FTP_SERVER_USERNAME",
        "FTP username:",
    )

    ftp_password = get_secret(
        "FTP_PASSWORD",
        "FTP password:",
        secret=True,
    )

    # ---- Bastion ----
    bastion_username = get_secret(
        "BASTION_USERNAME",
        "Bastion username:",
    )

    bastion_password = get_secret(
        "BASTION_PASSWORD",
        "Bastion password:",
        secret=True,
    )

    pull_secret = get_pull_secret()

    secrets['hmc_username'] = hmc_username
    secrets['pull_secret'] = pull_secret
    secrets['hmc_password'] = hmc_password
    secrets['ftp_username'] = ftp_username
    secrets['ftp_password'] = ftp_password
    secrets['bastion_username'] = bastion_username
    secrets['bastion_password'] = bastion_password

    

    return secrets,found_in_env
    
# Get pull secret from authfile, environment variable, or prompt user for input, exiting if value is not provided
def get_pull_secret():
    # Repo root: ./authfile
    authfile = REPO_ROOT / "authfile"
    if authfile.exists() and authfile.is_file():
        return authfile.read_text(encoding="utf-8").strip()

    # Env: PULLSECRET_PATH
    pullsecret_path = os.getenv("PULLSECRET_PATH")
    if pullsecret_path:
        path = Path(pullsecret_path)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8").strip()

        logger.error(f"PULLSECRET_PATH is set but file not found: {pullsecret_path}")
        sys.exit(1)

    # Prompt user (secret input)
    pull_secret = questionary.password(
        "Paste OpenShift pull secret:",
        validate=lambda x: bool(x.strip()) or "Pull secret is required",
    ).ask()

    if pull_secret is None:
        sys.exit(1)

    return pull_secret.strip()

