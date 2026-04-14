@echo off
title H&A - Processo Principal

REM === Vai para a pasta do projeto ===
cd /d "%~dp0"

REM === Ativa o ambiente virtual ===
call venv\Scripts\activate.bat

REM === Inicia a UI do H&A ===
python NOME_EXATO_DO_ARQUIVO.py

pause
