from src.dpm_partition import DpmPartition
from pathlib import Path
import yaml
import zhmcclient
import logging
import urllib3
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "inputs.yaml"

def load_config(config_filepath):
    with open(config_filepath, encoding="utf-8") as f:
        return yaml.safe_load(f)

def generate_manifests():
    urllib3.disable_warnings()
    logger.info("Creating agent-config.yaml and install-config.yaml")
    config = load_config("inputs.yaml")

    session = zhmcclient.Session(
        config['hmc']['host'], config['hmc']['username'], config['hmc']['password'], verify_cert=False)
    client = zhmcclient.Client(session)
    console = client.consoles.console

    node=DpmPartition(config['cluster']['partitions'][0], config['cluster']['disk_type'], config['cluster']['network_type']) 
    
    partitions = console.list_permitted_partitions()
    partition = [x for x in partitions if x.properties.get("name") == config['cluster']['partitions'][0]][0]
    
    status = node.get_status(partition)

    nic=node.get_network_card(partition, config['cluster']['network_type'])
    disk=node.get_disk_ids(partition, config['cluster']['disk_type'])
    mac=node.get_mac_address(partition, config['cluster']['network_type'], node.get_network_card(partition, config['cluster']['network_type']))
    
    info=node.get_partition_info(partition)

    print("Partition Status: ", status)
    print("NIC: ", nic)
    print("Disk: ", disk)
    print("MAC Address: ", mac)
    print("Partition Info: ", info)