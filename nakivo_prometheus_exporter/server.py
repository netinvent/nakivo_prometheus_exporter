#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of nakivo_prometheus_exporter

__appname__ = "nakivo_prometheus_exporter"
__author__ = "Orsiris de Jong"
__site__ = "https://www.github.com/netinvent/nakivo_prometheus_exporter"
__description__ = "Naviko API Prometheus data exporter"
__copyright__ = "Copyright (C) 2024 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2024032601"


import sys
import os

# Fix dev env module import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pathlib import Path
from argparse import ArgumentParser
from nakivo_prometheus_exporter.prom_parser import load_config_file
from nakivo_prometheus_exporter import metrics
from nakivo_prometheus_exporter import __debug__
from ofunctions.logger_utils import logger_get_logger


def main():
    logger = logger_get_logger()
    _DEV = os.environ.get("_DEV", False)

    default_config_file = "nakivo_prometheus_exporter.yaml"

    parser = ArgumentParser(
        prog=f"{__appname__}",
        description="""Naviko API Prometheus exporter\n
This program is distributed under the GNU General Public License and comes with ABSOLUTELY NO WARRANTY.\n
This is free software, and you are welcome to redistribute it under certain conditions; Please type --license for more info.""",
    )

    parser.add_argument(
        "--dev", action="store_true", help="Run with uvicorn in devel environment"
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

    config_dict = load_config_file(config_file)
    if not config_dict:
        logger.critical(f"Cannot load configuration file {config_file}")
        sys.exit(1)

    try:
        logger = logger_get_logger(config_dict["http_server"]["log_file"], debug=__debug__._DEBUG)
    except (AttributeError, KeyError, IndexError, TypeError):
        pass

    if args.dev:
        _DEV = True

    try:
        listen = config_dict["http_server"]["listen"]
    except (TypeError, KeyError):
        listen = None
    try:
        port = config_dict["http_server"]["port"]
    except (TypeError, KeyError):
        port = None

    logger = logger_get_logger()
    # Cannot use gunicorn on Windows
    if _DEV or os.name == "nt":
        logger.info("Running dev version")
        import uvicorn

        server_args = {
            "workers": 1,
            "log_level": "debug",
            "reload": True,
            "host": listen if listen else "0.0.0.0",
            "port": port if port else 9119,
        }
    else:
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            """
            This class supersedes gunicorn's class in order to load config before launching the app
            """

            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                config = {
                    key: value
                    for key, value in self.options.items()
                    if key in self.cfg.settings and value is not None
                }
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        server_args = {
            "workers": 4,  # Don't run multiple workers since we don't have shared variables yet (multiprocessing.cpu_count() * 2) + 1,
            "bind": f"{listen}:{port}" if listen else "0.0.0.0:8080",
            "worker_class": "uvicorn.workers.UvicornWorker",
        }

    try:
        if _DEV or os.name == "nt":
            uvicorn.run("nakivo_prometheus_exporter.metrics:app", **server_args)
        else:
            StandaloneApplication(metrics.app, server_args).run()
    except KeyboardInterrupt as exc:
        logger.error("Program interrupted by keyoard: {}".format(exc))
        sys.exit(200)
    except Exception as exc:
        logger.error("Program interrupted by error: {}".format(exc))
        logger.critical("Trace:", exc_info=True)
        sys.exit(201)


if __name__ == "__main__":
    main()
