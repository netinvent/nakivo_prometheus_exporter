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


import logging
import secrets
from argparse import ArgumentParser
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi_offline import FastAPIOffline
from nakivo_prometheus_exporter.prom_parser import load_config_file, get_nakivo_data


logger = logging.getLogger()


# Make sure we load given config files again
default_config_file = "nakivo_prometheus_exporter.yaml"
parser = ArgumentParser()
parser.add_argument(
    "-c",
    "--config-file",
    dest="config_file",
    type=str,
    default=default_config_file,
    required=False,
    help="Path to nakivo_prometheus_exporter.yaml file",
)
args = parser.parse_args()
if args.config_file:
    config_dict = load_config_file(args.config_file)
else:
    logger.critical("No configuration file given. Exiting.")


app = FastAPIOffline()
security = HTTPBasic()

# Timestamp of last time we sent an sms, per number
LAST_SENT_TIMESTAMP = {}


def anonymous_auth():
    return "anonymous"


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = config_dict["http_server"]["username"].encode("utf-8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = config_dict["http_server"]["password"].encode("utf-8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


try:
    if config_dict["http_server"]["no_auth"] is True:
        logger.warning("Running without HTTP authentication")
        auth_scheme = anonymous_auth
    else:
        logger.info("Running with HTTP authentication")
        auth_scheme = get_current_username
except (KeyError, AttributeError, TypeError):
    auth_scheme = get_current_username
    logger.info("Running with HTTP authentication")


@app.get("/")
async def api_root(auth=Depends(auth_scheme)):
    return {"app": __appname__}


@app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics(auth=Depends(auth_scheme)):
    data = ""
    try:
        for nakivo_host in config_dict["nakivo_hosts"]:
            sub_data = get_nakivo_data(nakivo_host)
            if sub_data:
                data += sub_data
        return data
    except KeyError:
        logger.critical("Bogus configuration file. Missing nakivo_hosts key.")
