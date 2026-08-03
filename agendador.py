#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prospector Standalone — agendador de prospecção.
Lê agendamentos.json e roda as buscas que estiverem no horário.
Chamado a cada minuto pela tarefa do sistema (instalar-agendador).
Cada agendamento: {"nicho","cidade","quantos","hora":"HH:MM","dias":[0-6]|"todos","ultimo":"YYYY-MM-DD"}
"""
import json, os, sys, datetime, subprocess

for _stream in (getattr(sys, 'stdout', None), getattr(sys, 'stderr', None)):
    try:
        if _stream and hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PASTA = os.path.dirname(os.path.abspath(__file__))
AG = os.path.join(PASTA, 'agendamentos.json')
LOG = os.path.join(PASTA, 'agendador-log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write('[%s] %s\n' % (datetime.datetime.now().strftime('%d/%m %H:%M'), msg))

def main():
    if not os.path.exists(AG):
        return
    try:
        ags = json.load(open(AG, encoding='utf-8'))
    except Exception as e:
        log('erro lendo agendamentos: %s' % e); return
    agora = datetime.datetime.now()
    hoje = agora.strftime('%Y-%m-%d')
    hhmm = agora.strftime('%H:%M')
    mudou = False
    for a in ags:
        if not a.get('ativo', True):
            continue
        # dia da semana permitido?
        dias = a.get('dias', 'todos')
        if dias != 'todos' and agora.weekday() not in dias:
            continue
        # já rodou hoje?
        if a.get('ultimo') == hoje:
            continue
        # chegou o horário? (roda se o minuto atual >= horário e ainda não rodou hoje)
        if hhmm >= a.get('hora', '09:00'):
            nicho, cidade, quantos = a.get('nicho'), a.get('cidade'), a.get('quantos', 5)
            if not nicho or not cidade:
                continue
            log('rodando: %s em %s (%s leads)' % (nicho, cidade, quantos))
            try:
                # ajusta leads_por_busca no config e roda o motor
                cfgp = os.path.join(PASTA, 'config-standalone.json')
                cst = json.load(open(cfgp, encoding='utf-8'))
                cst.setdefault('prospeccao', {})['leads_por_busca'] = int(quantos)
                json.dump(cst, open(cfgp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                r = subprocess.run([sys.executable, os.path.join(PASTA, 'motor.py'), nicho, cidade],
                                   capture_output=True, text=True, timeout=600, cwd=PASTA)
                log('  ok' if r.returncode == 0 else '  erro: %s' % (r.stderr or '')[:200])
            except Exception as e:
                log('  falha: %s' % e)
            a['ultimo'] = hoje
            mudou = True
    if mudou:
        json.dump(ags, open(AG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
