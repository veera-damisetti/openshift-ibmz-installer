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
        logger.info("Connected to bastion host ")
    except Exception as e:
        logger.error("Failed to connect to bastion host %s", str(e))
        return
    command = "mkdir" + config['cluster']['name']

    remote_host.run(command,sudo=True)
    return

def configure_dns(config: dict):
    logger.debug("Starting the configuration of DNS on bastion")
    remote_host = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])
    try:
        remote_host.connect()
        logger.info("Connected to bastion host ")
    except Exception as e:
        logger.error("Failed to connect to bastion host %s", str(e))
        return
    logger.debug("Installing named ( bind ) on bastion ")
    exit_code, out, err = remote_host.run("yum install -y bind", sudo=True)
    if exit_code != 0:
        logger.error("Failed to install bind: %s", err)
        remote_host.close()
        return
    logger.info("named installed successfully")
    clusters_dir = helpers.get_basepath() / config['cluster']['name']

    files = ["named.conf.template","forward.zone.template"]
    destinations = ["named.conf", config['cluster']['name']+config['cluster']['base_domain']+".zone"]
    for i in range(len(files)):
        try:
            template_renderer.render_template(
                    template_name="dns/"+files[i],
                    output_path=Path(clusters_dir / destinations[i]),
                    config=config,
            )
        except Exception as e:
            logger.error("Unabled to render the %s from template , %s",files[i],str(e))
            return
    
    files = destinations.copy()
    destinations = ["/etc/named.conf","/var/named/"+config['cluster']['name']+"."+config['cluster']['base_domain']+".zone"]
    
    for i in range(len(destinations)):
        try:
            remote_host.send_file(Path(clusters_dir / files[i]),destinations[i])
        except Exception as e:
            logger.error("Error in sending %s configuration file to bastion host",destinations[i])
            raise e
        
    try:
        remote_host.run("systemctl restart named", sudo=True)
    except Exception as e:
        logger.error("Unable to start named.service %s",str(e))
        raise e
    logger.info("Successfully configured DNS")
    remote_host.close()
    return 

    

    

def configure_haproxy(config: dict ):

    logger.debug("Starting the configuration of haproxy on bastion")
    remote_host = RemoteHost(config['bastion']['ip'],config['bastion_username'],config['bastion_password'])

    try:
        remote_host.connect()
        logger.info("Connected to bastion host ")
    except Exception as e:
        logger.error("Failed to connect to bastion host %s", str(e))
        return
    logger.info("Installing HAProxy on bastion host")
    exit_code, out, err = remote_host.run("yum install -y haproxy", sudo=True)
    if exit_code != 0:
        logger.error("Failed to install HAProxy: %s", err)
        remote_host.close()
        return
    logger.info("HAProxy installed successfully")

    clusters_dir = helpers.get_basepath() / config['cluster']['name']
    try:
        template_renderer.render_template(
                template_name="haproxy/haproxy.cfg.template",
                output_path=Path(clusters_dir / "haproxy.cfg"),
                config=config,
        )
    except Exception as e:
        logger.error("Unabled to render the haproxy.cfg from template , %s",str(e))
        return 

    try:
        remote_host.send_file(Path(clusters_dir / "haproxy.cfg"),"/etc/haproxy/haproxy.cfg")
    except Exception as e:
        logger.error("Error in sending haproxy configuration file to bastion host")
        raise e
    remote_host.run("setsebool -P haproxy_connect_any 1",sudo=True)
    try:
        remote_host.run("systemctl enable haproxy", sudo=True)
        remote_host.run("systemctl restart haproxy", sudo=True)
    except Exception as e:
        logger.error("Unable to start haproxy %s",str(e))
        raise e
    
    logger.info("Successfully Configured HAProxy on bastion")
    remote_host.close()

    return

    



