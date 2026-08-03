@echo off
title Prospector Standalone - instalacao
cd /d "%~dp0"
echo ============================================
echo  Prospector Standalone - verificando tudo
echo ============================================
python --version 2>nul || (echo [ERRO] Python nao encontrado. Instale em python.org/downloads marcando "Add python.exe to PATH". & pause & exit /b 1)
echo [OK] Python encontrado.
pip install python-docx >nul 2>&1 && echo [OK] Gerador de contrato Word pronto. || echo [AVISO] python-docx nao instalado (contrato sai so em HTML).
echo.
echo [OK] Instalado! Proximos passos:
echo   1. Crie sua conta em aisa.one (US$ 2 gratis) e gere a chave da API.
echo   2. Duplo clique em iniciar-dashboard.bat
echo   3. No painel: Configuracoes - Motor de IA - cole a chave - Salvar.
echo   4. Aba Assistente: "prospectar nutricionista em Sao Paulo"
pause
