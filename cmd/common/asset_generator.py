import os

from src.remote_connection import RemoteHost
import cmd.common.helpers as helpers
import logging
from pathlib import Path
import time

logger = logging.getLogger("ocp_ibmz_install")

def download_openshift_installer(version: str,bastion: RemoteHost):

    openshift_release_url = f"https://mirror.openshift.com/pub/openshift-v4/s390x/clients/ocp/{version}/openshift-install-linux.tar.gz"
    command = f"curl -L {openshift_release_url} -o /tmp/openshift-install.tar.gz"
    exit_code, out, err = bastion.run(command)
    if exit_code != 0:
        logger.error("Failed to download OpenShift installer: %s", err)
        return 1, f"Failed to download OpenShift installer: {err}"  
    command = "tar -xzf /tmp/openshift-install.tar.gz -C /usr/local/bin/"
    exit_code, out, err = bastion.run(command)
    if exit_code != 0:
        logger.error("Failed to extract OpenShift installer: %s", err)
        return 1, f"Failed to extract OpenShift installer: {err}"
    
    logger.info("OpenShift installer downloaded and extracted successfully")

    command = "rm /tmp/openshift-install.tar.gz"
    exit_code, out, err = bastion.run(command)
    if exit_code != 0:
        logger.error("Failed to remove OpenShift installer tar file: %s", err)
        return 1, f"Failed to remove OpenShift installer tar file: {err}"
    logger.debug("OpenShift installer tar file removed successfully")

    return 0, ""

# Send the agent-config.yaml and install-config.yaml to bastion host for cluster installation
def send_manifests_to_bastion(cluster_name, bastion: RemoteHost):
    local_path = helpers.get_basepath() / cluster_name
    remote_home = bastion.run("echo $HOME")[1].strip()
    
    for file in ["agent-config.yaml", "install-config.yaml"]:
        local_file = local_path / file
        if not local_file.exists():
            logger.error("Required manifest %s not found at %s", file, local_file)
            return 1, f"Required manifest {file} not found at {local_file}"
        remote_path = f"{remote_home}/{cluster_name}/{file}"
        exit_code, err = bastion.send_file(local_file, remote_path)
        if exit_code != 0:
            logger.error("Error in sending %s to bastion host, %s", file, err)
            return 1, err
    
        logger.debug("Successfully sent %s to bastion host at %s", file, remote_path)
    return 0, ""
    
# Install OpenShift client on bastion host to run the openshift-install command for cluster installation and get the live logs to display on terminal

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

    # Take back up of agent-config.yaml file and install-config.yaml on bastion only as openshift-install command consumes it and we will miss them.
    # create a directory in cluster dir and move the files there as backup
    command = f"mkdir -p $HOME/{cluster_name}/post-install-artifacts && cp $HOME/{cluster_name}/agent-config.yaml $HOME/{cluster_name}/install-config.yaml $HOME/{cluster_name}/post-install-artifacts/"
    exit_code, out, err = bastion.run(command)
    if exit_code != 0:
        logger.error("Failed to back up manifest files on bastion host, %s", err)
        return 1, err
    logger.debug("Backed up manifest files successfully on bastion host")

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

# Function to copy the rootfs image to /var/www/html/ on bastion host to be used for cluster installation
def copy_rootfs_to_webserver_path( rootfs_path, bastion: RemoteHost) :
    command = "cp {} /var/www/html/rootfs.img".format(rootfs_path)
    command += " && chmod 644 /var/www/html/rootfs.img"
    exit_code, out, err = bastion.run(command, sudo=True)
    if exit_code != 0:
        logger.error("Failed to copy rootfs image to webserver path on bastion host, %s", err)
        return 1, f"Failed to copy rootfs image to webserver path on bastion host: {err}"
    logger.debug("Successfully copied rootfs image to webserver path on bastion host")
    return 0, ""


