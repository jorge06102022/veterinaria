@echo off
title PetPOS Pro - Servidor Local
color 0A
cd /d "%~dp0"
echo ==============================================================
echo        INICIANDO PETPOS PRO - PELUQUERIA & PET SHOP
echo ==============================================================
echo.
echo URL de acceso local: http://127.0.0.1:8000/
echo Usuario: admin
echo Contrasena: admin123
echo.
echo Presiona Ctrl + C para detener el servidor.
echo ==============================================================
echo.
python manage.py runserver 127.0.0.1:8000
pause
