#a class to send tar file from bastion to ftp erver iusing lftp and untar there 

import logging
logger = logging.getLogger("ocp_ibmz_install")

class FtpConnector:
    def __init__(self, bastion_client, ftp_server_ip, ftp_username, ftp_password):
        self.bastion_client = bastion_client
        self.ftp_server_ip = ftp_server_ip
        self.ftp_username = ftp_username
        self.ftp_password = ftp_password

    def send_dir_to_ftp(self, local_dir, remote_dir):
        logger.debug("Checking if lftp is installed on bastion host")
        exit_code, out, err = self.bastion_client.run("rpm -q lftp")
        if exit_code != 0:
            logger.debug("lftp not found, installing it")
            exit_code, out, err = self.bastion_client.run("yum install -y lftp", sudo=True)
            if exit_code != 0:
                logger.error("Failed to install lftp: %s", err)
                return 1, f"Failed to install lftp: {err}"
        logger.debug("lftp installed successfully")
        command = f'lftp -u {self.ftp_username},{self.ftp_password} ftp://{self.ftp_server_ip} -e "mirror -R {local_dir} {remote_dir}; exit"'
        exit_code, out, err = self.bastion_client.run(command)
        if exit_code != 0:
            logger.error("Failed to send directory to FTP server: %s", err)
            return 1, f"Failed to send directory to FTP server: {err}"
        logger.debug("Directory sent to FTP server successfully")
        return 0, ""