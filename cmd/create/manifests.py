import json

from src.dpm_partition import DpmPartition
from src.remote_connection import RemoteHost
import cmd.common.helpers as helpers
import  cmd.common.template_renderer as template_renderer
import cmd.common.input_reader as common
from pathlib import Path
import zhmcclient
import logging
import yaml
import urllib3

logger = logging.getLogger("ocp_ibmz_install")
urllib3.disable_warnings()

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = BASE_DIR / "inputs.yaml"

def generate_manifests():
    secrets , found_in_env = common.secrets_reader()
    print(found_in_env)
    if not found_in_env: 
        logger.warning("Couldn't find all the secrets in env, so creating .secrets file for further access")
        logger.warning("Recommended way is to export all the secrets using environment variables")
        secrets_path = BASE_DIR / ".secrets"
        exit_code, err = helpers.write_secrets_file(secrets_path, secrets)
        if exit_code != 0:
            logger.error("Failed to write .secrets file: %s", err)
            return
        logger.debug("Successfully created .secrets file at %s", secrets_path)

    if not CONFIG_FILE.exists():
        logger.info(
        "Input configuration file 'inputs.yaml' was not found at %s. "
        "Switching to interactive mode to collect user inputs.",BASE_DIR,
        )
        common.input_reader()
    
    logger.info(
        "Input configuration file 'inputs.yaml' found at %s. "
        "Loading configuration from file.", BASE_DIR,
    )
    config = helpers.load_config(CONFIG_FILE)
    logger.debug("Configuration loaded")
    
    cluster_name = config["cluster"]["name"]
    cluster_dir = BASE_DIR / cluster_name
    cluster_dir.mkdir(parents=True, exist_ok=True)

    installation_method = 'ABI'
    if len(config['infra']['partitions']['compute_nodes']) > 0 :
        installation_method = 'UPI'
        logger.debug("Using User-Provisioned Infrastructure ( UPI ) as Installation mode")
    else:
        logger.debug("Using Agent Based Installer ( ABI ) as Installation mode")
        logger.info("Creating agent-config.yaml and install-config.yaml")


    logger.debug("Creating install-config.yaml")
    logger.debug("Caluculating machine network CIDR based on Node IPs")
    all_ips = config['infra']['ip']['control_nodes']+config['infra']['ip']['compute_nodes'] + [config['bastion']['ip']]
    machine_network_cidr = helpers.get_cidr(all_ips)
    config['machine_network_cidr'] = machine_network_cidr
    config = config | secrets
    
    ssh_key = helpers.generate_ssh_keypair("ocp-ibmz-install")
    if ssh_key is None:
        logger.error("Failed to generate SSH key pair")
        return
    config['ssh_key'] = ssh_key

    logger.debug("Rendering install-config.yaml from template")
    exit_code, err = template_renderer.render_template(
                template_name="install-config.yaml.template",
                output_path=Path(cluster_dir / "install-config.yaml"),
                config=config,
        )
    if exit_code != 0:
        logger.error("Unable to render the install-config.yaml from template , %s",err)
        return 
    
    logger.debug("Adding pullSecret and sshKey to install-config.yaml")
    install_config_path = cluster_dir / "install-config.yaml"
    try:
        # Load generated YAML
        with open(install_config_path, "r") as f:
            install_config = yaml.safe_load(f)
       
        pull_secret_clean = json.dumps(
        json.loads(config["pull_secret"]),
        separators=(",", ":")
        )

        install_config["pullSecret"] = pull_secret_clean
        install_config['sshKey'] = config['ssh_key']

        # Write back
        with open(install_config_path, "w") as f:
            yaml.dump(
                install_config,
                f,
                default_flow_style=False,
                sort_keys=False,
                indent=2
            )

        logger.debug("pullSecret and sshKey added to install-config.yaml successfully")

    except Exception as e:
        logger.error("Failed to update pullSecret in install-config.yaml: %s", e)
        return

    logger.debug("install-config.yaml generated successfully")

    if installation_method == 'ABI':
        logger.debug("Creating agent-config.yaml")
        
        logger.debug("Rendering agent-config.yaml from template")
        exit_code, err = template_renderer.render_template(
                template_name="agent-config.yaml.template", 
                output_path=Path(cluster_dir / "agent-config.yaml"),
                config=config,
            )
        if exit_code != 0:
            logger.error("Unable to render the agent-config.yaml from template , %s",err)
            return    
        logger.debug("agent-config.yaml generated successfully")
        logger.info("Successfully generated agent-config.yaml and install-config.yaml and saved in %s",cluster_dir)
    return
        

    session = zhmcclient.Session(
        config['hmc']['host'], config['hmc']['username'], config['hmc']['password'], verify_cert=False)
    client = zhmcclient.Client(session)
    console = client.consoles.console

    node=DpmPartition(config['cluster']['partitions'][0], config['cluster']['disk_type'], config['cluster']['network_type']) 
    
    partitions = console.list_permitted_partitions()
    partition = [x for x in partitions if x.properties.get("name") == config['cluster']['partitions'][0]][0]
    
    status = node.get_status(partition)

    nic=node.get_network_card(partition, config['cluster']['network_type'])
    disk=node.get_disk_ids(partition, config['cluster']['disk_type'])
    mac=node.get_mac_address(partition, config['cluster']['network_type'], node.get_network_card(partition, config['cluster']['network_type']))
    
    info=node.get_partition_info(partition)

    print("Partition Status: ", status)
    print("NIC: ", nic)
    print("Disk: ", disk)
    print("MAC Address: ", mac)
    print("Partition Info: ", info)

    
    
