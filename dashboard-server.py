#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prospector — servidor local do dashboard (SQLite). Sem dependências: só Python padrão.
Uso: python dashboard-server.py  (ou duplo clique em iniciar-dashboard.bat)
Abre em http://localhost:8766 — edições, exclusões e drag&drop salvam no prospector.db

Deploy (ex.: Railway/Render): definir PORT, HOST=0.0.0.0, SENHA_PAINEL, PROSPECTOR_DB, AISA_KEY.
"""
import json, sqlite3, os, sys, webbrowser, hashlib
for _stream in (getattr(sys, 'stdout', None), getattr(sys, 'stderr', None)):
    try:
        if _stream and hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PASTA = os.path.dirname(os.path.abspath(__file__))
os.chdir(PASTA)
DB = os.environ.get('PROSPECTOR_DB', os.path.join(PASTA, 'prospector.db'))
DATA = os.environ.get('PROSPECTOR_DATA', PASTA)
AGENDAMENTOS = os.path.join(DATA, 'agendamentos.json')
CONFIG = os.path.join(PASTA, 'prospector-config.json')

def ler_config():
    try: return json.load(open(CONFIG, encoding='utf-8'))
    except Exception: return {}
PORT = int(os.environ.get('PORT', '8766'))
DEPLOY = 'PORT' in os.environ
HOST = os.environ.get('HOST', '0.0.0.0' if DEPLOY else '127.0.0.1')
SENHA = os.environ.get('SENHA_PAINEL') or ''
TOKEN = hashlib.sha256(('prospector::' + SENHA).encode('utf-8')).hexdigest() if SENHA else ''
PROTEGIDO = bool(SENHA)

def garantir_config():
    """Sem config-standalone.json (ex.: primeiro deploy): cria a partir das variáveis de ambiente."""
    pst = os.path.join(PASTA, 'config-standalone.json')
    if os.path.exists(pst): return
    cst = {}
    if os.environ.get('AISA_KEY'): cst['aisa_key'] = os.environ['AISA_KEY']
    if os.environ.get('AISA_MODELO'): cst['modelo'] = os.environ['AISA_MODELO']
    pr = {}
    for k in ('nota_minima', 'avaliacoes_minimas', 'raio_km', 'leads_por_busca'):
        v = os.environ.get('PROSPECCAO_' + k.upper())
        if v is not None:
            try: pr[k] = float(v) if k == 'nota_minima' else int(float(v))
            except Exception: pass
    if pr: cst['prospeccao'] = pr
    json.dump(cst, open(pst, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('config-standalone.json criado a partir das variáveis de ambiente')

CAMPOS = ['slug','nome','nicho','cidade','nota','avaliacoes','email','telefone','whatsapp',
          'siteAntigo','motivo','status','urlNova','dataProposta','valor','obs',
          'contratoStatus','contratoEm','manutencao','pago','docCliente','endCliente',
          'instagram','igSeguidores','igPosts','igAtivo','igCategoria','score','temperatura',
          'abordagem','dossie','contatadoEm','contatadoPor','busca']

def conexao():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS leads(
        slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
        email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
        status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
        contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
        atualizado TEXT DEFAULT (datetime('now','localtime')))''')
    for col, tipo in [('contratoStatus',"TEXT DEFAULT 'pendente'"),('contratoEm','TEXT'),('manutencao','REAL'),('pago','INTEGER DEFAULT 0'),('docCliente','TEXT'),('endCliente','TEXT'),
                      ('instagram','TEXT'),('igSeguidores','INTEGER'),('igPosts','INTEGER'),('igAtivo','TEXT'),('igCategoria','TEXT'),('score','INTEGER'),('temperatura','TEXT'),('abordagem','TEXT'),('dossie','TEXT'),('busca','TEXT')]:
        try: c.execute('ALTER TABLE leads ADD COLUMN %s %s' % (col, tipo))
        except sqlite3.OperationalError: pass
    return c

def importar_snapshot():
    """Primeira execução sem banco: importa os leads embutidos no dashboard.html."""
    try:
        html = open(os.path.join(PASTA, 'dashboard.html'), encoding='utf-8').read()
        ini = html.index('<script id="dados" type="application/json">') + len('<script id="dados" type="application/json">')
        fim = html.index('</script>', ini)
        dados = json.loads(html[ini:fim])
        c = conexao()
        for l in dados.get('leads', []):
            c.execute('INSERT OR IGNORE INTO leads (%s) VALUES (%s)' % (','.join(CAMPOS), ','.join('?'*len(CAMPOS))),
                      [l.get(k) for k in CAMPOS])
        c.commit(); c.close()
        print('Snapshot importado do dashboard.html para o prospector.db')
    except Exception as e:
        print('(sem snapshot para importar: %s)' % e)

class App(SimpleHTTPRequestHandler):
    def _cookie(self, nome):
        for par in (self.headers.get('Cookie', '') or '').split(';'):
            par = par.strip()
            if par.startswith(nome + '='):
                return par[len(nome) + 1:]
        return None
    def _autenticado(self):
        if not PROTEGIDO: return True
        return self._cookie('painel') == TOKEN
    def _login_page(self):
        corpo = ('<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<title>Prospector — acesso</title>'
                 '<style>body{font-family:Segoe UI,Arial,sans-serif;background:#0f1117;color:#e7e7ea;'
                 'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}'
                 '.box{background:#171a21;border:1px solid #2a2e3a;border-radius:14px;padding:32px;width:300px}'
                 'h1{font-size:18px;margin:0 0 4px} p{color:#8a90a0;font-size:13px;margin:0 0 18px}'
                 'input{width:100%;box-sizing:border-box;padding:11px;border-radius:8px;border:1px solid #2a2e3a;'
                 'background:#0f1117;color:#fff;font-size:14px;margin-bottom:14px}'
                 'button{width:100%;padding:11px;border:0;border-radius:8px;background:#3b82f6;color:#fff;'
                 'font-size:14px;font-weight:600;cursor:pointer}'
                 'button:hover{background:#2f6fdc} .err{color:#f87171;font-size:12.5px;display:none;margin-bottom:10px}'
                 '</style></head><body><div class="box"><h1>🔐 Prospector</h1>'
                 '<p>Painel protegido — digite a senha.</p>'
                 '<div class="err" id="err">Senha incorreta</div>'
                 '<input type="password" id="s" placeholder="Senha" autofocus>'
                 '<button onclick="entrar()">Entrar</button></div>'
                 '<script>function entrar(){var s=document.getElementById("s").value;'
                 'fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},'
                 'body:JSON.stringify({senha:s})}).then(function(r){if(r.ok){location.href="/"}'
                 'else{document.getElementById("err").style.display="block"}})'
                 '.catch(function(){document.getElementById("err").style.display="block"})}'
                 'document.getElementById("s").addEventListener("keydown",function(e){if(e.key==="Enter")entrar()})'
                 '</script></body></html>').encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers(); self.wfile.write(corpo)
    def _negar(self):
        return self._json(401, {'erro': 'nao_autenticado'})
    def _ver_rota(self, rota):
        if not PROTEGIDO: return True
        if rota.startswith('/api/'):
            if not self._autenticado():
                self._negar(); return False
        elif rota in ('/', '/dashboard.html', '/dashboard-template.html'):
            if not self._autenticado():
                self._login_page(); return False
        return True
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        super().end_headers()
    def _login(self):
        corpo = self._corpo()
        if PROTEGIDO and corpo.get('senha') == SENHA:
            body = json.dumps({'ok': True}, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            seg = '; Secure' if (DEPLOY or os.environ.get('COOKIE_SECURE')) else ''
            self.send_header('Set-Cookie', 'painel=%s; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax%s' % (TOKEN, seg))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
            return
        return self._json(401, {'erro': 'senha'})
    def _json(self, code, obj):
        corpo = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers(); self.wfile.write(corpo)
    def _corpo(self):
        n = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
    def do_GET(self):
        if not self._ver_rota(self.path.split('?')[0]): return
        if self.path.split('?')[0] == '/api/config':
            cfg = ler_config()
            hg = dict(cfg.get('hostgator', {}))
            hg['senhaDefinida'] = bool(hg.get('senha'))
            hg.pop('senha', None)  # a senha NUNCA sai do arquivo
            aisa = {}; prosp = {}
            pst = os.path.join(PASTA, 'config-standalone.json')
            if os.path.exists(pst):
                cst = json.load(open(pst, encoding='utf-8'))
                aisa = {'chaveDefinida': bool(cst.get('aisa_key')), 'modelo': cst.get('modelo', '')}
                prosp = cst.get('prospeccao', {})
            return self._json(200, {'contratante': cfg.get('contratante', {}), 'hostgator': hg, 'aisa': aisa, 'prospeccao': prosp})
        if self.path.split('?')[0] == '/api/leads':
            c = conexao(); c.row_factory = sqlite3.Row
            rows = [dict(r) for r in c.execute('SELECT * FROM leads').fetchall()]; c.close()
            return self._json(200, rows)
        if self.path.split('?')[0] == '/api/agendamentos':
            ap = AGENDAMENTOS
            ags = json.load(open(ap, encoding='utf-8')) if os.path.exists(ap) else []
            return self._json(200, ags)
        if self.path in ('/', ''):
            dh = os.path.join(PASTA, 'dashboard.html')
            tp = os.path.join(PASTA, 'dashboard-template.html')
            # SEMPRE regenera do template (garante que o painel reflete a versão atual)
            if os.path.exists(tp):
                import datetime as _dt
                c = conexao(); c.row_factory = sqlite3.Row
                _leads = [dict(r) for r in c.execute('SELECT * FROM leads').fetchall()]; c.close()
                _t = open(tp, encoding='utf-8').read().replace('__DADOS__',
                    json.dumps({'atualizado': _dt.datetime.now().strftime('%d/%m/%Y %H:%M'), 'leads': _leads}, ensure_ascii=False))
                open(dh, 'w', encoding='utf-8').write(_t)
            self.path = '/dashboard.html'
        return SimpleHTTPRequestHandler.do_GET(self)
    def do_POST(self):
        if self.path.split('?')[0].startswith('/api/') and not self._autenticado():
            if self.path.split('?')[0] == '/api/login':
                return self._login()
            return self._negar()
        if self.path.split('?')[0] == '/api/login':
            return self._login()
        if self.path.split('?')[0] == '/api/logout':
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Set-Cookie', 'painel=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.split('?')[0] == '/api/agendamentos':
            ags = self._corpo()
            if isinstance(ags, list):
                json.dump(ags, open(AGENDAMENTOS, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                return self._json(200, {'ok': True})
            return self._json(400, {'erro': 'formato'})
        if self.path.split('?')[0] == '/api/assistente':
            try:
                import engine
                msg = self._corpo().get('mensagem', '')
                cfg_st = json.load(open(os.path.join(PASTA, 'config-standalone.json'), encoding='utf-8'))
                simular = not cfg_st.get('aisa_key')
                resp = engine.assistente(msg, simular=simular)
                if simular:
                    resp += '\n\n(modo simulação — cole sua chave AIsa em Configurações pra valer de verdade)'
                return self._json(200, {'resposta': resp})
            except Exception as e:
                import traceback
                with open(os.path.join(PASTA, 'painel-log.txt'), 'a', encoding='utf-8') as _f:
                    _f.write('\n=== %s ===\n%s\n' % (e, traceback.format_exc()))
                return self._json(200, {'resposta': '⚠️ Erro no assistente: %s (detalhe em painel-log.txt)' % e})
        if self.path.split('?')[0] == '/api/leads':
            l = self._corpo(); c = conexao()
            c.execute('INSERT OR REPLACE INTO leads (%s) VALUES (%s)' % (','.join(CAMPOS), ','.join('?'*len(CAMPOS))),
                      [l.get(k) for k in CAMPOS])
            c.commit(); c.close(); return self._json(200, {'ok': True})
        return self._json(404, {'erro': 'rota'})
    def do_PUT(self):
        if self.path.split('?')[0].startswith('/api/') and not self._autenticado():
            return self._negar()
        if self.path.split('?')[0] == '/api/config':
            cfg = ler_config(); corpo = self._corpo()
            if 'prospeccao' in corpo:
                pst = os.path.join(PASTA, 'config-standalone.json')
                cst = json.load(open(pst, encoding='utf-8')) if os.path.exists(pst) else {}
                pr = cst.get('prospeccao', {})
                for k, v in corpo['prospeccao'].items():
                    try: pr[k] = float(v) if k in ('nota_minima',) else int(float(v))
                    except Exception: pass
                cst['prospeccao'] = pr
                json.dump(cst, open(pst, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                return self._json(200, {'ok': True})
            if 'contratante' in corpo or 'hostgator' in corpo or 'aisa' in corpo:
                if 'contratante' in corpo:
                    ct = cfg.get('contratante', {})
                    ct.update({k: v for k, v in corpo['contratante'].items() if isinstance(v, str)})
                    cfg['contratante'] = ct
                if 'aisa' in corpo:
                    pst = os.path.join(PASTA, 'config-standalone.json')
                    cst = json.load(open(pst, encoding='utf-8')) if os.path.exists(pst) else {}
                    a = corpo['aisa']
                    if isinstance(a.get('aisa_key'), str) and a['aisa_key']:
                        cst['aisa_key'] = a['aisa_key']
                    if isinstance(a.get('modelo'), str) and a['modelo']:
                        cst['modelo'] = a['modelo']
                    json.dump(cst, open(pst, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                if 'hostgator' in corpo:
                    hg = cfg.get('hostgator', {})
                    for k, v in corpo['hostgator'].items():
                        if not isinstance(v, str): continue
                        if k == 'senha' and v == '': continue  # em branco = mantém a atual
                        hg[k] = v
                    cfg['hostgator'] = hg
            else:  # compatibilidade: corpo plano = contratante
                ct = cfg.get('contratante', {})
                ct.update({k: v for k, v in corpo.items() if isinstance(v, str)})
                cfg['contratante'] = ct
            json.dump(cfg, open(CONFIG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            return self._json(200, {'ok': True})
        partes = self.path.split('?')[0].split('/')
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'leads':
            slug, ch = partes[3], self._corpo()
            sets = [k for k in ch if k in CAMPOS and k != 'slug']
            if sets:
                c = conexao()
                c.execute('UPDATE leads SET %s, atualizado=datetime("now","localtime") WHERE slug=?' %
                          ','.join('%s=?' % k for k in sets), [ch[k] for k in sets] + [slug])
                c.commit(); c.close()
            return self._json(200, {'ok': True})
        return self._json(404, {'erro': 'rota'})
    def do_DELETE(self):
        if self.path.split('?')[0].startswith('/api/') and not self._autenticado():
            return self._negar()
        from urllib.parse import parse_qs
        p = self.path.split('?')
        partes = p[0].split('/')
        qs = parse_qs(p[1]) if len(p) > 1 else {}
        st = (qs.get('status') or [''])[0]
        if len(partes) == 3 and partes[1] == 'api' and partes[2] == 'leads':
            c = conexao()
            if st == 'novo':
                n = c.execute("DELETE FROM leads WHERE status='novo' AND contatadoEm IS NULL").rowcount
                c.commit(); c.close(); return self._json(200, {'ok': True, 'apagados': n})
            if st == 'todas':
                n = c.execute('DELETE FROM leads').rowcount
                c.commit(); c.close(); return self._json(200, {'ok': True, 'apagados': n})
            c.close()
            return self._json(400, {'erro': 'status invalido (novo|todas)'})
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'leads':
            c = conexao(); c.execute('DELETE FROM leads WHERE slug=?', (partes[3],)); c.commit(); c.close()
            return self._json(200, {'ok': True})
        return self._json(404, {'erro': 'rota'})
    def log_message(self, *a): pass

if __name__ == '__main__':
    garantir_config()
    novo = not os.path.exists(DB)
    conexao().close()
    if novo: importar_snapshot()
    if PROTEGIDO:
        print('Painel com acesso por senha em http://%s:%d' % (HOST, PORT))
    else:
        print('Prospector rodando em http://localhost:%d  (Ctrl+C para parar)' % PORT)
    if not DEPLOY:
        try: webbrowser.open('http://localhost:%d' % PORT)
        except Exception: pass
    try: ThreadingHTTPServer((HOST, PORT), App).serve_forever()
    except KeyboardInterrupt: print('\nEncerrado.')
