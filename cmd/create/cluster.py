import logging
import os
import time
from datetime import datetime
from typer import echo
import urllib3
from pathlib import Path
import cmd.common.helpers as helpers
import cmd.common.input_reader as reader
from src.remote_connection import RemoteHost
import cmd.common.asset_generator as asset_generator
from src.hmc import HMCClient
from src.paramfile_generator import ParamFileGenerator  
from src.dpm_partition import DpmPartition
from src.ftp_connector import FtpConnector
import cmd.common.boot_manager as boot_manager
import cmd.common.post_install_runner as post_install_runner
from src.bastion_setup_manager import BastionSetupManager
import cmd.create.manifests as manifests


logger = logging.getLogger("ocp_ibmz_install")
urllib3.disable_warnings()

BASE_DIR = helpers.get_basepath()
CONFIG_FILE = BASE_DIR / "inputs.yaml"

def cluster():
    start_time = time.time()
    start_timestamp = datetime.now()
    logger.debug(f"Installation started at: {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    logger.debug("Looking for input configuration file at %s", CONFIG_FILE)
    
    if not CONFIG_FILE.exists():
        logger.warning(
        "Input configuration file 'inputs.yaml' was not found at %s. "
        "Starting manifests generation process", BASE_DIR,
        )
        manifests.generate_manifests()

    logger.info(
            "Input configuration file 'inputs.yaml' found at %s. "
            "Loading configuration from file.", BASE_DIR,
        )
    config = helpers.load_config(CONFIG_FILE)
    logger.debug("Input Configuration loaded")
    
    configs_dir = BASE_DIR / config['cluster']['name']

    logger.info("Looking for agent-config.yaml and install-config.yaml under %s",BASE_DIR)
    if not (configs_dir / "agent-config.yaml").exists() or not (configs_dir / "install-config.yaml").exists():
        logger.warning("Required manifests not found," \
        "Starting manifests generation process to create agent-config.yaml and install-config.yaml")
        manifests.generate_manifests()

    logger.debug("Consuming agent-config.yaml and install-config.yaml from %s",configs_dir)
    logger.debug("Loading secrets")
    secrets_file = Path(BASE_DIR) / ".secrets"
    if secrets_file.exists():
        logger.debug("Found .secrets  for loading secrets")
        logger.warning("Recommended way is to export all the secrets using environment variables")
        secrets=helpers.load_config(secrets_file)
    else:
        secrets, x = reader.secrets_reader()


    config = config | secrets

    logger.debug("Getting gateway IP from bastion host")
    bastion_client = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])
    exit_code, err = bastion_client.connect()
    if exit_code != 0:
        logger.error("Failed to connect to bastion host, %s", err)
        return
    logger.debug("Successfully connected to bastion host to retrieve gateway IP")

    try:
        gateway=bastion_client.get_gateway()
        if gateway is not None:
            config['gateway']=gateway
        else:
            logger.error("Failed to retrieve gateway IP from bastion host")
            return
        
        logger.debug("Starting the configuration of bastion host for cluster installation")
        
        bastion_setup_manager = BastionSetupManager(bastion_client, config)
        
        exit_code , err = bastion_setup_manager.create_workdir() 
        if exit_code != 0:
            logger.error("Failed to create workdir on bastion host, %s", err)
            return
        
        exit_code , err = bastion_setup_manager.configure_dns()
        if exit_code != 0:
            logger.error("Failed to configure DNS on bastion host, %s", err)
            return  
        
        exit_code , err = bastion_setup_manager.configure_haproxy()
        if exit_code != 0:          
            logger.error("Failed to configure HAProxy on bastion host, %s", err)
            return 
        
        exit_code , err = bastion_setup_manager.configure_http_server()
        if exit_code != 0:
            logger.error("Failed to configure HTTP server on bastion host, %s", err)
            return
        
        logger.debug("Successfully configured bastion host for cluster installation")


        exit_code , err = asset_generator.download_openshift_installer(config['cluster']['version'], bastion_client)
        if exit_code != 0:
            logger.error("Failed to download OpenShift installer, %s", err)
            return
        exit_code , err = asset_generator.send_manifests_to_bastion(config['cluster']['name'], bastion_client)
        if exit_code != 0:
            logger.error("Failed to send manifests to bastion host, %s", err)
            return

        logger.info("Starting the asset generation by running openshift-install command on bastion host")
        exit_code, err = asset_generator.run_openshift_install(bastion_client, config['cluster']['name'], config['cluster']['version'])
        if exit_code != 0:
            logger.error("Failed to run OpenShift Installer to generate boot artifacts, %s", err)
            return
        logger.debug("Successfully ran openshift-install command on bastion host to generate boot artifacts")

        exit_code, err = asset_generator.copy_rootfs_to_webserver_path(f"{bastion_client.run('echo $HOME')[1].strip()}/{config['cluster']['name']}/boot-artifacts/agent.s390x-rootfs.img", bastion_client)
        if exit_code != 0:
            logger.error("Failed to copy rootfs image to webserver path on bastion host, %s", err)
            return
        logger.debug("Successfully copied rootfs image to webserver path on bastion host")


        hmc=HMCClient(config['infra']['hmc_host'], config['hmc_username'], config['hmc_password'])
        exit_code, err = hmc.connect()
        if exit_code != 0:
            logger.error("Failed to connect to HMC, %s", err)
            return  
        logger.debug("Successfully connected to HMC")
        try:
            logger.debug("Starting the param file generation for each control plane node")
            exit_code, err = generate_param_files(config,'control_nodes',hmc,bastion_client)
            if exit_code != 0:
                logger.error("Failed to generate param files for control plane nodes, %s", err)
                return
            logger.debug("Successfully generated param files for control plane nodes")
            if len(config['infra']['partitions']['compute_nodes']) > 0:
                logger.debug("Starting the param file generation for each compute node")
                exit_code, err = generate_param_files(config,'compute_nodes',hmc,bastion_client)
                if exit_code != 0:
                    logger.error("Failed to generate param files for compute nodes, %s", err)
                    return
                logger.debug("Successfully generated param files for compute nodes")
            else:
                logger.debug("No compute nodes defined in configuration, skipping param file generation for compute nodes")
        finally:    
            hmc.disconnect()
            logger.debug("Disconnected from HMC")


        exit_code, err = bastion_client.prepare_ftp_structure(f"{bastion_client.run('echo $HOME')[1].strip()}/{config['cluster']['name']}")  
        if exit_code != 0:
            logger.error("Failed to prepare FTP structure on bastion host, %s", err)
            return
        logger.debug("Successfully prepared FTP structure on bastion host for cluster installation")

        ftp_connector = FtpConnector(bastion_client, config['ftp']['host'], config['ftp_username'], config['ftp_password'])
        exit_code, err = ftp_connector.send_dir_to_ftp(f"{bastion_client.run('echo $HOME')[1].strip()}/{config['cluster']['name']}/{config['cluster']['name']}-ftp", f"{config['cluster']['name']}")     
        if exit_code != 0:
            logger.error("Failed to send FTP directory to FTP server, %s", err)
            return
        logger.debug("Successfully sent FTP directory file to FTP server")


        exit_code, err = boot_manager.node_boot_orchestrator(config)
        if exit_code != 0:
            logger.error("Failed to boot nodes, %s", err)
            return
        logger.debug("Successfully booted all nodes")

        exit_code, err = boot_manager.wait_for_installation_completion(bastion_client, config['cluster']['name'])
        if exit_code != 0:
            logger.error("Error while waiting for installation completion, %s", err)
            return
        logger.debug("Cluster installation completed successfully")

        exit_code, err = post_install_runner.post_install_runner(bastion_client, config['cluster']['name'])
        if exit_code != 0:
            logger.error("Error while running post installation tasks, %s", err)
            return
        logger.debug("Post installation tasks completed successfully")
        logger.debug("Openshift cluster installation completed successfully, you can now access the cluster using oc from the bastion host")

    finally:
        logger.debug("Closing SSH connection to bastion host")
        bastion_client.close()

        # Logging the end time and total execution time
        end_time = time.time()
        end_timestamp = datetime.now()
        elapsed = end_time - start_time
        mins, secs = divmod(elapsed, 60)
        logger.debug(f"Total execution time: {int(mins)} min {int(secs)} sec")


    logger.debug(f"Installation finished at: {end_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    return
    

def generate_param_files(config,node_type,hmc,bastion_client):
    if node_type == "control_nodes":
        node_partitions = config['infra']['partitions']['control_nodes']
        node_ips = config['infra']['ip']['control_nodes']
        hostname_prefix = "control"
    elif node_type == "compute_nodes":
        node_partitions = config['infra']['partitions']['compute_nodes']
        node_ips = config['infra']['ip']['compute_nodes']
        hostname_prefix = "compute"
    else:
        logger.error("Invalid node type specified for param file generation: %s", node_type)
        return 1, f"Invalid node type specified: {node_type}"
    for i in range(len(node_partitions)):
        node_config = {
            "cluster_name": config['cluster']['name'],
            "base_domain": config['cluster']['base_domain'],
            "disk_type": config['infra']['disk_type'],
            "network_type": config['infra']['network_type'],
            "ip": node_ips[i],
            "gateway": config['gateway'],
            "hostname": f"{hostname_prefix}-{i}.{config['cluster']['name']}.{config['cluster']['base_domain']}",
            "bastion_ip": config['bastion']['ip'],
        }
        console = hmc.client.consoles.console

        partitions = console.list_permitted_partitions()
        partition = [x for x in partitions if x.properties.get("name") == node_partitions[i]][0]

       
        dpm_partition = DpmPartition(node_partitions[i] , config['infra']['disk_type'], config['infra']['network_type'],partition)
        
        param_generator = ParamFileGenerator(dpm_partition, node_config)
        exit_code, err = param_generator.generate_param_file(hostname_prefix + f"-{i}")
        if exit_code != 0:
            logger.error("Failed to generate param file for partition %s, %s", node_partitions[i], err)
            return 1, f"Failed to generate param file for partition {node_partitions[i]}: {err}"
        logger.debug("Successfully generated param file for partition %s", node_partitions[i])

        exit_code, err = param_generator.send_param_file(bastion_client, hostname_prefix + f"-{i}")
        if exit_code != 0:
            logger.error("Failed to send param file for partition %s to bastion host, %s", node_partitions[i], err)
            return 1, f"Failed to send param file for partition {node_partitions[i]} to bastion host: {err}"
        logger.debug("Successfully sent param file for partition %s to bastion host", node_partitions[i])

        # delete the param file locally after sending to bastion host , no backup needed
        os.remove(BASE_DIR / config['cluster']['name'] / f"{hostname_prefix}-{i}.param")

    return 0, ""