import logging
from logging import config
import time
logger = logging.getLogger("ocp_ibmz_install")
from src.dpm_partition import DpmPartition
from src.hmc import HMCClient
from src.boot_manager import BootManager


#function to handle booting part for all nodes, in parallel using threadpoolexecutor, takes config as input and uses the details under infra section to connect to HMC and boot the nodes using BootManager class

def node_boot_orchestrator(config):
    hmc=HMCClient(config['infra']['hmc_host'], config['hmc_username'], config['hmc_password'])
    exit_code, err = hmc.connect()
    if exit_code != 0:
        logger.error("Failed to connect to HMC, %s", err)
        return 1, f"Failed to connect to HMC: {err}"
    logger.debug("Successfully connected to HMC")
    try:
        logger.debug("Starting the boot procedure for all nodes")
        control_nodes = config['infra']['partitions']['control_nodes']
        compute_nodes = config['infra']['partitions']['compute_nodes']
        node_types = ['control']
        if len(compute_nodes) > 0:
            node_types.append('compute')
        else:
            logger.debug("No compute nodes defined in configuration, skipping boot procedure for compute nodes")
        
        console = hmc.client.consoles.console
        partitions = console.list_permitted_partitions()
        logger.debug(f"Retrieved the list of partitions from HMC console")

        for node_type in node_types:
            logger.info(f"Starting the boot procedure for {node_type} nodes")
            nodes = config['infra']['partitions'][f"{node_type}_nodes"]
            for i in range(len(nodes)):
                
                partition = [x for x in partitions if x.properties.get("name") == nodes[i]][0]
                logger.info(f"Booting {node_type} node : {node_type}-{i} : {nodes[i]}")

                dpm_partition = DpmPartition(nodes[i], config['infra']['disk_type'], config['infra']['network_type'], partition)

                boot_manager = BootManager(hmc, dpm_partition, config['ftp']['host'], config['ftp_username'], config['ftp_password'], config['cluster']['name'], f"{node_type}-{i}")

                exit_code, err = boot_manager.boot_partition()
                if exit_code != 0:  
                    logger.error(f"Failed to boot {node_type} node {nodes[i]}, {err}")
                    return 1, f"Failed to boot {node_type} node {nodes[i]}: {err}"
                logger.info(f"Successfully booted {node_type} node {nodes[i]}")
            logger.info(f"Completed the boot procedure for {node_type} nodes")

        logger.info("Successfully completed the boot procedure for all nodes")
    finally:
        hmc.disconnect()
    return 0, ""

def wait_for_installation_completion(bastion_client, cluster_name: str):
    log_level = "info"
    if logger.isEnabledFor(logging.DEBUG):
        log_level = "debug"
        logger.debug("Debug logging enabled, setting OpenShift installer log level to debug")

    command = f"cd $HOME/{cluster_name} && stdbuf -oL -eL openshift-install agent wait-for install-complete --dir . --log-level {log_level}"
    
    stdin, stdout, stderr = bastion_client.client.exec_command(command)
    channel = stdout.channel

    while True:
        if channel.recv_ready():
            data = channel.recv(4096).decode()
            print(data, end="", flush=True)

        if channel.recv_stderr_ready():
            err = channel.recv_stderr(4096).decode()
            print(err, end="", flush=True)

        if channel.exit_status_ready():
            break

        time.sleep(0.1)

    return channel.recv_exit_status(), ""