#!/usr/bin/env bash
# build.sh - Script de construcción ejecutado por Render
set -o errexit

echo "==> 1. Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> 2. Recopilando archivos estáticos..."
python manage.py collectstatic --noinput

echo "==> 3. Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

echo "==> 4. Inicializando cuenta administrativa tatiana..."
python manage.py init_admin

echo "==> Despliegue preparado con éxito para PetPOS Pro."
