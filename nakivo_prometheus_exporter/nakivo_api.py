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

from typing import Union, List
from ofunctions.requestor import Requestor
from logging import getLogger

logger = getLogger()


class NakivoAPI:
    """
    Python bindings for Nakivo API
    """
    def __init__(self, host: str, username: str, password: str, cert_verify: bool = True):
        if not host:
            msg = "No Nakvio host given"
            logger.critical(msg)
        
        if not username:
            msg = "No nakivo username given"
            logger.critical(msg)
        
        if not password:
            msg = "No nakivo password given"
            logger.critical(msg)
        
        self.host = host
        self.username = username
        self.password = password
        self.cert_verify = cert_verify

        self.req = Requestor(host, cert_verify=self.cert_verify)
        if not self.req.create_session():
            msg = f"Cannot create session to {self.host}"
            logger.critical(msg)
            raise ValueError(msg)
        self.req.endpoint = 'c/router'

    def authenticate(self):
        payload = {
            "action": "AuthenticationManagement",
            "method": "login",
            # data: username, password, remember_me bool
            "data": [self.username, self.password, False],
            "type": "rpc",
            "tid": 1
        }
        result = self.req.requestor(action="create", data=payload)
        if not result:
            msg = "Authentication Error"
            try:
                logger.error(f": {result.text}")
                return False
            except AttributeError:
                logger.error(": No more info. Error code")
                return False
        return result

    def get_license_info(self):
        payload = {
            "action": "LicensingManagement",
            "method": "getLicenseInfo",
            "data": None,
            "type": "rpc",
            "tid": 1
        }
        return self.req.requestor(action="create", data=payload)

    def get_repository_info(self):
        payload = {
            "action": "BackupManagement",
            "method": "getBackupRepository",
            "data": [3],
            "type": "rpc",
            "tid": 1
        }
        return self.req.requestor(action="create", data=payload)


    def get_job_list(self):
        payload = {
            "action": "JobSummaryManagement",
            "method": "getGroupInfo",
            # data: [[Groups: int, or None for all groups], clientTimeOffsetToUtc: int, Get Children: bool]
            "data": [[None],0,True],
            "type": "rpc",
            "tid": 1
        }
        return self.req.requestor(action="create", data=payload)
    
    def get_job(self, job_ids: Union[int, List[int]]):
        payload = {
            "action": "JobSummaryManagement",
            "method": "getJobInfo",
            # [[idList: int], clientTimeOffsetToUtc: int]
            "data": [job_ids, 0],
            "type": "rpc",
            "tid": 1
        }
        return self.req.requestor(action="create", data=payload)

    def get_jobs(self):
        result = self.get_job_list()
        if result:
            try:
                job_children_ids = []
                for child in result["data"]["children"]:
                    job_children_ids += child["childJobIds"]
            except (AttributeError, IndexError, TypeError):
                logger.error("Cannot get job IDS")
        else:
            logger.error("Obtaining job list failed")
        
        job_result = self.get_job(job_children_ids)
        return job_result
