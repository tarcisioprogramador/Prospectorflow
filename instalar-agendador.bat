@echo off
title Prospector - instalar agendador automatico
echo.
echo  Isto cria uma tarefa do Windows que verifica a cada minuto
echo  se ha alguma prospeccao agendada e roda sozinha no horario.
echo.
echo  IMPORTANTE: prospeccoes agendadas consomem creditos da sua
echo  conta AIsa automaticamente. Configure com o saldo em mente.
echo.
schtasks /Create /F /TN "ProspectorAgendador" /SC MINUTE /MO 1 /TR "wscript.exe \"%~dp0agendador-oculto.vbs\""
if %errorlevel%==0 (
  echo.
  echo  [OK] Agendador instalado! Configure os horarios no painel, aba Leads.
  echo  Para desinstalar: schtasks /Delete /TN ProspectorAgendador /F
) else (
  echo.
  echo  [ERRO] Rode este arquivo com botao direito ^> Executar como administrador.
)
echo.
pause
