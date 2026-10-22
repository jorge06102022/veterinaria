#!/usr/bin/env bash
# start.sh - Comando de inicio del servidor en Render
exec gunicorn pos_project.wsgi:application --bind 0.0.0.0:$PORT