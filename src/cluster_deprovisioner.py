import logging
logger = logging.getLogger("ocp_ibmz_install")
from src.hmc import HMCClient
from src.dpm_partition import DpmPartition

# FTP cleanup
    # Connect HMC and delete boot properties for all nodes
    # Connect to bastion and delete cluster directory in home
    # Delete all the services which we created on bastion , dns haproxy httpd and close the ports on firewall which we opened for haproxy and httpd and dns 


class ClusterDeprovisioner:
    def __init__(self, config):
        self.config = config

    def hmc_boot_configuration_reset(self):
        hmc=HMCClient(self.config['infra']['hmc_host'], self.config['hmc_username'], self.config['hmc_password'])
        exit_code, err = hmc.connect()
        if exit_code != 0:
            logger.error("Failed to connect to HMC, %s", err)
            return 1, f"Failed to connect to HMC: {err}"
        logger.debug("Successfully connected to HMC")

        # Logic to reset boot configuration for all nodes
        try:
            console = hmc.client.consoles.console
            partitions = console.list_permitted_partitions()
            logger.debug(f"Retrieved the list of partitions from HMC console")
            all_nodes = self.config['infra']['partitions']['control_nodes'] + self.config['infra']['partitions']['compute_nodes']
            for node in all_nodes:
                partition = [x for x in partitions if x.properties.get("name") == node][0]
                logger.debug(f"Resetting boot configuration for node : {node}")
                dpm_partition = DpmPartition(node, self.config['infra']['disk_type'], self.config['infra']['network_type'], partition)
                exit_code, err = dpm_partition.reset_boot_configuration()
                if exit_code != 0:
                    logger.error(f"Failed to reset boot configuration for node %s, %s", node, err)
                else:
                    logger.debug(f"Successfully reset boot configuration for node %s", node)
                
                dpm_partition.stop()
        finally:
            hmc.disconnect()
        return 0, ""
    
    def ftp_cleanup(self, bastion_client):
        # Logic to cleanup FTP structure on bastion
        command = f'lftp -u {self.config["ftp_username"]},{self.config["ftp_password"]} ftp://{self.config["ftp"]["host"]} -e "rm -rf {self.config["cluster"]["name"]}; exit"'
        exit_code, _, err = bastion_client.run(command)
        if exit_code != 0:
            logger.error("Failed to remove cluster artifacts from FTP server: %s", err)
            return 1, f"Failed to remove cluster artifacts from FTP server: {err}"
        logger.debug("Successfully removed all the cluster artifacts from FTP server")
        return 0, ""
                
    def bastion_cleanup(self, bastion_client):
        services = ['named', 'haproxy', 'httpd']
        files = [
            "/etc/httpd/conf/httpd.conf", 
            "/etc/haproxy/haproxy.cfg", 
            "/etc/named.conf",
            "/var/www/html/rootfs.img"
            "/var/named/{cluster_name}.{base_domain}.zone".format(cluster_name=self.config['cluster']['name'], base_domain=self.config['cluster']['base_domain']),
            "{home_dir}/{cluster_name}".format(home_dir=bastion_client.run('echo $HOME')[1].strip(), cluster_name=self.config['cluster']['name'])
        ]

        for service in services:
            logger.debug(f"Removing service {service} from bastion host")
            exit_code, _, err = bastion_client.run(f"yum remove -y {service}", sudo=True)
            if exit_code != 0:
                logger.error(f"Failed to remove service {service}: %s", err)
                return 1, f"Failed to remove service {service}: {err}"
            else:   
                logger.debug(f"Successfully removed service {service}") 
            
        for file in files:
            logger.debug(f"Removing file {file} from bastion host")
            exit_code, _,err = bastion_client.run(f"rm -rf {file}", sudo=True)
            if exit_code != 0:
                logger.error(f"Failed to remove file {file}: %s", err)
                return 1, f"Failed to remove file {file}: {err}"
            else:
                logger.debug(f"Successfully removed file {file}")

        return 0, ""


        