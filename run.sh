#!/bin/bash
# latest version of java and a python environment where requirements are installed is required

# CVE-2025-48795 Mitigation: Use custom Log4j config to disable Apache CXF logging
# This prevents sensitive file contents from being logged by the vulnerable CXF code
nohup java -Dlog4j.configurationFile=file:jars/log4j2-secure.xml \
  -jar jars/tika-server-standard-nlm-modified-2.9.2_v2.jar > /dev/null 2>&1 &

python -m nlm_ingestor.ingestion_daemon
