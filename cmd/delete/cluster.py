import time
from datetime import datetime
import logging

from yaml import reader
logger = logging.getLogger("ocp_ibmz_install")
import cmd.common.helpers as helpers
from pathlib import Path
from src.cluster_deprovisioner import ClusterDeprovisioner
from src.remote_connection import RemoteHost
import cmd.common.input_reader as reader

BASE_DIR = helpers.get_basepath()
CONFIG_FILE = BASE_DIR / "inputs.yaml"

def destroy_cluster():
    start_time = time.time()
    start_timestamp = datetime.now()
    logger.debug(f"Execution started at: {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    

    if not CONFIG_FILE.exists():
        logger.error(
        "Input configuration file 'inputs.yaml' was not found at %s."
        "Please ensure the inputs.yaml file is present and try again.",
        CONFIG_FILE
        )
        return
    logger.info(
            "Input configuration file 'inputs.yaml' found at %s. "
            "Loading configuration from file.", BASE_DIR,
        )
    config = helpers.load_config(CONFIG_FILE)
    secrets_file = Path(BASE_DIR) / ".secrets"
    if secrets_file.exists():
        logger.debug("Found .secrets  for loading secrets")
        logger.warning("Recommended way is to export all the secrets using environment variables")
        secrets=helpers.load_config(secrets_file)
    else:
        secrets, x = reader.secrets_reader()
    
    config = config | secrets

    cluster_deprovisioner = ClusterDeprovisioner(config)
    bastion_client = RemoteHost(config['bastion']['ip'], config['bastion_username'], config['bastion_password'])
    exit_code, err = bastion_client.connect()
    if exit_code != 0:
        logger.error("Failed to connect to bastion host, %s", err)
        return
    logger.info("Successfully connected to bastion, Starting cluster deletion process")
    try:
        logger.info("Connecting to HMC to stop the cluster nodes and reset the boot configuration")
        exit_code, err = cluster_deprovisioner.hmc_boot_configuration_reset()
        if exit_code != 0:
            logger.error("Failed to reset boot configuration for cluster nodes, %s", err)
            return
        logger.debug("All partitions boot configuration reset successfully, Partitions are stopped.")

        logger.info("Cleaning up the FTP server artifacts for the cluster")
        exit_code, err = cluster_deprovisioner.ftp_cleanup(bastion_client)
        if exit_code != 0:
            logger.error("Failed to cleanup FTP structure for cluster, %s", err)
            return
        logger.info("Successfully deleted all the cluster artifacts from FTP server")

        logger.info("Removing all the cluster related configurations and files and stopping the related services on bastion")
        exit_code, err = cluster_deprovisioner.bastion_cleanup(bastion_client)
        if exit_code != 0:
            logger.error("Failed to cleanup bastion for cluster, %s", err)
            return
        logger.info("Removed all the cluster related configurations and files and stopped the related services on bastion successfully")
    
    finally:        
        bastion_client.close()
        end_time = time.time()
        end_timestamp = datetime.now()
        elapsed = end_time - start_time
        mins, secs = divmod(elapsed, 60)

        logger.debug(f"Execution finished at: {end_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Total execution time: {int(mins)} min {int(secs)} sec")
    
    logger.debug("Successfully deleted all the cluster resources and cleaned up the environment")
    return



    
    
    

    