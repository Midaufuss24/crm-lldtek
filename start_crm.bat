@echo off
title LLDTEK CRM SERVER
cd /d "%~dp0"
call .venv\Scripts\activate

:: Dòng này giúp mở trình duyệt vào thẳng App sau khi khởi động
start "" "http://DESKTOP-EK0CH97:8501"

streamlit run app.py
pause