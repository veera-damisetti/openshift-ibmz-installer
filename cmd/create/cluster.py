import logging
import sys
import urllib3
from pathlib import Path
import cmd.common.helpers as helpers
import cmd.common.input_reader as reader
import cmd.common.configure_bastion as bastion
from src.remote_connection import RemoteHost
import cmd.common.asset_generator as asset_generator
from src.hmc import HMCClient
from src.paramfile_generator import ParamFileGenerator  
from src.dpm_partition import DpmPartition


logger = logging.getLogger("ocp_ibmz_install")
urllib3.disable_warnings()

BASE_DIR = helpers.get_basepath()
CONFIG_FILE = BASE_DIR / "inputs.yaml"

def cluster():
    logger.debug("Looking for input configuration file at %s", CONFIG_FILE)
    
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

    logger.debug("Getting gateway IP from bastion host")
    bastion_client = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])
    bastion_client.connect()
    gateway=bastion_client.get_gateway()
    config['gateway']=gateway
    
    logger.debug("Starting the configuration of bastion host for cluster installation")
    
    exit_code , err = bastion.create_workdir(config) 
    if exit_code != 0:
        logger.error("Failed to create workdir on bastion host, %s", err)
        return
    
    #exit_code , err = bastion.configure_dns(config)
    if exit_code != 0:
        logger.error("Failed to configure DNS on bastion host, %s", err)
        return  
    
    #xit_code , err = bastion.configure_haproxy(config)
    if exit_code != 0:          
        logger.error("Failed to configure HAProxy on bastion host, %s", err)
        return 
    
    #exit_code , err = bastion.configure_http_server(config)
    if exit_code != 0:
        logger.error("Failed to configure HTTP server on bastion host, %s", err)
        return
    
    logger.debug("Successfully configured bastion host for cluster installation")


    #exit_code , err = asset_generator.download_openshift_installer(config['cluster']['version'], bastion_client)
    if exit_code != 0:
        logger.error("Failed to download OpenShift installer, %s", err)
        return
    #exit_code , err = asset_generator.send_manifests_to_bastion(config['cluster']['name'], bastion_client)
    if exit_code != 0:
        logger.error("Failed to send manifests to bastion host, %s", err)
        return

    logger.info("Starting the asset generation by running openshift-install command on bastion host")
    #exit_code, err = asset_generator.run_openshift_install(bastion_client, config['cluster']['name'], config['cluster']['version'])
    if exit_code != 0:
        logger.error("Failed to run OpenShift Installer to generate boot artifacts, %s", err)
        return
    logger.debug("Successfully ran openshift-install command on bastion host to generate boot artifacts")

    hmc=HMCClient(config['infra']['hmc_host'], config['hmc_username'], config['hmc_password'])
    exit_code, err = hmc.connect()
    if exit_code != 0:
        logger.error("Failed to connect to HMC, %s", err)
        return  
    logger.debug("Successfully connected to HMC")

    

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
            logger.error("Failed to generate param files for compute plane nodes, %s", err)
            return
        logger.debug("Successfully generated param files for compute plane nodes")
     
    
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

        #send to bastion host
        exit_code, err = param_generator.send_param_file(bastion_client, hostname_prefix + f"-{i}")
        if exit_code != 0:
            logger.error("Failed to send param file for partition %s to bastion host, %s", node_partitions[i], err)
            return 1, f"Failed to send param file for partition {node_partitions[i]} to bastion host: {err}"
        logger.debug("Successfully sent param file for partition %s to bastion host", node_partitions[i])   
    return 0, ""