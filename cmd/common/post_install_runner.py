import logging
logger = logging.getLogger("ocp_ibmz_install")


def post_install_runner(bastion_client, cluster_name):
    logger.debug("Starting post-installation tasks")

    # move kubeconfig from cluster_dir/auth/kueconfig to $HOME/.kube/config on bastion host
    logger.debug("Moving kubeconfig to $HOME/.kube/config on bastion host")
    command = f"mkdir -p $HOME/.kube && cp $HOME/{cluster_name}/auth/kubeconfig $HOME/.kube/config"
    exit_code, err = bastion_client.run(command)
    if exit_code != 0:
        logger.error("Failed to copy kubeconfig, %s", err)
        return exit_code, err
    
    logger.debug("Kubeconfig copied successfully to $HOME/.kube/config on bastion host")
    logger.debug("You can now access the cluster using oc from the bastion host")
    logger.debug("Post-installation tasks completed successfully")
    return 0, ""