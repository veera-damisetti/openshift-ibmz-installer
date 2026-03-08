import logging
logger = logging.getLogger("ocp_ibmz_install")


def post_install_runner(bastion_client, cluster_name):
    logger.debug("Starting post-installation tasks")
    
    
    logger.debug("Post-installation tasks completed successfully")