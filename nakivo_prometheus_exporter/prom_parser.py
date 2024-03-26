#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of nakivo_prometheus_exporter

__appname__ = "nakivo_prometheus_exporter"
__author__ = "Orsiris de Jong"
__site__ = "https://www.netperfect.fr/nakivo_prometheus_exporter"
__description__ = "Naviko API Prometheus data exporter"
__copyright__ = "Copyright (C) 2024 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2024032601"


import sys
from argparse import ArgumentParser
from typing import Union
from ruamel.yaml import YAML
from pathlib import Path
from ofunctions.logger_utils import logger_get_logger
from nakivo_prometheus_exporter.nakivo_api import NakivoAPI

logger = logger_get_logger()


# Monkeypatching ruamel.yaml ordreddict so we get to use pseudo dot notations
# eg data.g('my.array.keys') == data['my']['array']['keys']
# and data.s('my.array.keys', 'new_value')
def g(self, path, sep=".", default=None, list_ok=False):
    """
    Getter for dot notation in an a dict/OrderedDict
    print(d.g('my.array.keys'))
    """
    return self.mlget(path.split(sep), default=default, list_ok=list_ok)


def load_config_file(config_file: Path) -> Union[bool, dict]:
    """
    Checks whether config file is valid
    """
    try:
        with open(config_file, "r", encoding="utf-8") as file_handle:
            yaml = YAML(typ="rt")
            full_config = yaml.load(file_handle)
            if not full_config:
                logger.critical("Config file seems empty !")
                return False
            return full_config
    except OSError:
        logger.critical(f"Cannot load configuration file from {config_file}")
        return False


def license_to_prometheus(license_data: dict, host: str):
    """
    Extract Nakivo license status from Job result
    """
    try:
        installed = 1 if license_data["data"]["installed"] else 0
    except KeyError:
        installed = 0
    try:
        client = license_data["data"]["client"]
    except KeyError:
        client = None
    try:
        vmcount = license_data["data"]["usedVms"]
    except KeyError:
        vmcount = 0
    try:
        sockets = license_data["data"]["usedSockets"]
    except KeyError:
        sockets = 0
    try:
        ec2 = license_data["data"]["usedEc2Instances"]
    except KeyError:
        ec2 = 0
    try:
        physical_servers = license_data["data"]["usedPhysicalServers"]
    except KeyError:
        physical_servers = 0
    try:
        physical_workstations = license_data["data"]["usedPhysicalWorkstations"]
    except KeyError:
        physical_workstations = 0
    try:
        o365users = license_data["data"]["usedOffice365Users"]
    except KeyError:
        o365users = 0
    try:
        oracledb = license_data["data"]["usedOracleDatabases"]
    except KeyError:
        oracledb = 0
    try:
        monitoredvm = license_data["data"]["usedMonitoredVms"]
    except KeyError:
        monitoredvm = 0
    try:
        expiration = round(
            license_data["data"]["expiresIn"] / 1000
        )  # milliseconds to seconds
    except KeyError:
        expiration = 0

    prom_data = f'# HELP nakivo_license_installed Is the Nakivo instance licensed\n\
# TYPE nakivo_license_installed gauge\n\
nakivo_license_installed{{host="{host}",client="{client}"}} {installed}\n\
# HELP nakivo_license_vmcount How many VMs do we backup\n\
# TYPE nakivo_license_vmcount gauge\n\
nakivo_license_vmcount{{host="{host}",client="{client}"}} {vmcount}\n\
# HELP nakivo_license_sockets How many VMs do we backup\n\
# TYPE nakivo_license_sockets gauge\n\
nakivo_license_sockets{{host="{host}",client="{client}"}} {sockets}\n\
# HELP nakivo_license_ec2count How many EC2 instances do we backup\n\
# TYPE nakivo_license_ec2count gauge\n\
nakivo_license_ec2count{{host="{host}",client="{client}"}} {ec2}\n\
# HELP nakivo_license_physicalservercount How many physical servers do we backup\n\
# TYPE nakivo_license_physicalservercount gauge\n\
nakivo_license_physicalservercount{{host="{host}",client="{client}"}} {physical_servers}\n\
# HELP nakivo_license_physicalworkstationcount How many physical workstations do we backup\n\
# TYPE nakivo_license_physicalworkstationcount gauge\n\
nakivo_license_physicalworkstationcount{{host="{host}",client="{client}"}} {physical_workstations}\n\
# HELP nakivo_license_o365count How many Office 365 users do we backup\n\
# TYPE nakivo_license_o365count gauge\n\
nakivo_license_o365count{{host="{host}",client="{client}"}} {o365users}\n\
# HELP nakivo_license_oraclecount How many oracle databases do we backup\n\
# TYPE nakivo_license_oraclecount gauge\n\
nakivo_license_oraclecount{{host="{host}",client="{client}"}} {oracledb}\n\
# HELP nakivo_license_monitoredvm How many vms are monitored\n\
# TYPE nakivo_license_monitoredvm gauge\n\
nakivo_license_monitoredvm{{host="{host}",client="{client}"}} {monitoredvm}\n\
# HELP nakivo_license_expiration When will the license expire (seconds)\n\
# TYPE nakivo_license_expiration gauge\n\
nakivo_license_expiration{{host="{host}",client="{client}"}} {expiration}\n'
    return prom_data


def get_vm_backup_result(job_result: dict, host: str, filter_active_only: bool = True):
    """
    Extract VM backup status from Nakvio Job result
    """
    vm_job_state = []
    prom_data = "# HELP nakivo_backup_state When will the license expire (seconds)\n\
# TYPE nakivo_backup_state gauge\n\
# HELP nakivo_backup_state Backup duration (seconds)\n\
# TYPE nakivo_backup_state gauge\n\
# HELP nakivo_backup_state Backup size (bytes)\n\
# TYPE nakivo_backup_state gauge\n"
    for job in job_result["data"]["children"]:
        if filter_active_only:
            if job["status"] in ("GRAY"):
                continue
        job_name = job["name"]
        for vm in job["objects"]:
            name = vm["sourceName"]
            state = vm["lrState"]
            if state in ("SUCCEEDED"):
                num_state = 0
            elif state in ("RUNNING", "DEMAND", "SCHEDULED", "WAITING"):
                num_state = 1
            else:
                num_state = 2
            prom_data += f'nakivo_backup_state{{host="{host}",object="{name}",job_name="{job_name}"}} {num_state}\n'
            duration = round(vm["lrDuration"] / 1000)  # milliseconds to seconds
            prom_data += f'nakivo_backup_duration{{host="{host}",object="{name}",job_name="{job_name}"}} {duration}\n'
            data_size = vm["lrDataTransferredUncompressed"]
            prom_data += f'nakivo_backup_size{{host="{host}",object="{name}",job_name="{job_name}"}} {data_size}\n'
    return prom_data


def get_nakivo_data(host_config):
    """
    Connects to Nakivo API and exports job data
    """
    try:
        host = host_config["host"]
        username = host_config["username"]
        password = host_config["password"]
        cert_verify = host_config["cert_verify"]
    except (AttributeError, ValueError, TypeError, KeyError):
        try:
            # pylint: disable=undefined-variable
            logger.error(f"Bogus host config for {host}")
        except NameError:
            logger.error("Bogus host config")
        return False

    api = NakivoAPI(host, username, password, cert_verify)
    if not api.authenticate():
        logger.error(f"Authentication failure for {host} as {username}")
        return False

    prom_data = ""
    try:
        license = api.get_license_info()
        if not license:
            logger.error(f"Cannot get license data for {host}")
            prom_data = f'nakivo_license_installed{{host="{host}"}} 0'
        else:
            prom_data = license_to_prometheus(license, host)
    except Exception as exc:
        logger.error(f"Cannot retrieve license data for {host}: {exc}")

    try:
        jobs = api.get_jobs()
        if not jobs:
            logger.error(f"Cannot get job info for {host}")
        else:
            prom_data += get_vm_backup_result(jobs, host)
    except Exception as exc:
        logger.error(f"Cannot retrieve job data for {host}: {exc}")
    return prom_data


def main():
    default_config_file = "nakivo_prometheus_exporter.yaml"

    parser = ArgumentParser(
        prog=f"{__appname__}",
        description="""Naviko API Prometheus exporter\n
This program is distributed under the GNU General Public License and comes with ABSOLUTELY NO WARRANTY.\n
This is free software, and you are welcome to redistribute it under certain conditions; Please type --license for more info.""",
    )

    parser.add_argument(
        "-c",
        "--config-file",
        dest="config_file",
        type=str,
        default=default_config_file,
        required=False,
        help=f"Path to YAML configuration file (defaults to current dir {default_config_file})",
    )

    args = parser.parse_args()

    config_file = Path(args.config_file)
    if not config_file.exists():
        logger.critical(f"Cannot load config file {config_file}")
        sys.exit(1)

    config = load_config_file(config_file)
    if not config:
        logger.critical(f"Cannot load configuration file {config_file}")
        sys.exit(1)

    try:
        for nakivo_host in config["nakivo_hosts"]:
            get_nakivo_data(nakivo_host)
    except KeyError:
        logger.critical("Bogus configuration file. Missing nakivo_hosts key.")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
