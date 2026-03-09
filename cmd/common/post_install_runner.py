import logging
logger = logging.getLogger("ocp_ibmz_install")
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box


def post_install_runner(bastion_client, cluster_name):
    logger.debug("Starting post-installation tasks")
    cluster_dir = f"$HOME/{cluster_name}"
    
    logger.debug("Retrieving kubeadmin password from cluster directory")
    cmd = f"cat {cluster_dir}/auth/kubeadmin-password"
    exit_code, password, err = bastion_client.run(cmd)
    if exit_code != 0:
        logger.error("Failed to read kubeadmin password, %s", err)
        return exit_code, err
    password = password.strip()
    logger.debug("Successfully retrieved kubeadmin password from cluster directory")

    logger.debug("Retrieving API URL from kubeconfig")
    cmd = f"grep 'server:' {cluster_dir}/auth/kubeconfig | awk '{{print $2}}'"
    exit_code, api_url, err = bastion_client.run(cmd)
    if exit_code != 0:
        logger.error("Failed to read API URL from kubeconfig, %s", err)
        return exit_code, err
    logger.debug("Successfully retrieved API URL from kubeconfig")
    api_url = api_url.strip()

    logger.debug("Constructing OpenShift console URL from API URL")
    console_url = api_url.replace("https://api.", "https://console-openshift-console.apps.")
    login_command = f"oc login {api_url} -u kubeadmin -p {password}"
    logger.debug("Constructed OpenShift console URL and login command successfully")
    logger.info(("Reporting cluster access details for the Openshift cluster. You can use these details to access the cluster using oc CLI or OpenShift web console"))
    
    display_cluster_access_details(password, api_url, console_url, login_command)
    
    logger.debug("Moving kubeconfig to $HOME/.kube/config on bastion host")
    command = f"mkdir -p $HOME/.kube && cp $HOME/{cluster_name}/auth/kubeconfig $HOME/.kube/config"
    exit_code, _, err = bastion_client.run(command)
    if exit_code != 0:
        logger.error("Failed to copy kubeconfig, %s", err)
        return exit_code, err
    
    logger.debug("Kubeconfig copied successfully to $HOME/.kube/config on bastion host")
    logger.debug("You can now access the cluster using oc from the bastion host")
    logger.info("Post-installation tasks completed successfully")
    logger.info("Successfully installed OpenShift cluster, Please use the above details to access your cluster using oc CLI or OpenShift web console.")
    return 0, ""


def display_cluster_access_details(password, api_url, console_url, login_command):
    console = Console()

    table = Table(box=None, show_header=False)
    table.add_column("Key", style="bold cyan", width=12)
    table.add_column("Value", style="bold white")

    table.add_row("API URL", api_url)
    table.add_row("Username", "kubeadmin")
    table.add_row("Password", password)
    table.add_row("Console URL", console_url)
    table.add_row("Login Command", login_command)

    panel = Panel(
        table,
        title="[bold white]OpenShift Cluster Access Details[/bold white]",
        border_style="bold red",
        box=box.DOUBLE,
        padding=(1, 3)
    )
    console.print(panel)
