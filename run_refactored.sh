#!/bin/bash
# Запуск рефакторенной версии Traveler Finance

cd "$(dirname "$0")" || exit 1

echo "🚀 Запуск Traveler Finance (рефакторенная версия)..."
echo "Нажмите Ctrl+C чтобы остановить"
echo ""

python3 backend/app_refactored.py "$@"
