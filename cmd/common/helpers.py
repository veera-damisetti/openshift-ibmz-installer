import ipaddress 
import subprocess
from pathlib import Path
import logging
logger = logging.getLogger("ocp_ibmz_install")

def get_cidr(ip_list):
    """
    Takes a list of IP strings and returns the smallest CIDR 
    that contains all of them.
    """
    if not ip_list:
        return None
    
    # Convert strings to IP objects and find the bounds
    ips = sorted([ipaddress.IPv4Address(ip) for ip in ip_list])
    min_ip = int(ips[0])
    max_ip = int(ips[-1])
    
    # Find the first bit where the min and max differ
    # XOR shows the differing bits
    diff = min_ip ^ max_ip
    
    # The length of the common prefix is 32 minus the position 
    # of the most significant bit that differs
    if diff == 0:
        prefix_len = 32
    else:
        prefix_len = 32 - diff.bit_length()
    
    network = ipaddress.IPv4Network((ips[0], prefix_len), strict=False)
    return str(network)

def generate_ssh_keypair(key_name: str = "ocp-ibmz-install", ssh_dir: str = "~/.ssh"):
    """
    Check if ssh key is available, and generates if not available 
    returns the public key as string
    """
    
    try:
        ssh_dir_path = Path(ssh_dir).expanduser()
        ssh_dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured SSH directory exists: %s", ssh_dir_path)
    except Exception as e:
        logger.error("Failed to create SSH directory %s: %s", ssh_dir, e)
        raise

    key_path = ssh_dir_path / key_name
    pub_key_path = key_path.with_suffix(".pub")

    if not key_path.exists() or not pub_key_path.exists():
        logger.debug("SSH key pair not found. Generating new key pair: %s", key_path)
        try:
            subprocess.run(
                ["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(key_path), "-N", ""],
                check=True
            )
            logger.debug("Generated new SSH key pair: %s and %s", key_path, pub_key_path)
        except Exception as e:
            logger.error("Unexpected error while generating SSH key pair: %s", e)
            raise
    else:
        logger.debug("SSH key pair already exists: %s and %s", key_path, pub_key_path)

    try:
        with open(pub_key_path, "r") as f:
            pub_key = f.read().strip()
            logger.debug("Reading the public key  %s", pub_key_path)
            return pub_key
    except FileNotFoundError:
        logger.error("Public key file not found: %s", pub_key_path)
        raise
    except Exception as e:
        logger.error("Error reading public key %s: %s", pub_key_path, e)
        raise
