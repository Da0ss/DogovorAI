#!/bin/bash

# Настройки (Берем данные из нашего будущего локального докера)
DB_CONTAINER_NAME="dogovorai_postgres"
DB_USER="dionysus_user"
DB_NAME="startup_db"
BACKUP_DIR="./backups"
ROTATION_DAYS=7

# Создаем папку для бэкапов, если её нет
mkdir -p $BACKUP_DIR

# Имя файла с таймстампом
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql"

echo "=== [$(date)] Начало процесса резервного копирования ==="

# Дампим базу данных прямо из контейнера Docker
docker exec $DB_CONTAINER_NAME pg_dump -U $DB_USER -d $DB_NAME > $BACKUP_FILE

# Проверяем, создался ли файл и не пустой ли он
if [ -s "$BACKUP_FILE" ]; then
    echo "[УСПЕХ] Бэкап успешно создан: $BACKUP_FILE"
else
    echo "[ОШИБКА] Не удалось создать бэкап или файл пуст!"
    rm -f $BACKUP_FILE
    exit 1
fi

# Ротация: удаляем бэкапы старше 7 дней, чтобы диск не переполнился
echo "Проверка старых бэкапов для удаления (старше $ROTATION_DAYS дней)..."
find $BACKUP_DIR -name "backup_*.sql" -type f -mtime +$ROTATION_DAYS -exec rm {} \; -exec echo "[УДАЛЕНО] Старый бэкап: {}" \;

echo "=== Процесс завершен ==="