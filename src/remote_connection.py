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
            raise RuntimeError("SSH client is not connected")

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

    def get_gateway(self):
        """
        Fetch the default gateway from the remote host using `ip route`.
        Returns the gateway IP as a string.
        """
        if not self.client:
            raise RuntimeError("SSH client is not connected")

        exit_code, out, err = self.run("ip route")

        if exit_code != 0:
            logger.error("Failed to fetch routing table: %s", err)
            raise RuntimeError("Unable to determine gateway")

        for line in out.splitlines():
            if line.startswith("default via"):
                parts = line.split()
                gateway = parts[2]
                logger.debug("Default gateway retrieved successfully")
                return gateway

        raise RuntimeError("Default gateway not found in routing table")
    

