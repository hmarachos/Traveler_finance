.PHONY: help build up down logs clean test dev prod

help:
	@echo "Traveler Finance - Docker Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev       - запустить в режиме разработки"
	@echo "  make build     - собрать Docker образ"
	@echo "  make up        - запустить контейнеры"
	@echo "  make down      - остановить контейнеры"
	@echo "  make logs      - показать логи приложения"
	@echo "  make clean     - очистить контейнеры и образы"
	@echo ""
	@echo "Production:"
	@echo "  make prod      - запустить в production режиме (с Nginx)"
	@echo "  make prod-up   - запустить production контейнеры"
	@echo "  make prod-down - остановить production контейнеры"
	@echo "  make prod-logs - показать production логи"
	@echo ""
	@echo "Утилиты:"
	@echo "  make shell     - войти в shell контейнера"
	@echo "  make db-reset  - сбросить БД"
	@echo "  make health    - проверить здоровье приложения"

# Development
dev: build up logs

build:
	@echo "🔨 Building Docker image..."
	docker-compose build --no-cache

up:
	@echo "🚀 Starting containers..."
	docker-compose up -d
	@echo "✅ Application is running at http://127.0.0.1:8080"

down:
	@echo "🛑 Stopping containers..."
	docker-compose down

logs:
	@echo "📋 Application logs (Ctrl+C to exit)..."
	docker-compose logs -f

logs-nginx:
	@echo "📋 Nginx logs (Ctrl+C to exit)..."
	docker-compose logs -f nginx

clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	docker rmi $$(docker images | grep traveler-finance | awk '{print $$3}') 2>/dev/null || true
	@echo "✅ Cleanup done"

# Production
prod: prod-build prod-up prod-logs

prod-build:
	@echo "🔨 Building production Docker image..."
	docker-compose -f docker-compose.prod.yml build --no-cache

prod-up:
	@echo "🚀 Starting production containers..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "✅ Production is running at http://127.0.0.1:80"

prod-down:
	@echo "🛑 Stopping production containers..."
	docker-compose -f docker-compose.prod.yml down

prod-logs:
	@echo "📋 Production logs (Ctrl+C to exit)..."
	docker-compose -f docker-compose.prod.yml logs -f

# Utilities
shell:
	docker-compose exec traveler-finance-app /bin/bash

db-reset:
	@echo "⚠️  Resetting database..."
	docker-compose exec traveler-finance-app rm /app/data/traveler.sqlite3
	@echo "✅ Database reset. Restart app to reinitialize."

health:
	@echo "🏥 Checking application health..."
	@curl -f http://127.0.0.1:8080/api/trips > /dev/null 2>&1 && echo "✅ Application is healthy" || echo "❌ Application is not responding"

ps:
	@echo "📦 Running containers:"
	docker-compose ps

restart:
	@echo "🔄 Restarting application..."
	docker-compose restart
	@echo "✅ Application restarted"

pull:
	@echo "📥 Pulling latest images..."
	docker-compose pull

push:
	@echo "📤 Pushing images to registry..."
	docker-compose push

# Quick helpers
status: ps

version:
	@echo "Traveler Finance Docker Setup"
	@echo ""
	@echo "Docker version:"
	@docker --version
	@echo ""
	@echo "Docker Compose version:"
	@docker-compose --version
