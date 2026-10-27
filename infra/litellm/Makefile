.PHONY: help deploy stop health logs

SHELL := /usr/bin/env bash

# Load .env automatically if present
-include .env
export

LITELLM_HOST ?= localhost
LITELLM_PORT ?= 4000
LITELLM_URL  := http://$(LITELLM_HOST):$(LITELLM_PORT)

BLUE  := \033[36m
GREEN := \033[32m
RESET := \033[0m

help: ## Display available targets
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(BLUE)%-10s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

deploy: ## Pull, rebuild, recreate containers, and print LiteLLM URL
	docker compose pull || true
	docker compose up --build --force-recreate -d --remove-orphans
	docker compose ps
	@echo -e "\n$(GREEN)🚀 LiteLLM deployed at:$(RESET) $(BLUE)$(LITELLM_URL)$(RESET)\n"

stop: ## Stop and remove running containers
	docker compose down

health: ## Check LiteLLM service liveliness
	curl -fsS $(LITELLM_URL)/health/liveliness
	@echo ""

logs: ## Tail container logs
	docker compose logs -f