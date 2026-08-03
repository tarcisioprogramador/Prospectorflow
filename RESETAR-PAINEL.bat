@echo off
title Resetar painel
cd /d "%~dp0"
echo Encerrando servidores antigos...
taskkill /F /IM python.exe >nul 2>&1
echo Apagando dashboard.html velho (sera reconstruido do template)...
if exist dashboard.html del /F dashboard.html
echo Verificando o template...
python -c "t=open('dashboard-template.html',encoding='utf-8').read(); assert 'var view=' in t and t.count('<script>')>=1; print('  template OK, tamanho:',len(t))"
echo.
echo Iniciando servidor limpo...
start "" python dashboard-server.py
echo.
echo Pronto! Aguarde o navegador abrir em localhost:8766 e de Ctrl+Shift+R.
echo Se o menu ainda vier vazio, tire print e mande pro Claude.
pause
