import logging
from click import command
logger = logging.getLogger("ocp_ibmz_install")
from src.remote_connection import RemoteHost
import cmd.common.helpers as helpers
import  cmd.common.template_renderer as template_renderer
from pathlib import Path
from src.remote_connection import RemoteHost

class BastionSetupManager:
    def __init__(self, bastion_client: RemoteHost, config: dict):
        self.bastion_client = bastion_client
        self.config = config

    def create_workdir(self):
        if not self.bastion_client: 
            logger.error("SSH client is not connected")
            return 1, "SSH client is not connected"
        command = "mkdir -p " + "$HOME/" + self.config['cluster']['name']
        exit_code, out, err = self.bastion_client.run(command,sudo=True)
        if exit_code != 0:
            logger.error("Failed to create workdir on bastion host, %s", err)
            return 1 , err
        return 0, ""

    def configure_dns(self):
        if not self.bastion_client:
            logger.error("SSH client is not connected")
            return 1, "SSH client is not connected"
        
        logger.debug("Installing named ( bind ) on bastion ")
        exit_code, out, err = self.bastion_client.run("yum install -y bind", sudo=True)
        if exit_code != 0:
            logger.error("Failed to install bind: %s", err)
            return 1 , err
        logger.debug("named installed successfully on bastion")
        clusters_dir = helpers.get_basepath() / self.config['cluster']['name']

        files = ["named.conf.template","forward.zone.template"]
        destinations = ["named.conf", self.config['cluster']['name']+self.config['cluster']['base_domain']+".zone"]
        for i in range(len(files)):
            exit_code, err = template_renderer.render_template(
                        template_name="dns/"+files[i],
                        output_path=Path(clusters_dir / destinations[i]),
                        config=self.config,
                )
            if exit_code != 0:
                logger.error("Unabled to render the %s from template , %s",files[i],err)
                return 1, err
        
        files = destinations.copy()
        destinations = ["/etc/named.conf","/var/named/"+self.config['cluster']['name']+"."+self.config['cluster']['base_domain']+".zone"]
        
        for i in range(len(destinations)):
                exit_code, err = self.bastion_client.send_file(Path(clusters_dir / files[i]),destinations[i])
                if exit_code != 0:
                    logger.error("Error in sending %s to bastion host, %s",files[i],err)
                    return 1 , err
        logger.debug("DNS configuration files sent to bastion host successfully")
            
        exit_code, out ,err = self.bastion_client.run("systemctl restart named", sudo=True)
        if exit_code != 0:
            logger.error("Unable to start named.service %s",err)
            return 1, err
        logger.debug("Successfully configured DNS")
        if self.open_port_firewalld("53","udp")[0] != 0:    
            logger.error("Error while opening port 53 for DNS on bastion") 
            return 1, "Failed to open port 53 for DNS on bastion"
        
        logger.debug("Updating resolv.conf on bastion host to use local named server for name resolution")
        cmd = f"grep -q '^nameserver {self.config['bastion']['ip']}' /etc/resolv.conf || sudo sed -i '1inameserver {self.config['bastion']['ip']}' /etc/resolv.conf"
        exit_code, out, err = self.bastion_client.run(cmd, sudo=True)   
        if exit_code != 0:
            logger.error("Failed to update /etc/resolv.conf: %s", err)
            return 1, err
        logger.debug("Added bastion IP as nameserver in /etc/resolv.conf")
        return 0 , ""
    


    def configure_haproxy(self):
        if not self.bastion_client:
            logger.error("SSH client is not connected")
            return 1, "SSH client is not connected" 
        logger.debug("Installing HAProxy on bastion host")
        exit_code, out, err = self.bastion_client.run("yum install -y haproxy", sudo=True)
        if exit_code != 0:
            logger.error("Failed to install HAProxy: %s", err)
            return 1 , str(err)
        logger.debug("HAProxy installed successfully")

        clusters_dir = helpers.get_basepath() / self.config['cluster']['name']
    
        exit_code, err = template_renderer.render_template(
                template_name="haproxy/haproxy.cfg.template",
                output_path=Path(clusters_dir / "haproxy.cfg"),
                config=self.config,
        )
        if exit_code != 0:
            logger.error("Unabled to render the haproxy.cfg from template , %s",err)
            return 1 , err

        exit_code, err = self.bastion_client.send_file(Path(clusters_dir / "haproxy.cfg"),"/etc/haproxy/haproxy.cfg")
        if exit_code != 0:
            logger.error("Error in sending haproxy configuration file to bastion host, %s", err)
            return 1 , err
        self.bastion_client.run("setsebool -P haproxy_connect_any 1",sudo=True)
        exit_code, out, err = self.bastion_client.run("systemctl enable haproxy ; systemctl restart haproxy", sudo=True)
        if exit_code != 0:
            logger.error("Unable to start haproxy %s",str(err))
            return 1 , str(err)
        
        logger.debug("Opening required ports for HAProxy on bastion host")
        ports=['80','443','6443','22623']
        for port in ports:
            if self.open_port_firewalld(port,"tcp")[0]!= 0:    
                logger.error("Error while opening port %s for haproxy on bastion",port) 
                return 1, "Failed to open port {}".format(port)
            
        return 0, ""

    def configure_http_server(self):
        if not self.bastion_client:
            logger.error("SSH client is not connected")
            return 1, "SSH client is not connected"
        commands = [
            "sudo yum install -y httpd",
            "sudo sed -i 's/^Listen[[:space:]]\+80$/Listen 8080/' /etc/httpd/conf/httpd.conf",
            "sudo systemctl enable httpd",
            "sudo systemctl restart httpd"
        ]
        for i in range(len(commands)):
            exit_code, out, err = self.bastion_client.run(commands[i],sudo=True)
            if exit_code !=0: 
                logger.error("Error while configuring httpd server on bastion")
                return 1, "Failed to configure httpd server on bastion"
            
        if self.open_port_firewalld("8080","tcp")[0] != 0:
            logger.error("Error while opening port 8080 for httpd server on bastion")
            return 1, "Failed to open port 8080 for httpd server on bastion"
        return 0, ""
    
    def ensure_firewalld(self):
        """
        Ensure firewalld is installed and running on the remote host.
        Installs and starts it if required.
        """
        if not self.bastion_client:
            logger.error("SSH client is not connected")
            return 1, "SSH client is not connected"

        logger.debug("Ensuring firewalld is installed and running on the remote host")

        # Check if firewalld exists
        exit_code, out, err = self.bastion_client.run("rpm -q firewalld")
        if exit_code != 0:
            logger.debug("firewalld not installed, installing it")
            exit_code, out, err = self.bastion_client.run("yum install -y firewalld", sudo=True)
            if exit_code != 0:
                logger.error("Failed to install firewalld: %s", err)
                return 1, "Failed to install firewalld"

        logger.debug("Checking if firewalld is running")

        exit_code, out, err = self.bastion_client.run("systemctl is-active firewalld")
        if exit_code != 0:
            logger.debug("firewalld not running, enabling and starting it")
            exit_code, out, err = self.bastion_client.run(
                "systemctl enable --now firewalld", sudo=True
            )
            if exit_code != 0:
                logger.error("Failed to start firewalld: %s", err)
                return 1, "Failed to start firewalld"

        logger.debug("firewalld is installed and running")
        return 0, ""
    
    def open_port_firewalld(self,port,protocol,zone="public"):
        if self.ensure_firewalld()[0]!= 0:
            logger.error("Unexpected error while ensuring firewalld is running on the remote host")
            return 1, "Failed to ensure firewalld is running"
        command = f"firewall-cmd --permanent --zone={zone} --add-port={port}/{protocol}"
        exit_code ,  out, err = self.bastion_client.run(command,sudo=True)
        if exit_code != 0 : 
            logger.error("Failed to open port %s/%s: %s",port,protocol,err)
            return 1, "Failed to open port {}/{}".format(port, protocol)
        exit_code, out, err = self.bastion_client.run("firewall-cmd --reload",sudo=True)
        if exit_code != 0:
            logger.error("Failed to reload firewalld: %s", err)
            return 1, "Failed to reload firewalld"
        logger.debug("Successfully opened port %s/%s in firewalld",port,protocol)
        return 0 , ""
    