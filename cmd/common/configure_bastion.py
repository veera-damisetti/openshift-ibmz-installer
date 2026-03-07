import logging
logger = logging.getLogger("ocp_ibmz_install")
from src.remote_connection import RemoteHost
import cmd.common.helpers as helpers
import  cmd.common.template_renderer as template_renderer
from pathlib import Path

def create_workdir(config: dict): 
    remote_host = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])
    try:
        remote_host.connect()
        logger.debug("Connected to bastion host successfully")
    except Exception as e:
        logger.error("Failed to connect to bastion host %s", str(e))
        return 1 , str(e)
    command = "mkdir -p " + "$HOME/" + config['cluster']['name']

    exit_code, out, err = remote_host.run(command,sudo=True)
    if exit_code != 0:
        logger.error("Failed to create workdir on bastion host, %s", err)
        remote_host.close()
        return 1 , err
    return 0, ""

def configure_dns(config: dict):
    logger.debug("Starting the configuration of DNS on bastion")
    remote_host = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])
    try:
        remote_host.connect()
        logger.debug("Connected to bastion host successfully")
    except Exception as e:
        logger.error("Failed to connect to bastion host %s", str(e))
        remote_host.close()
        return 1 , str(e)
    
    logger.debug("Installing named ( bind ) on bastion ")
    exit_code, out, err = remote_host.run("yum install -y bind", sudo=True)
    if exit_code != 0:
        logger.error("Failed to install bind: %s", err)
        remote_host.close()
        return 1 , err
    logger.debug("named installed successfully on bastion")
    clusters_dir = helpers.get_basepath() / config['cluster']['name']

    files = ["named.conf.template","forward.zone.template"]
    destinations = ["named.conf", config['cluster']['name']+config['cluster']['base_domain']+".zone"]
    for i in range(len(files)):
        exit_code, err = template_renderer.render_template(
                    template_name="dns/"+files[i],
                    output_path=Path(clusters_dir / destinations[i]),
                    config=config,
            )
        if exit_code != 0:
            logger.error("Unabled to render the %s from template , %s",files[i],err)
            remote_host.close()
            return 1, err
    
    files = destinations.copy()
    destinations = ["/etc/named.conf","/var/named/"+config['cluster']['name']+"."+config['cluster']['base_domain']+".zone"]
    
    for i in range(len(destinations)):
            exit_code, err = remote_host.send_file(Path(clusters_dir / files[i]),destinations[i])
            if exit_code != 0:
                logger.error("Error in sending %s to bastion host, %s",files[i],err)
                remote_host.close()
                return 1 , err
    logger.debug("DNS configuration files sent to bastion host successfully")
        
    exit_code, out ,err = remote_host.run("systemctl restart named", sudo=True)
    if exit_code != 0:
        logger.error("Unable to start named.service %s",err)
        remote_host.close()
        return 1, err
    logger.debug("Successfully configured DNS")
    if open_port_firewalld(remote_host,"53","udp")[0] != 0:    
        logger.error("Error while opening port 53 for DNS on bastion") 
        remote_host.close()
        return 1, "Failed to open port 53 for DNS on bastion"
    remote_host.close()
    return 0 , ""

def configure_haproxy(config: dict ):
    logger.debug("Starting the configuration of haproxy on bastion")
    remote_host = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])

    try:
        remote_host.connect()
        logger.debug("Connected to bastion host ")
    except Exception as e:
        logger.error("Failed to connect to bastion host %s", str(e))
        return 1, str(e)
    logger.debug("Installing HAProxy on bastion host")
    exit_code, out, err = remote_host.run("yum install -y haproxy", sudo=True)
    if exit_code != 0:
        logger.error("Failed to install HAProxy: %s", err)
        remote_host.close()
        return 1 , str(err)
    logger.debug("HAProxy installed successfully")

    clusters_dir = helpers.get_basepath() / config['cluster']['name']
   
    exit_code, err = template_renderer.render_template(
            template_name="haproxy/haproxy.cfg.template",
            output_path=Path(clusters_dir / "haproxy.cfg"),
            config=config,
    )
    if exit_code != 0:
        logger.error("Unabled to render the haproxy.cfg from template , %s",err)
        return 1 , err

    exit_code, err = remote_host.send_file(Path(clusters_dir / "haproxy.cfg"),"/etc/haproxy/haproxy.cfg")
    if exit_code != 0:
        logger.error("Error in sending haproxy configuration file to bastion host, %s", err)
        remote_host.close()
        return 1 , err
    remote_host.run("setsebool -P haproxy_connect_any 1",sudo=True)
    try:
        remote_host.run("systemctl enable haproxy", sudo=True)
        remote_host.run("systemctl restart haproxy", sudo=True)
    except Exception as e:
        logger.error("Unable to start haproxy %s",str(e))
        remote_host.close()
        return 1 , str(e)
    
    logger.debug("Successfully Configured HAProxy on bastion")
    ports=['80','443','6443','22623']
    for port in ports:
        if open_port_firewalld(remote_host,port,"tcp")[0]!= 0:    
            logger.error("Error while opening port %s for haproxy on bastion",port) 
            remote_host.close()
            return 1, "Failed to open port {}".format(port)
    remote_host.close()
    return 0 , ""

def configure_http_server(config: dict):
    """
    Install and configure Apache HTTP server to listen on port 8080.
    """
    remote_host = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])
    remote_host.connect()

    commands = [
        "sudo yum install -y httpd",
        "sudo sed -i 's/^Listen 80 /Listen 8080/' /etc/httpd/conf/httpd.conf",
        "sudo systemctl enable httpd",
        "sudo systemctl restart httpd"
    ]
    for i in range(len(commands)):
        exit_code, out, err = remote_host.run(commands[i],sudo=True)
        if exit_code !=0: 
            logger.error("Error while configuring httpd server on bastion")
    
    if open_port_firewalld(remote_host,"8080","tcp")[0] != 0:
        logger.error("Error while opening port 8080 for httpd server on bastion")
    return 0, ""


def ensure_firewalld(client):
    """
    Ensure firewalld is installed and running on the remote host.
    Installs and starts it if required.
    """
    if not client:
        logger.error("SSH client is not connected")
        return 1, "SSH client is not connected"

    logger.debug("Ensuring firewalld is installed and running on the remote host")

    # Check if firewalld exists
    exit_code, out, err = client.run("rpm -q firewalld")
    if exit_code != 0:
        logger.debug("firewalld not installed, installing it")
        exit_code, out, err = client.run("yum install -y firewalld", sudo=True)
        if exit_code != 0:
            logger.error("Failed to install firewalld: %s", err)
            return 1, "Failed to install firewalld"

    logger.debug("Checking if firewalld is running")

    exit_code, out, err = client.run("systemctl is-active firewalld")
    if exit_code != 0:
        logger.debug("firewalld not running, enabling and starting it")
        exit_code, out, err = client.run(
            "systemctl enable --now firewalld", sudo=True
        )
        if exit_code != 0:
            logger.error("Failed to start firewalld: %s", err)
            return 1, "Failed to start firewalld"

    logger.debug("firewalld is installed and running")
    return 0, ""

def open_port_firewalld(client,port,protocol,zone="public"):
    if ensure_firewalld(client)[0]!= 0:
        logger.error("Unexpected error while ensuring firewalld is running on the remote host")
        return 1, "Failed to ensure firewalld is running"
    command = f"firewall-cmd --permanent --zone={zone} --add-port={port}/{protocol}"
    exit_code ,  out, err = client.run(command,sudo=True)
    if exit_code != 0 : 
        logger.error("Failed to open port %s/%s: %s",port,protocol,err)
        return 1, "Failed to open port {}/{}".format(port, protocol)
    try:
        client.run("firewall-cmd --reload",sudo=True)
    except Exception as e:  
        logger.error("Failed to reload firewalld: %s", str(e))
        return 1, "Failed to reload firewalld"
    logger.debug("Successfully opened port %s/%s in firewalld",port,protocol)
    return 0 , ""



