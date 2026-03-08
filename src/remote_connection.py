import os
import paramiko
import logging
logger = logging.getLogger("ocp_ibmz_install")
class RemoteHost:
    def __init__(self, host, username, password, port=22, timeout=10):
        self.host = host
        self.username = username
        self.password = password    
        self.port = port
        self.timeout = timeout
        self.client = None

    def connect(self):
        logger.debug("Connecting to remote host %s@host:%d", self.username, self.port)
        try:
            client = paramiko.SSHClient()
            logger.debug("SSH client created successfully for host")
        except Exception as e:
            logger.error("Failed to create SSH client: %s", str(e))
            raise
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            logger.debug("Attempting to connect to %s@host:%d", self.username, self.port)
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False
            )
            logger.debug("Successfully connected to %s@host:%d", self.username, self.port)
        except Exception as e:
            logger.error("Failed to connect to %s@host:%d: %s", self.username, self.port, str(e))
            raise

        self.client = client

    def run(self, command, sudo=False):
        if sudo:
            command = f"sudo -S -p '' {command}"

        stdin, stdout, stderr = self.client.exec_command(command)
        if sudo:
            stdin.write(self.password + "\n")
            stdin.flush()

        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode()
        err = stderr.read().decode()

        return exit_code, out, err

    def close(self):
        if self.client:
            self.client.close()
    
    def send_file(self, local_path, remote_path):
        if not self.client:
            return 1 , "SSH client is not connected"

        logger.debug(
            "Sending the file to %s@host:%s",
            self.username,
            remote_path,
        )

        sftp = self.client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()
        
        return 0, ""

    def get_gateway(self):
        """
        Fetch the default gateway from the remote host using `ip route`.
        Returns the gateway IP as a string.
        """
        if not self.client:
            logger.error("SSH client is not connected")
            return None

        exit_code, out, err = self.run("ip route")

        if exit_code != 0:
            logger.error("Failed to fetch routing table: %s", err)
            return None
        

        for line in out.splitlines():
            if line.startswith("default via"):
                parts = line.split()
                gateway = parts[2]
                logger.debug("Default gateway retrieved successfully")
                return gateway

        logger.error("Default gateway not found in routing table")
        return None
    

    def prepare_ftp_structure(self, base_dir):
        """
        Creates FTP directory structure based on .param files and
        deletes the original .param files after copying.

        If base_dir = /root/veera/mycluster

        Structure created:
            /root/veera/mycluster/mycluster-ftp/
        """

        if not self.client:
            return 1, "SSH client is not connected"

        cluster_name = os.path.basename(base_dir.rstrip("/"))
        ftp_dir = f"{base_dir}/{cluster_name}-ftp"

        logger.debug("Preparing FTP directory structure in %s", ftp_dir)

        # Find .param files
        exit_code, out, err = self.run(f"ls {base_dir}/*.param")

        if exit_code != 0:
            logger.error("Failed to list .param files: %s", err)
            return 1, "No param files found"

        param_files = [p.strip() for p in out.splitlines() if p.strip()]

        if not param_files:
            logger.error("No .param files found in %s", base_dir)
            return 1, "No param files found"

        # Create clustername-ftp directory
        exit_code, _, err = self.run(f"mkdir -p {ftp_dir}")
        if exit_code != 0:
            logger.error("Failed to create ftp directory: %s", err)
            return 1, "FTP directory creation failed"

        for param_path in param_files:

            param_name = param_path.split("/")[-1].replace(".param", "")
            node_dir = f"{ftp_dir}/{param_name}"
            images_dir = f"{node_dir}/images"

            logger.debug("Creating FTP boot structure for %s", param_name)

            exit_code, _, err = self.run(f"mkdir -p {images_dir}")
            if exit_code != 0:
                logger.error("Failed creating directories for %s: %s", param_name, err)
                return 1, f"Directory creation failed for {param_name}"

            exit_code, _, err = self.run(
                f"cp {base_dir}/boot-artifacts/agent.s390x-generic.ins {node_dir}/generic.ins"
            )
            if exit_code != 0:
                logger.error("Failed copying generic.ins for %s: %s", param_name, err)
                return 1, "generic.ins copy failed"

            exit_code, _, err = self.run(
                f"sed -i 's|images/pxeboot/|images/|g' {node_dir}/generic.ins"
            )
            if exit_code != 0:
                logger.error("Failed updating generic.ins paths for %s: %s", param_name, err)
                return 1, "Failed to update generic.ins paths"
            
            exit_code, _, err = self.run(
                f"sed -i 's|images/vmlinuz|images/agent.s390x-vmlinuz|g' {node_dir}/generic.ins"
            )
            if exit_code != 0:
                logger.error("Failed updating vmlinuz path for %s: %s", param_name, err)
                return 1, "Failed to update vmlinuz path"

            exit_code, _, err = self.run(
                f"cp {param_path} {images_dir}/genericdvd.prm"
            )
            if exit_code != 0:
                logger.error("Failed copying param file for %s: %s", param_name, err)
                return 1, "Failed to copy param file"

            exit_code, _, err = self.run(f"rm -f {param_path}")
            if exit_code != 0:
                logger.error("Failed deleting original param file %s: %s", param_path, err)
                return 1, "Failed to delete original param file"

            artifacts = [
                "agent.s390x-initrd.addrsize",
                "agent.s390x-initrd.img",
                "agent.s390x-vmlinuz",
            ]

            for artifact in artifacts:
                exit_code, _, err = self.run(
                    f"cp {base_dir}/boot-artifacts/{artifact} {images_dir}/"
                )
                if exit_code != 0:
                    logger.error(
                        "Failed copying %s for %s: %s",
                        artifact,
                        param_name,
                        err
                    )
                    return 1, f"Failed to copy artifact: {artifact}"

        logger.debug("FTP directory structure created successfully at %s", ftp_dir)

        return 0, f"FTP structure ready at {ftp_dir}"
    