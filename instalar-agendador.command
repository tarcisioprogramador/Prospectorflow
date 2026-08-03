#!/bin/bash
cd "$(dirname "$0")"
PASTA="$(pwd)"
PLIST="$HOME/Library/LaunchAgents/com.prospector.agendador.plist"
mkdir -p "$HOME/Library/LaunchAgents"
echo ""
echo " IMPORTANTE: prospeccoes agendadas consomem creditos da sua conta AIsa"
echo " automaticamente. Configure com o saldo em mente."
echo ""
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.prospector.agendador</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>$PASTA/agendador.py</string>
  </array>
  <key>StartInterval</key><integer>60</integer>
  <key>RunAtLoad</key><true/>
</dict></plist>
PLISTEOF
launchctl unload "$PLIST" 2>/dev/null
if launchctl load "$PLIST"; then
  echo "[OK] Agendador instalado! Configure os horarios no painel, aba Leads."
  echo "Para desinstalar: launchctl unload \"$PLIST\" && rm \"$PLIST\""
else
  echo "[ERRO] Nao consegui registrar. Rode de novo."
fi
read -p "Enter para fechar..."
