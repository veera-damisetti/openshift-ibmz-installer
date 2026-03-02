import logging
import zhmcclient
logger = logging.getLogger("ocp_ibmz_install")

class DpmPartition():
    def __init__(self, name, disk_type, network_type):  
        self.name = name
        self.disk_type = disk_type
        self.network_type = network_type
    
    def get_status(self,partition):
        logger.debug("Getting status of DPM partition %s",self.name)
        try:
            return partition.get_property('status')
        except zhmcclient.Error as e:
            logger.error("Error retrieving status for DPM partition %s: %s", self.name, str(e))
            return None
    
    def update_properties(self,partition, ftp_host, ftp_username, ftp_password, ftp_insfile):
        logger.debug("Updating boot properties for DPM partition %s.", self.name)
        boot_params = {
        'boot-device': 'ftp',
        'boot-ftp-host': ftp_host,
        'boot-ftp-username': ftp_username,
        'boot-ftp-password': ftp_password,
        'boot-ftp-insfile': ftp_insfile,
        }
        try:
            partition.update_properties(boot_params)
        except zhmcclient.Error as e:
            logger.error("Error updating boot properties for DPM partition %s: %s", self.name, str(e))
            return
        logger.debug("Boot properties updated for DPM partition %s.", self.name)
    
    def start (self,partition):
        logger.debug("Starting DPM partition %s.", self.name)
        if self.get_status(partition) == 'active':
            logger.debug("DPM partition %s is already active.", self.name)
            logger.debug("Stopping DPM partition %s before starting it again.", self.name)
            self.stop(partition)
        partition.start(wait_for_completion=True)

    def stop(self,partition):
        if self.get_status(partition) != 'stopped':
            logger.debug("Stopping DPM partition %s.",self.name)
            try:
                partition.stop(wait_for_completion=True)
                logger.debug("DPM partition %s stopped successfully.",self.name)
            except zhmcclient.Error as e:
                logger.error("Error stopping DPM partition %s: %s", self.name, str(e))
        logger.debug("DPM partition %s is already stopped.",self.name)
        
    def get_disk_ids(self,partition,disk_type):
        if disk_type == "fcp":
            disk_details = {"disk_id": "", "wwpn": "", "lun": ""}
            try:
                logger.debug("Retrieving attached storage groups for partition %s.", self.name)
                storage_groups = partition.list_attached_storage_groups(full_properties=True)
            except zhmcclient.Error as e:
                logger.error("Error retrieving attached storage groups for partition %s: %s", self.name, str(e))
                return
            if not storage_groups:
                logger.error("No storage groups attached to partition %s.", self.name)
                return
            
            logger.debug("Looking for storage group of type %s for partition %s.", disk_type, self.name)
            for sg in storage_groups:
                if sg.get_property("type") == disk_type and sg.get_property("shared") == False:
                    logger.debug("Found storage group %s of type %s for partition %s.", sg.name, disk_type, self.name)
                    sv_list=sg.storage_volumes.list(full_properties=True)
                    if len(sv_list) == 0:
                        logger.error("No storage volumes found in storage group %s for partition %s.", sg.name, self.name)
                        return
                    logger.debug("Retrieving disk details from storage group %s for partition %s.", sg.name, self.name)
                    disk_details["disk_id"] = sv_list[0].properties["paths"][0]['device-number']
                    disk_details["wwpn"] = sv_list[0].properties["paths"][0]['target-world-wide-port-name']
                    disk_details["lun"]= sv_list[0].properties["paths"][0]['logical-unit-number']
                    logger.debug("Retrieved disk details from the storage volume %s in storage group %s for partition %s", sg.name, sg.name, self.name)
                    return disk_details
        elif disk_type == "dasd":
            logger.warning("DASD disk type is currently not supported")
            return 
        logger.error("Disk not available with specified disk type %s for partition %s.", disk_type, self.name)
        return
    
    def get_cpc(self,partition):
        logger.debug("Getting CPC for partition %s.", self.name)  
        try:
            return partition.manager.parent.name
        except zhmcclient.Error as e:
            logger.error("Error retrieving CPC for partition %s: %s", self.name, str(e))
            return None
    
    def get_network_card(self,partition, network_type):
        logger.debug("Getting network card of type %s for DPM partition %s.", network_type, self.name) 
        try:
            logger.debug("Getting NICs for partition %s.", self.name)
            nics = partition.nics.list(full_properties=True)
        except zhmcclient.Error as e:
            logger.error("Error retrieving network cards for partition %s: %s", self.name, str(e))
            return None
        if not nics:
            logger.error("No NICs defined for this partition %s.", self.name)
            
        found_networkcard = False
        for i, nic in enumerate(nics, 1):
            nic_type = nic.get_property("type")
            if network_type == "osa":
                if nic_type in ["osa","osd"]:
                    found_networkcard = True
                    logger.debug("Found network card of type %s for partition %s.", nic_type, self.name)
                    return str(nic.get_property("device-number"))
            if network_type == "roce":
                if nic_type == "roce":
                    found_networkcard = True
                    return str(nic.get_property("device-number"))
                
        if not found_networkcard:
            logger.error("No suitable network card found for partition %s with network type %s.", self.name, network_type)
            return None
        
    def get_mac_address(self,partition, network_type, network_card):
        if network_type == "roce":
            logger.error("Can't get MAC address from HMC for RoCE network card for DPM partitions")
            return None
        
        logger.debug("Getting MAC address for network card of type %s for DPM partition %s.", network_type, self.name) 
        try:
            logger.debug("Getting NICs for partition %s.", self.name)
            nics = partition.nics.list(full_properties=True)
        except zhmcclient.Error as e:
            logger.error("Error retrieving network cards for partition %s: %s", self.name, str(e))
            return None
        if not nics:
            logger.error("No NICs defined for this partition %s.", self.name)

        for i, nic in enumerate(nics, 1):
            nic_id = nic.get_property("device-number")
            if nic_id == network_card:
                try:
                    return nic.get_property("mac-address")
                except zhmcclient.Error as e:
                    logger.error("Error retrieving MAC address for network card %s on partition %s: %s", network_card, self.name, str(e))
                    return None      
                
        logger.error("No network card with device number %s found for partition %s.", network_card, self.name)
        return None
    
    def get_partition_info(self,partition):
        logger.debug("Getting partition information for DPM partition %s.", self.name)
        partition.pull_full_properties()
        partition_info = {}
        logger.debug("Retrieving cpu and memory details for partition %s.", self.name)
        try:
            partition_info['cp_procs']= partition.get_property("cp-processors")
            partition_info['ifl_procs'] = partition.get_property("ifl-processors")
            partition_info['initial_memory'] = partition.get_property("initial-memory")
            partition_info['max_mem'] = partition.get_property("maximum-memory")
            partition_info['reserved_memory'] = partition.get_property("reserved-memory")
        except zhmcclient.Error as e:
            logger.error("Error retrieving cpu and memory information for DPM partition %s: %s", self.name, str(e))
            return None
        return partition_info
        







