#!/bin/bash
set -e

echo "Waiting for DB..."
python -c "
import time, psycopg2, os
for i in range(30):
    try:
        psycopg2.connect(host=os.environ.get('DB_HOST','db'), dbname=os.environ.get('DB_NAME','lottodb'), user=os.environ.get('DB_USER','lottouser'), password=os.environ.get('DB_PASSWORD','lottopass'), port=os.environ.get('DB_PORT','5432')).close()
        print('DB OK'); break
    except: print(f'retry {i+1}'); time.sleep(2)
"

echo "Making migrations..."
python manage.py makemigrations lotto --noinput

echo "Migrating..."
python manage.py migrate --noinput

echo "Collectstatic..."
python manage.py collectstatic --noinput

echo "Init data..."
python manage.py shell -c "
from django.contrib.auth import get_user_model; from lotto.models import LottoRound
User = get_user_model()
if not User.objects.filter(username='admin').exists(): User.objects.create_superuser('admin','admin@lotto.com','admin1234'); print('admin created')
if not LottoRound.objects.exists(): LottoRound.objects.create(round_number=1); print('round 1 created')
"

echo "Starting server..."
exec gunicorn lotto_app.wsgi:application --bind 0.0.0.0:8000 --workers 2