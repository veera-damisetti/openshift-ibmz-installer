import logging
logger = logging.getLogger("ocp_ibmz_install")
from src.remote_connection import RemoteHost
from src.hmc import HMCClient

class AuthenticationValidator:
    def __init__(self, config):
        self.config = config

    def _connect_bastion(self):
        logger.debug("Connecting to bastion host %s", self.config['bastion']['ip'])
        bastion_client = RemoteHost(
                host=self.config['bastion']['ip'],
                username=self.config['bastion_username'],
                password=self.config['bastion_password']
            )
        exit_code, err = bastion_client.connect()
        if exit_code != 0:
            return None, f"Failed to connect to bastion host: {err}"
        logger.debug("Successfully connected to bastion host")
        return bastion_client, ""


    def valid_ssh_credentials(self):
        logger.debug("Validating SSH authentication to bastion host")
        
        bastion_client, err = self._connect_bastion()
        if bastion_client is None:
            return False
        bastion_client.close()
        return True
    
    def valid_hmc_credentials(self):
        logger.debug("Validating authentication to HMC host %s", self.config['infra']['hmc_host'])
        hmc_client = HMCClient(
                host=self.config['infra']['hmc_host'],
                username=self.config['hmc_username'],
                password=self.config['hmc_password']
            )
        exit_code, err = hmc_client.connect()
        if exit_code != 0:
            return False
        hmc_client.disconnect()
        return True
    
    def valid_ftp_credentials(self):
        logger.debug("Validating FTP authentication to bastion host")
        bastion_client, err = self._connect_bastion()
        if bastion_client is None:
            logger.error("SSH authentication validation failed for bastion host, %s", err)
            return False
        
        logger.debug("Checking if lftp is installed on bastion host")
        exit_code, out, err = bastion_client.run("rpm -q lftp")
        if exit_code != 0:
            logger.debug("lftp not found, installing it")
            exit_code, out, err = bastion_client.run("yum install -y lftp", sudo=True)
            if exit_code != 0:
                logger.error("Failed to install lftp: %s", err)
                return 1, f"Failed to install lftp: {err}"
        logger.debug("lftp installed successfully")
        
        command = f'lftp -u {self.config["ftp_username"]},{self.config["ftp_password"]} ftp://{self.config["ftp"]["host"]} -e  "ls; exit"'
        exit_code, std_out ,err = bastion_client.run(command)
        if exit_code != 0:
            return False
        bastion_client.close()
        return True