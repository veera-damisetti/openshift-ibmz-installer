import cmd.common.helpers as helpers
import logging
logger = logging.getLogger("ocp_ibmz_install")
import cmd.common.input_reader as reader
import cmd.common.helpers as helpers

class ConfigValidator:
    def __init__(self, config):
        self.config = config
        self.errors = []

    def validate(self):
        cluster = self.config.get("cluster", {})
        infra = self.config.get("infra", {})
        bastion = self.config.get("bastion", {})
        ftp = self.config.get("ftp", {})

        all_ips = []

       # Cluster validations
        name = cluster.get("name")
        if not name:
            self.errors.append("cluster.name is required")
        elif name != name.lower():
            self.errors.append("cluster.name must contain only lowercase letters")

        base_domain = cluster.get("base_domain")
        if not base_domain:
            self.errors.append("cluster.base_domain is required")
        else:
            if base_domain != base_domain.lower():
                self.errors.append("cluster.base_domain must be lowercase")

            result = reader.validate_base_domain(base_domain)
            if result is not True:
                self.errors.append(f"cluster.base_domain invalid: {result}")

        version = cluster.get("version")
        if not version:
            self.errors.append("cluster.version is required")
        else:
            valid_versions = reader.fetch_valid_ocp_versions()
            if valid_versions and version not in valid_versions:
                self.errors.append(f"cluster.version '{version}' is not valid")

        # Infra validations
        hmc_host = infra.get("hmc_host")
        if not hmc_host:
            self.errors.append("infra.hmc_host is required")

        if not infra.get("disk_type"):
            self.errors.append("infra.disk_type is required")

        if not infra.get("network_type"):
            self.errors.append("infra.network_type is required")

        partitions = infra.get("partitions", {})
        ip_cfg = infra.get("ip", {})

        control_partitions = partitions.get("control_nodes", [])
        compute_partitions = partitions.get("compute_nodes", [])

        control_ips = ip_cfg.get("control_nodes", [])
        compute_ips = ip_cfg.get("compute_nodes", [])

        # control node count rule
        if len(control_partitions) not in (1, 3):
            self.errors.append("control_nodes must contain either 1 or 3 partitions")

        if len(control_partitions) != len(control_ips):
            self.errors.append(
                "control_nodes partition count must equal control_nodes ip count"
            )

        # Compute node rules
        if compute_partitions or compute_ips:
            if len(control_partitions) == 1:
                self.errors.append(
                    "compute nodes are not allowed when control_nodes count is 1"
                )

            if len(compute_partitions) != len(compute_ips):
                self.errors.append(
                    "compute_nodes partition count must equal compute_nodes ip count"
                )

        # IP Validation
        for ip in control_ips:
            if not helpers.ipv4_validator(ip):
                self.errors.append(f"Invalid control node IP: {ip}")
            else:
                all_ips.append(ip)

        for ip in compute_ips:
            if not helpers.ipv4_validator(ip):
                self.errors.append(f"Invalid compute node IP: {ip}")
            else:
                all_ips.append(ip)

        bastion_ip = bastion.get("ip")
        if not bastion_ip:
            self.errors.append("bastion.ip is required")
        elif not helpers.ipv4_validator(bastion_ip):
            self.errors.append("bastion.ip must be a valid IPv4")
        else:
            all_ips.append(bastion_ip)

        ftp_host = ftp.get("host")
        if not ftp_host:
            self.errors.append("ftp.host is required")
        elif not helpers.ipv4_validator(ftp_host):
            self.errors.append("ftp.host must be a valid IPv4")

        # Duplicate IP rule
        if len(all_ips) != len(set(all_ips)):
            self.errors.append("Duplicate IPs found across control, compute, and bastion nodes")

        # Subnet consistency rule
        if all_ips:
            first_two = ".".join(all_ips[0].split(".")[:2])

            for ip in all_ips:
                if ".".join(ip.split(".")[:2]) != first_two:
                    self.errors.append(
                        "All control, compute, and bastion IPs must be in the same network (first two octets must match)"
                    )
                    break

        return len(self.errors) == 0, self.errors