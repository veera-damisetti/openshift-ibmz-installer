# Class to connect and dosconnect to hmc , take creds as inputs host,user,pass and return the session object to interact with hmc
import zhmcclient
from cmd.common import helpers
import logging  
logger = logging.getLogger("ocp_ibmz_install")

class HMCClient():
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.session = None
        self.client = None

    def connect(self):
        logger.debug("Connecting to HMC at %s", self.host)
        try:
            self.session = zhmcclient.Session(self.host, self.username, self.password, verify_cert=False)
            self.client = zhmcclient.Client(self.session)
            logger.debug("Successfully connected to HMC at %s", self.host)
        except zhmcclient.Error as e:
            logger.error("Failed to connect to HMC at %s: %s", self.host, str(e))
            return 1, str(e)
        return 0, ""
    
    def disconnect(self):
        if self.session:
            logger.debug("Disconnecting from HMC at %s", self.host)
            try:
                self.session.logout()
                logger.debug("Successfully disconnected from HMC at %s", self.host)
            except zhmcclient.Error as e:
                logger.error("Failed to disconnect from HMC at %s: %s", self.host, str(e))
                return 1, str(e)
        return 0, ""
    


'''
session = zhmcclient.Session(
        config['hmc']['host'], config['hmc']['username'], config['hmc']['password'], verify_cert=False)
    client = zhmcclient.Client(session)
    console = client.consoles.console

    node=DpmPartition(config['cluster']['partitions'][0], config['cluster']['disk_type'], config['cluster']['network_type']) 
    
    partitions = console.list_permitted_partitions()
    partition = [x for x in partitions if x.properties.get("name") == config['cluster']['partitions'][0]][0]
'''