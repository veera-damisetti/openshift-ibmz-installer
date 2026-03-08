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
        return  
    logger.debug("Successfully connected to HMC")

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
        logger.debug(f"Starting the boot procedure for {node_type} nodes")
        nodes = config['infra']['partitions'][f"{node_type}_nodes"]
        for i in range(len(nodes)):
            
            partition = [x for x in partitions if x.properties.get("name") == nodes[i]][0]
            logger.debug(f"Booting {node_type} node : {node_type}-{i} : {nodes[i]}")

            dpm_partition = DpmPartition(nodes[i], config['infra']['disk_type'], config['infra']['network_type'], partition)

            boot_manager = BootManager(hmc, dpm_partition, config['ftp']['host'], config['ftp_username'], config['ftp_password'], config['cluster']['name'], f"{node_type}-{i}")

            exit_code, err = boot_manager.boot_partition()
            if exit_code != 0:  
                logger.error(f"Failed to boot {node_type} node %s, %s", nodes[i], err)
                return 1, f"Failed to boot {node_type} node {nodes[i]}: {err}"
            logger.debug("Successfully booted {node_type} node %s", nodes[i])
        logger.debug("Completed the boot procedure for {node_type} nodes")

    logger.debug("Successfully completed the boot procedure for all nodes")
    hmc.disconnect()
    logger.debug("Disconnected from HMC")
    return 0, ""

# Function to wait for the installation to complete by runing opeshift install command 
# openshift-install agent wait-for install-complete --dir=<path to cluster dir> --log-level=debug and checking the output for completion status, takes config as input to get the path to cluster dir and also uses the bastion host to run the command remotely, returns 0 if installation is complete, 1 if there is an error or installation failed, and 2 if installation is still in progress after a certain timeout period.
'''
def install_oc_client(version: str, bastion: RemoteHost):
    oc_client_url = f"https://mirror.openshift.com/pub/openshift-v4/s390x/clients/ocp/{version}/openshift-client-linux.tar.gz"
    command = f"curl -L {oc_client_url} -o /tmp/openshift-client.tar.gz"
    exit_code, out, err = bastion.run(command)
    if exit_code != 0:
        logger.error("Failed to download OpenShift client: %s", err)
        return 1, f"Failed to download OpenShift client: {err}"  
    command = "tar -xzf /tmp/openshift-client.tar.gz -C /usr/local/bin/ oc kubectl --no-same-owner"
    exit_code, out, err = bastion.run(command)
    if exit_code != 0:
        logger.error("Failed to extract OpenShift client: %s", err)
        return 1, f"Failed to extract OpenShift client: {err}"
    
    logger.debug("OpenShift client downloaded and extracted successfully")

    command = "rm /tmp/openshift-client.tar.gz"
    exit_code, out, err = bastion.run(command)
    if exit_code != 0:
        logger.error("Failed to remove OpenShift client tar file: %s", err)
        return 1, f"Failed to remove OpenShift client tar file: {err}"
    logger.debug("OpenShift client tar file removed successfully")

    return 0, ""

# Function to run the openshift-install command on bastion host and stream the logs to terminal in real time

def run_openshift_install(bastion: RemoteHost, cluster_name: str,version: str):
    exit_code, err = install_oc_client(version, bastion)
    if exit_code != 0:
        logger.error("Failed to install OpenShift client on bastion host, %s", err)
        return 1, err

    # install nmstate on bastion using yum 
    exit_code, out, err = bastion.run("yum install -y nmstate", sudo=True)
    if exit_code != 0:
        logger.error("Failed to install nmstate on bastion host, %s", err)
        return 1, err

    log_level = "info"
    if logger.isEnabledFor(logging.DEBUG):
        log_level = "debug"
        logger.debug("Debug logging enabled, setting OpenShift installer log level to debug")
    
    command = f"cd $HOME/{cluster_name} && stdbuf -oL -eL openshift-install agent create pxe-files --dir . --log-level {log_level}"

    stdin, stdout, stderr = bastion.client.exec_command(command)
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
'''

# same for bootstrap completion 
# openshift-install agent wait-for bootstrap-complete --log-level=debug --dir=$HOME/$CLUSTER_NAME/ # Monitor bootstrap process
def wait_for_bootstrap_completion(bastion_client, cluster_name: str):
    log_level = "info"
    if logger.isEnabledFor(logging.DEBUG):
        log_level = "debug"
        logger.debug("Debug logging enabled, setting OpenShift installer log level to debug")
        
    command = f"cd $HOME/{cluster_name} && stdbuf -oL -eL openshift-install agent wait-for bootstrap-complete --dir . --log-level {log_level}"
    stdin, stdout, stderr = bastion_client.client.exec_command(command)
    channel = stdout.channel

    while True:
        if channel.recv_ready():
            data = channel.recv(4096).decode()
            print(data, end="", flush=True)
            if "Bootstrap complete" in data:
                logger.debug("Bootstrap completed successfully")
                return 0
            if "Error" in data or "Failed" in data:
                logger.error("Bootstrap failed with error: %s", data)
                return 1

        if channel.recv_stderr_ready():
            err = channel.recv_stderr(4096).decode()
            print(err, end="", flush=True)
            logger.error("Bootstrap failed with error: %s", err)
            return 1

        if channel.exit_status_ready():
            break

        time.sleep(0.1)

    logger.error("Bootstrap process exited unexpectedly")
    return 1

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
            if "Install complete" in data:
                logger.debug("Installation completed successfully")
                return 0
            if "Error" in data or "Failed" in data:
                logger.error("Installation failed with error: %s", data)
                return 1

        if channel.recv_stderr_ready():
            err = channel.recv_stderr(4096).decode()
            print(err, end="", flush=True)
            logger.error("Installation failed with error: %s", err)
            return 1

        if channel.exit_status_ready():
            break

        time.sleep(0.1)

    logger.error("Installation process exited unexpectedly")
    return 1