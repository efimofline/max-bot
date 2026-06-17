@echo off
REM Запуск echo-бота для MAX.
REM Перед первым запуском вставь свой токен ниже (между кавычками)
REM или впиши его прямо в bot.py.

REM set MAX_BOT_TOKEN=сюда_твой_токен

cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" bot.py
pause
