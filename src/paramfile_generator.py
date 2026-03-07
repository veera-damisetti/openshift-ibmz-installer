# class to prepare param files for each nodes , by taking dpm parition object as input and cluster configuration as input 

import logging
logger = logging.getLogger("ocp_ibmz_install")
import  cmd.common.template_renderer as template_renderer
from pathlib import Path
import cmd.common.helpers as helpers
from src.dpm_partition import DpmPartition

'''
node_config = {
    "cluster_name": "test-cluster",
    "base_domain": "example.com",
    "disk_type": "fcp",
    "network_type": "sriov",
    ip: "",
    gateway: "",
    hostname: "",
    disk_info: {},
    network_info: "",
    bastion_ip: "",
}
'''
class ParamFileGenerator:
    def __init__(self, dpm_partition, node_config):
        self.dpm_partition = dpm_partition
        self.node_config = node_config

    def get_storage_and_network_info(self):
        # logic to get the storage and network information from the dpm partition object based on the cluster configuration
        storage_info = self.dpm_partition.get_disk_ids(self.node_config['disk_type'])
        if not storage_info:
            logger.error("Failed to retrieve storage information for DPM partition %s", self.dpm_partition.name)
            return None
        network_info = self.dpm_partition.get_network_info(self.node_config['network_type'])  
        if not network_info:
            logger.error("Failed to retrieve network information for DPM partition %s", self.dpm_partition.name)
            return None
        return storage_info, network_info

    def generate_param_file(self,filename):
        # logic to generate param file for each node based on the partition object and cluster configuration
        storage_info, network_info = self.get_storage_and_network_info()
        if not storage_info or not network_info:
            logger.error("Failed to retrieve network information for DPM partition %s", self.dpm_partition.name)
            return 1, "Failed to retrieve storage or network information"
        self.node_config['disk_info'] = storage_info
        self.node_config['network_info'] = network_info
        cluster_dir = helpers.get_basepath() / self.node_config['cluster_name']
        exit_code, err = template_renderer.render_template(
                template_name="paramfiles/paramfile.param.template",
                output_path= cluster_dir / f"{filename}.param",
                config=self.node_config,
            )
        if exit_code != 0:
            logger.error("Unable to render the param file from template , %s",err)
            return 1, err
        logger.debug("Param file generated successfully for node %s at %s", self.dpm_partition.name, cluster_dir / f"{self.dpm_partition.name}_param.yaml")
        return 0, ""
        
        
    def send_param_file(self,remote_host,filename):
        # logic to send the param file to the respective node using scp or any other method
        cluster_dir = helpers.get_basepath() / self.node_config['cluster_name']
        remote_home = remote_host.run("echo $HOME")[1].strip()
        remote_path = f"{remote_home}/{self.node_config['cluster_name']}/{filename}.param"
        exit_code, err = remote_host.send_file(cluster_dir / f"{filename}.param", remote_path)
        if exit_code != 0:
            logger.error("Failed to send param file for node %s to bastion host, %s", self.dpm_partition.name, err)
            return 1, f"Failed to send param file for node {self.dpm_partition.name} to bastion host: {err}"    
        logger.debug("Param file for node %s sent successfully to bastion host %s", self.dpm_partition.name, self.node_config['bastion_ip'])
        return 0, ""    