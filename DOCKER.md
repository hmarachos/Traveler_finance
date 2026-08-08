# Docker Setup для Traveler Finance

Полная конфигурация Docker Compose для развертывания приложения Traveler Finance.

## Содержание

- [Требования](#требования)
- [Быстрый старт](#быстрый-старт)
- [Режимы развертывания](#режимы-развертывания)
- [Команды](#команды)
- [Production](#production)
- [Troubleshooting](#troubleshooting)

## Требования

- **Docker** 20.10+ ([установка](https://docs.docker.com/get-docker/))
- **Docker Compose** 2.0+ ([установка](https://docs.docker.com/compose/install/))
- **Make** (опционально, для удобных команд)

### Проверка версий

```bash
docker --version
docker-compose --version
```

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/.../Traveler_finance.git
cd Traveler_finance
```

### 2. Запуск в режиме разработки

```bash
# Вариант 1: С помощью Make (если установлен)
make dev

# Вариант 2: Без Make
docker-compose up -d
docker-compose logs -f
```

### 3. Открыть в браузере

```
http://127.0.0.1:8080
```

### 4. Остановка

```bash
docker-compose down
```

## Режимы развертывания

### Development режим

Используется для разработки - приложение запускается в одном контейнере.

**Файл:** `docker-compose.yml`

```bash
docker-compose up -d
```

**Характеристики:**
- ✅ Быстрый старт
- ✅ Прямой доступ к приложению
- ✅ Легкая отладка
- ✅ Автоматический health check
- ❌ Без reverse proxy (Nginx)

**Порты:**
- Application: `http://127.0.0.1:8080`

### Production режим

Используется для production - приложение запускается с Nginx reverse proxy.

**Файл:** `docker-compose.prod.yml`

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Характеристики:**
- ✅ Nginx reverse proxy (кеширование, сжатие, безопасность)
- ✅ Разделение backend и proxy
- ✅ Production-ready конфигурация
- ✅ Health checks для обоих сервисов
- ✅ Логирование через Nginx

**Порты:**
- Application: `http://127.0.0.1:80` (через Nginx)
- Backend: внутри Docker сети

## Команды

### Основные команды

```bash
# Собрать образ
docker-compose build

# Запустить контейнеры
docker-compose up -d

# Остановить контейнеры
docker-compose down

# Показать логи (все контейнеры)
docker-compose logs -f

# Показать логи конкретного сервиса
docker-compose logs -f traveler-finance-app

# Список запущенных контейнеров
docker-compose ps

# Перезагрузить приложение
docker-compose restart
```

### С помощью Make (если установлен)

```bash
# Показать все команды
make help

# Development
make dev          # Собрать и запустить
make up           # Запустить контейнеры
make down         # Остановить контейнеры
make logs         # Показать логи
make clean        # Очистить всё

# Production
make prod         # Собрать и запустить production
make prod-up      # Запустить production
make prod-down    # Остановить production
make prod-logs    # Показать production логи

# Утилиты
make shell        # Войти в shell контейнера
make db-reset     # Сбросить БД
make health       # Проверить здоровье
make restart      # Перезагрузить
```

## Структура Docker

### docker-compose.yml (Development)

```yaml
services:
  traveler-finance:           # Основной контейнер приложения
    - ports: 8080:8080        # Доступ на http://localhost:8080
    - volumes:
        - traveler-data       # Сохранение БД
        - ./static:ro         # Статика (read-only)
        - ./backend:ro        # Код (read-only)
    - healthcheck             # Проверка здоровья каждые 30 сек
    - restart: unless-stopped # Автоперезагрузка при сбое
```

### docker-compose.prod.yml (Production)

```yaml
services:
  backend:                     # Python приложение
    - expose: 8080            # Доступ только из Docker сети
    - healthcheck             # Проверка здоровья
  
  nginx:                       # Reverse proxy
    - ports: 80:80            # Публичный доступ
    - depends_on: backend     # Зависит от backend
    - healthcheck             # Проверка здоровья Nginx
```

### Volumes

- `traveler-data` - сохранение SQLite БД между перезагрузками
- `traveler-logs` - логи Nginx (production только)

## Production

### Развертывание на сервере

1. **Клонировать репозиторий**
   ```bash
   git clone https://github.com/.../Traveler_finance.git /opt/traveler-finance
   cd /opt/traveler-finance
   ```

2. **Скопировать переменные окружения**
   ```bash
   cp .env.example .env
   # Отредактировать .env если нужно
   ```

3. **Запустить production контейнеры**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

4. **Проверить статус**
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

### Использование с Caddy (вместо Nginx)

Если хотите использовать Caddy с автоматическим HTTPS:

```bash
# Установить Caddy
sudo apt-get install caddy

# Создать Caddyfile
cat > /etc/caddy/Caddyfile <<EOF
your-domain.com {
    reverse_proxy 127.0.0.1:8080
}
EOF

# Перезагрузить Caddy
sudo systemctl reload caddy

# Запустить только backend контейнер
docker-compose up -d traveler-finance-app
```

### Использование с Docker Swarm

Для кластера серверов:

```bash
# Инициализировать Swarm
docker swarm init

# Развернуть stack
docker stack deploy -c docker-compose.prod.yml traveler

# Показать services
docker service ls

# Просмотреть логи
docker service logs traveler_backend
```

### Использование с Kubernetes

Конвертировать docker-compose в Kubernetes манифесты:

```bash
# Установить kompose
curl -L https://github.com/kubernetes/kompose/releases/download/v1.28.0/kompose-linux-amd64 -o kompose
chmod +x kompose

# Конвертировать
./kompose convert -f docker-compose.prod.yml

# Применить на кластер
kubectl apply -f *.yaml
```

## Переменные окружения

Создайте `.env` файл (или используйте `.env.example`):

```bash
cp .env.example .env
```

### Доступные переменные

| Переменная | Значение по умолчанию | Описание |
|-----------|----------------------|---------|
| `PORT` | `8080` | Порт приложения |
| `TRAVELER_DB` | `/app/data/traveler.sqlite3` | Путь к БД |
| `PYTHONUNBUFFERED` | `1` | Immediate output для логов |
| `PYTHONDONTWRITEBYTECODE` | `1` | Не создавать .pyc файлы |

## Health Check

Оба режима включают health checks:

```bash
# Development
curl http://127.0.0.1:8080/api/trips

# Production
curl http://127.0.0.1/health
```

Если приложение не отвечает, оно автоматически перезагружается.

## Логирование

### Development режим

```bash
# Логи приложения
docker-compose logs -f traveler-finance-app

# Последние 50 строк
docker-compose logs --tail 50

# Логи за последний час
docker-compose logs --since 1h
```

### Production режим

```bash
# Логи backend
docker-compose -f docker-compose.prod.yml logs -f backend

# Логи Nginx
docker-compose -f docker-compose.prod.yml logs -f nginx

# Только ошибки
docker-compose -f docker-compose.prod.yml logs -f --tail 100 | grep -i error
```

## Обновление приложения

```bash
# 1. Остановить текущие контейнеры
docker-compose down

# 2. Обновить код из репозитория
git pull origin main

# 3. Пересобрать образы
docker-compose build --no-cache

# 4. Запустить
docker-compose up -d
```

## Backup БД

```bash
# Скопировать БД с контейнера на хост
docker cp traveler-finance-app:/app/data/traveler.sqlite3 ./backup/traveler-$(date +%Y%m%d).sqlite3

# Или используя volume
docker run --rm -v traveler-data:/data -v $(pwd):/backup alpine tar czf /backup/traveler-backup.tar.gz /data
```

## Restore БД

```bash
# Скопировать БД в контейнер
docker cp ./backup/traveler.sqlite3 traveler-finance-app:/app/data/

# Или используя volume
docker run --rm -v traveler-data:/data -v $(pwd):/backup alpine tar xzf /backup/traveler-backup.tar.gz -C /
```

## Очистка

```bash
# Остановить и удалить контейнеры
docker-compose down

# Удалить volume (БД будет удалена!)
docker-compose down -v

# Удалить образы
docker rmi traveler-finance:latest

# Очистить всё неиспользуемое
docker system prune -a
```

## Troubleshooting

### Контейнер не запускается

```bash
# Проверить логи
docker-compose logs traveler-finance-app

# Проверить существование контейнера
docker ps -a

# Перестроить образ
docker-compose build --no-cache
```

### Ошибка "Address already in use"

```bash
# Найти процесс на порту 8080
lsof -i :8080

# Или использовать другой порт
docker-compose -e "PORT=8888" up -d
```

### БД повреждена

```bash
# Сбросить БД (создаст новую)
make db-reset

# Или вручную
docker-compose exec traveler-finance-app rm /app/data/traveler.sqlite3
docker-compose restart
```

### Медленное выполнение на Mac/Windows

Docker Desktop использует виртуальную машину, это может замедлить работу. Попробуйте:

```bash
# Увеличить ресурсы в Docker Desktop settings
# Memory: 4GB+
# CPUs: 2+

# Или используйте colima вместо Docker Desktop
brew install colima
colima start --memory 4 --cpu 2
```

### Проблемы с Nginx

```bash
# Проверить конфиг Nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# Перезагрузить Nginx
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

## Performance Tips

1. **Используйте production режим** с Nginx для лучшей производительности
2. **Кешируйте статику** - Nginx автоматически кеширует файлы на 30 дней
3. **Мониторьте логи** - регулярно проверяйте логи на ошибки
4. **Очищайте старые образы** - `docker image prune`
5. **Используйте read-only volumes** для кода

## FAQ

**Q: Могу ли я запустить несколько инстансов?**
A: Да, скопируйте `docker-compose.yml` с другим именем и измените порты.

**Q: Как добавить SSL/HTTPS?**
A: Используйте Caddy или Let's Encrypt с Nginx.

**Q: Где хранятся данные?**
A: В Docker volume `traveler-data` (обычно `/var/lib/docker/volumes/`).

**Q: Могу ли я использовать PostgreSQL вместо SQLite?**
A: Да, переделайте backend для использования PostgreSQL.

## Поддержка

Если возникли проблемы:
1. Проверьте [логи](#логирование)
2. Прочитайте [Troubleshooting](#troubleshooting)
3. Откройте issue на GitHub

## Лицензия

MIT License
