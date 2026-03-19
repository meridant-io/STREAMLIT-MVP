#!/bin/bash
printenv ENV_FILE > .env
printenv AUTH_CONFIG >auth_config.yaml
docker compose up --build