# A class to boot DPM LPARs, taking partition dpm_parition object as input and ftp creds also 

import logging
logger = logging.getLogger("ocp_ibmz_install")

class BootManager():
    def __init__(self, hmc_client, dpm_partition, ftp_server_ip, ftp_username, ftp_password, cluster_name,node_name):
        self.hmc_client = hmc_client
        self.ftp_server_ip = ftp_server_ip
        self.ftp_username = ftp_username
        self.ftp_password = ftp_password
        self.dpm_partition = dpm_partition
        self.cluster_name = cluster_name
        self.node_name = node_name

    def boot_partition(self):
        # Logic to boot the partition using HMC client and FTP credentials

        exit_code, err =  self.dpm_partition.update_properties(self.ftp_server_ip, self.ftp_username, self.ftp_password, f"{self.cluster_name}/{self.node_name}/generic.ins")
        if exit_code != 0:
            logger.error("Failed to update boot properties for partition %s, %s", self.dpm_partition.name, err)
            return 1, f"Failed to update boot properties for partition {self.dpm_partition.name}: {err}"
        
        exit_code, err = self.dpm_partition.start()
        if exit_code != 0:
            logger.error("Failed to start partition %s, %s", self.dpm_partition.name, err)
            return 1, f"Failed to start partition {self.dpm_partition.name}: {err}"

        return 0, ""
    
    