import logging
import sys
import urllib3
from pathlib import Path
import cmd.common.helpers as helpers
import cmd.common.input_reader as reader
import cmd.common.configure_bastion as bastion
from src.remote_connection import RemoteHost


logger = logging.getLogger("ocp_ibmz_install")
urllib3.disable_warnings()

BASE_DIR = helpers.get_basepath()
CONFIG_FILE = BASE_DIR / "inputs.yaml"

def cluster():
    logger.debug("Checking for inputs.yaml")
    
    if not CONFIG_FILE.exists():
        logger.error(
        "Input configuration file 'inputs.yaml' was not found at %s. "
        "Please run manifests creation step before starting this step",BASE_DIR,
        )
        return

    logger.info(
            "Input configuration file 'inputs.yaml' found at %s. "
            "Loading configuration from file.", BASE_DIR,
        )
    config = helpers.load_config(CONFIG_FILE)
    logger.debug("Input Configuration loaded")
    
    configs_dir = BASE_DIR / config['cluster']['name']

    logger.info("Looking for agent-config.yaml and install-config.yaml under %s",BASE_DIR)
    if not (configs_dir / "agent-config.yaml").exists() or not (configs_dir / "install-config.yaml").exists():
        logger.error("Required manifests not found, please create manifests before starting the cluster installation")
        return
    logger.debug("Consuming agent-config.yaml and install-config.yaml from %s",configs_dir)
    logger.debug("Loading secrets")
    secrets_file = Path(BASE_DIR) / ".secrets"
    if secrets_file.exists():
        logger.debug("Found .secrets  for loading secrets")
        logger.warning("Recommended way is to export all the secrets using environment variables")
        secrets=helpers.load_config(secrets_file)
    else:
        secrets, x =reader.secrets_reader()


    config = config | secrets

    remote_host = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])
    remote_host.connect()
    gateway=remote_host.get_gateway()
    config['gateway']=gateway

    bastion.create_workdir(config)
    bastion.configure_dns(config)
    bastion.configure_haproxy(config)
    
    return
    


    
