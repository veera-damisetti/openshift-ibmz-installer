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
        logger.debug("Connecting to remote host %s@%s:%d", self.username, self.host, self.port)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False
        )

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
            "Sending the file to %s@%s:%s",
            self.username,
            self.host,
            remote_path,
        )

        sftp = self.client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()

