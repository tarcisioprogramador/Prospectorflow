#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prospector Standalone — F2/F3: redesign, publicação, proposta, follow-up, contrato e assistente."""
import json, os, re, sqlite3, datetime, subprocess, sys
from urllib.parse import quote
import motor  # reutiliza api(), chat(), extrair_site(), CFG, slugify, regenerar_dashboard

PASTA = motor.PASTA
DB = os.path.join(PASTA, 'prospector.db')
MODELOS = os.path.join(PASTA, 'modelos')

def _cfg_user():
    p = os.path.join(PASTA, 'prospector-config.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}

def _lead(slug):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    r = c.execute('SELECT * FROM leads WHERE slug=?', (slug,)).fetchone(); c.close()
    return dict(r) if r else None

def _leads(status=None):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    q = 'SELECT * FROM leads' + (' WHERE status=?' if status else '') + ' ORDER BY nome'
    rs = c.execute(q, (status,) if status else ()).fetchall(); c.close()
    return [dict(r) for r in rs]

def _upd(slug, **campos):
    c = sqlite3.connect(DB)
    sets = ', '.join('%s=?' % k for k in campos)
    c.execute('UPDATE leads SET %s, atualizado=? WHERE slug=?' % sets,
              list(campos.values()) + [datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), slug])
    c.commit(); c.close()
    motor.regenerar_dashboard()

def _chave():
    return motor.CFG.get('aisa_key', '')

# ---------------- F2: REDESIGN ----------------
REGRAS = """Você é o diretor de arte de um estúdio de design premium. Crie uma landing page de ALTÍSSIMA qualidade — nível estúdio caro — para este cliente. O resultado tem que parecer um site de R$ 5.000, não um template gratuito. Se colocada ao lado do site original, a diferença deve ser CHOCANTE.

FATOS (invioláveis): use SOMENTE serviços, credenciais, nota, avaliações, endereço, telefone e e-mail fornecidos. NADA inventado. Mas o TEXTO é todo REESCRITO com copy de conversão: headline de benefício (não "Especialistas cuidando da sua saúde", e sim algo específico e forte), subheadline que vende, microcopy nos botões.

QUALIDADE VISUAL (obrigatório — capriche de verdade):
- HERO impactante: imagem de fundo do cliente COM overlay em gradiente escuro (linear-gradient) para o texto ficar legível; headline grande (clamp 40-64px), subheadline, e 1 CTA primário destacado. Nada de texto espremido sobre foto clara.
- PALETA sofisticada derivada da marca (1 cor principal + 1 acento + neutros quentes/frios coerentes). Use variáveis CSS (:root).
- SEÇÕES ricas e alternadas (fundo claro/escuro/acento): (1) hero, (2) barra de prova social com a nota do Google em DESTAQUE grande ("4.9 ★ · 2329 avaliações"), (3) serviços/especialidades em CARDS com sombra suave, cantos 16px, ícone ou emoji, e efeito hover, (4) sobre/diferenciais, (5) localização com endereço + link do Google Maps + horários se houver, (6) FAQ curto se der, (7) CTA final forte, (8) rodapé completo com dados reais (registro/CRM se existir).
- TIPOGRAFIA: uma serifada elegante para títulos (Playfair Display, Fraunces ou Lora) + uma sans limpa para corpo (Inter, DM Sans ou Sora). Hierarquia forte.
- ESPAÇAMENTO generoso: 80-120px de respiro vertical entre seções. Grid consistente, alinhamento impecável.
- Micro-toques premium: sombras suaves, transições 0.2s em hovers, bordas arredondadas, botão flutuante de WhatsApp fixo no canto.
- RESPONSIVIDADE TOTAL: perfeita em 360/375/768/1024/1280/1440px, clamp() na tipografia, grid/flex fluidos, ZERO rolagem horizontal.

TÉCNICO: arquivo ÚNICO autocontido, todo o CSS no <head>, só Google Fonts, sem bibliotecas. Todos os CTAs e o botão flutuante apontam para https://wa.me/{whats} com mensagem pré-preenchida contextual. Use as URLs de logo/foto fornecidas.

IMPORTANTE: gere a página COMPLETA e detalhada (várias seções, HTML rico) — não faça uma versão minimalista. Responda APENAS o HTML, começando exatamente em <!DOCTYPE html> e terminando em </html>. Não escreva mais nada."""

def _injetar_editor(html):
    md = open(os.path.join(MODELOS, 'editor-visual.md'), encoding='utf-8').read()
    m = re.search(r'```html\n(.*?)\n```', md, re.S)
    return html.replace('</body>', m.group(1) + '\n</body>') if m else html

def _comparador():
    dados_p = os.path.join(PASTA, 'comparar-dados.json')
    clientes = json.load(open(dados_p, encoding='utf-8')) if os.path.exists(dados_p) else []
    tpl = open(os.path.join(MODELOS, 'comparador-template.html'), encoding='utf-8').read()
    open(os.path.join(PASTA, 'comparar.html'), 'w', encoding='utf-8').write(
        tpl.replace('__CLIENTES__', json.dumps(clientes, ensure_ascii=False)))

def _resolver(termo):
    """Aceita slug exato OU parte do nome do cliente. Retorna o slug ou None."""
    termo = (termo or '')
    # limpar lixo: colchetes, e cortar no primeiro travessão/parêntese (texto de ajuda colado)
    termo = termo.replace('[', ' ').replace(']', ' ')
    for corte in ['—', ' - ', ' – ', '(', ':', '  recria', ' recria']:
        i = termo.find(corte)
        if i > 0: termo = termo[:i]
    termo = termo.strip().lower()
    if not termo: return None
    l = _lead(termo)
    if l: return termo
    import unicodedata
    def _n(s): return ''.join(c for c in unicodedata.normalize('NFD', (s or '').lower()) if unicodedata.category(c) != 'Mn')
    alvo = _n(termo)
    cand = [x for x in _leads() if alvo in _n(x.get('nome')) or alvo in (x.get('slug') or '')]
    if len(cand) == 1: return cand[0]['slug']
    return None

def _resolver_ou_erro(termo):
    s = _resolver(termo)
    if s: return s, None
    ls = _leads()
    opc = '\n'.join('  • %s  →  slug: %s' % (x['nome'], x['slug']) for x in ls[:15]) or '  (nenhum lead ainda)'
    return None, 'Não achei "%s". Diga o slug ou parte do nome de um destes:\n%s' % (termo, opc)

def redesenhar(slug, simular=False):
    l = _lead(slug)
    if not l: return '❌ Lead "%s" não encontrado. Use "listar" pra ver os slugs.' % slug
    pasta_site = os.path.join(PASTA, 'sites', slug)
    os.makedirs(pasta_site, exist_ok=True)
    if simular:
        html = '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>%s</title></head><body><h1>%s — página simulada</h1></body></html>' % (l['nome'], l['nome'])
    else:
        conteudo, _ = motor.extrair_site(l['siteAntigo'], _chave(), False)
        corpo_extra = 'Logo/foto: %s' % (l.get('obs') or '')
        whats = l.get('whatsapp') or ''
        try:
            # redesign pede modelo forte por qualidade — usa o do config, mas garante saída longa
            html = motor.chat(_chave(), REGRAS.replace('{whats}', whats),
                'Cliente: %s (%s, %s). Nota Google: %s (%s avaliações). WhatsApp: %s. Telefone: %s. %s\n\nCONTEÚDO REAL DO SITE ATUAL:\n%s'
                % (l['nome'], l['nicho'], l['cidade'], l['nota'], l['avaliacoes'], whats, l['telefone'], corpo_extra, (conteudo or '')[:9000]),
                json_mode=False, max_tokens=16000)
            html = re.sub(r'^```html\s*|\s*```$', '', html.strip())
            html = re.sub(r'^```\s*|\s*```$', '', html.strip())
        except Exception as e:
            if motor.SEM_SALDO:
                return ('⚠️ Conta AIsa sem saldo — gerei o CONCEITO GRÁTIS (montado a partir do site atual, sem IA).\n\n'
                        + redesenhar_grátis(slug))
            raise
    open(os.path.join(pasta_site, slug + '.html'), 'w', encoding='utf-8').write(html)
    open(os.path.join(pasta_site, slug + '-editor.html'), 'w', encoding='utf-8').write(_injetar_editor(html))
    dados_p = os.path.join(PASTA, 'comparar-dados.json')
    clientes = json.load(open(dados_p, encoding='utf-8')) if os.path.exists(dados_p) else []
    clientes = [c for c in clientes if c.get('slug') != slug]
    clientes.insert(0, {'slug': slug, 'nome': l['nome'], 'antigo': l['siteAntigo']})
    json.dump(clientes, open(dados_p, 'w', encoding='utf-8'), ensure_ascii=False)
    _comparador()
    _upd(slug, status='redesenhado')
    return '✅ %s redesenhado: sites/%s/%s.html + editor + comparar.html atualizados. Próximo: "publicar %s".' % (l['nome'], slug, slug, slug)

def redesenhar_grátis(slug):
    """F2 grátis (sem IA, sem gastar): baixa o site atual do cliente e monta um CONCEITO
    de site moderno a partir do conteúdo real (textos, imagens, contato, cor da marca).
    Gera sites/<slug>/<slug>.html + editor + atualiza o comparativo antes/depois."""
    import html as _html, urllib.parse as _up
    l = _lead(slug)
    if not l: return '❌ Lead "%s" não encontrado. Use "listar" pra ver os slugs.' % slug
    if not l.get('siteAntigo'):
        return '⚠️ Este lead não tem site registrado pra recriar (sem siteAntigo).'
    try:
        _, conteudo = motor._http_get(l['siteAntigo'])
    except Exception as e:
        return '⚠️ Não consegui baixar o site atual (%s) pra montar o conceito grátis.' % e
    if not conteudo or len(conteudo) < 300:
        return '⚠️ O site atual é pequeno demais pra extrair conteúdo — impossível montar um conceito decente.'
    base = l['siteAntigo']
    def _res(u):
        return _up.urljoin(base, u) if u and not u.lower().startswith(('http', 'data:', '//')) else u
    def _txt(s):
        s = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', ' ', s, flags=re.I)
        s = re.sub(r'<[^>]+>', ' ', s)
        return _html.unescape(re.sub(r'\s+', ' ', s)).strip()
    def _grupos(pat, n):
        out = []
        for m in re.findall(pat, conteudo, re.I | re.S)[:n]:
            t = _txt(m)
            if t and len(t) > 2 and t not in out: out.append(t)
        return out
    mt = re.search(r'<title[^>]*>(.*?)</title>', conteudo, re.I | re.S)
    titulo = _txt(mt.group(1)) if mt else (l['nome'] or '')
    marca = re.split(r'\s*[|\u2013\u2014\u2013:]\s*', titulo)[0].strip() or l['nome'] or ''
    desc = ''
    m = re.search(r'<meta\s+(?:name|property)=["\'](?:description|og:description)["\']\s+content=["\']([^"\']+)', conteudo, re.I)
    if not m: m = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+(?:name|property)=["\'](?:description|og:description)["\']', conteudo, re.I)
    if m: desc = _html.unescape(m.group(1)).strip()
    img = ''
    for pat in [r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)',
                r'<img[^>]+src=["\']([^"\']+)']:
        m = re.search(pat, conteudo, re.I)
        if m:
            c = _html.unescape(m.group(1)).strip()
            if c and not c.startswith('data:'):
                img = _res(c); break
    def _filtra(s):
        bl = s.lower().strip()
        return not (len(bl) < 4 or bl in ('home', 'inicio', 'início', 'contato', 'sobre', 'menu', 'fale conosco',
                                          'blog', 'servicos', 'serviços', 'especialidades', 'agendar consulta',
                                          'localizacao', 'localização', 'galeria', 'noticias', 'notícias', 'depoimentos'))
    servicos = [s for s in (_grupos(r'<h2[^>]*>(.*?)</h2>', 8) + _grupos(r'<h3[^>]*>(.*?)</h3>', 8)) if _filtra(s)][:6]
    paragrafos = [t for t in _grupos(r'<p[^>]*>(.*?)</p>', 12) if len(t) > 30][:3]
    emails, tel, zap, ig = motor._extrair_contatos(conteudo)
    email = l.get('email') or (emails[0].lower() if emails else '')
    whats = l.get('whatsapp') or zap or ''
    tel_fmt = l.get('telefone') or tel or ''
    end = ''
    m = re.search(r'((?:Rua|Av\.?|Avenida|Al\.?|Alameda|Praça|Praca|Estrada|Rodovia|Travessa)[^<>\n]{8,80})', conteudo, re.I)
    if m: end = _html.unescape(re.sub(r'\s+', ' ', m.group(1))).strip()
    if not end:
        m = re.search(r'\b\d{5}-?\d{3}\b', conteudo)
        if m: end = 'CEP %s · %s' % (m.group(0), l.get('cidade', ''))
    cor = '#C15F3C'
    freq = {}
    for h in re.findall(r'#([0-9a-fA-F]{6})\b', conteudo):
        h = h.lower()
        if h in ('ffffff', '000000', 'fefefe', 'fafafa', 'f5f5f5', 'efefef', 'e5e5e5', 'cccccc', '888888'):
            continue
        freq[h] = freq.get(h, 0) + 1
    if freq: cor = '#' + max(freq, key=freq.get)

    cidade = (l.get('cidade') or '').title()
    nicho = (l.get('nicho') or '').capitalize()
    whats_msg = _up.quote('Olá! Vim ver a prévia do novo site que preparei — pode me mostrar?', safe='')
    cta = 'https://wa.me/%s?text=%s' % (whats, whats_msg) if whats else ('mailto:%s' % email if email else '#')
    cta_txt = 'Chamar no WhatsApp' if whats else ('Enviar e-mail' if email else 'Fale com a gente')
    sub = desc or (paragrafos[0] if paragrafos else 'Atendimento especializado e atencioso em %s.' % cidade)
    prova = []
    prova.append(('<b>%s</b><span>WhatsApp</span>' % _html.escape(whats), 'zap') if whats else None)
    prova.append(('<b>%s</b><span>e-mail direto</span>' % _html.escape(email), 'email') if email else None)
    prova.append(('<b>%s</b><span>local de atendimento</span>' % _html.escape(cidade), 'cidade') if cidade else None)
    prova = [p for p in prova if p]
    emojis = ['🩺', '💻', '📅', '⭐', '🏥', '🌿', '🦷', '❤️', '💪', '🥗', '🔬', '✨']
    cards = ''.join('<div class="card"><div class="ico">%s</div><h3>%s</h3><p>Atendimento em %s — fale conosco pra saber mais.</p></div>'
                    % (emojis[i % len(emojis)], _html.escape(s), _html.escape(cidade))
                    for i, s in enumerate(servicos)) if servicos else ''
    if not cards:
        cards = '<div class="card"><div class="ico">⭐</div><h3>%s</h3><p>Atendimento dedicado em %s.</p></div>' % (_html.escape(nicho or 'Nossos serviços'), _html.escape(cidade))
    sobre_p = ''.join('<p>%s</p>' % _html.escape(p) for p in paragrafos) or ('<p>%s</p>' % _html.escape('Cuidamos de cada cliente com atenção, qualidade e um atendimento próximo — em %s.' % cidade))
    local_html = ('<b>Endereço</b><p>%s</p>' % _html.escape(end)) if end else '<b>Local</b><p>Atendimento em %s.</p>' % _html.escape(cidade)
    contato = ' · '.join(x for x in [email, whats, tel_fmt, ig and ('@' + ig), end] if x)
    foot = ' · '.join(x for x in [email, whats and ('WhatsApp: ' + whats), ig and ('@' + ig)] if x)
    if not foot: foot = _html.escape(nicho or '')
    prova_html = ''
    if prova:
        prova_html = ' '.join('<div>%s</div>' % p[0] for p in prova)
    else:
        prova_html = '<div><b>%s</b><span>%s em %s</span></div>' % (_html.escape(nicho or 'Atendimento'), _html.escape(nicho or 'especialidade'), _html.escape(cidade))
    hero_bg = ("url('%s') center/cover no-repeat" % img) if img else 'linear-gradient(135deg,#1C1A17 0%,#35312B 100%)'

    def _escurece(hexc, f=0.82):
        try:
            r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
            return '#%02x%02x%02x' % (int(r * f), int(g * f), int(b * f))
        except Exception:
            return hexc
    cor2 = _escurece(cor)
    pagina = TPL_DEMO
    for k, v in [('__MARCA__', _html.escape(marca)), ('__KICKER__', _html.escape((nicho + ' · ' + cidade).upper())),
                 ('__SUB__', _html.escape(sub)), ('__HERO_BG__', hero_bg),
                 ('__PROVA__', prova_html), ('__CARDS__', cards),
                 ('__SERV_LEAD__', _html.escape('Especialidades e serviços de %s em %s.' % (nicho or 'nosso time', cidade))),
                 ('__SOBRE_T__', _html.escape('Conheça o nosso trabalho')),
                 ('__SOBRE_LEAD__', _html.escape('Um pouco sobre o que fazemos e como atendemos.')),
                 ('__SOBRE_P__', sobre_p), ('__LOCAL__', local_html),
                 ('__CONTATO__', _html.escape(contato)), ('__CTA__', cta), ('__CTA_TXT__', _html.escape(cta_txt)),
                 ('__FOOT__', foot), ('__COR__', cor), ('__COR2__', cor2), ('__CIDADE__', _html.escape(cidade))]:
        pagina = pagina.replace(k, str(v))
    pasta_site = os.path.join(PASTA, 'sites', slug)
    os.makedirs(pasta_site, exist_ok=True)
    open(os.path.join(pasta_site, slug + '.html'), 'w', encoding='utf-8').write(pagina)
    open(os.path.join(pasta_site, slug + '-editor.html'), 'w', encoding='utf-8').write(_injetar_editor(pagina))
    dados_p = os.path.join(PASTA, 'comparar-dados.json')
    clientes = json.load(open(dados_p, encoding='utf-8')) if os.path.exists(dados_p) else []
    clientes = [c for c in clientes if c.get('slug') != slug]
    clientes.insert(0, {'slug': slug, 'nome': l['nome'], 'antigo': l['siteAntigo']})
    json.dump(clientes, open(dados_p, 'w', encoding='utf-8'), ensure_ascii=False)
    _comparador()
    _upd(slug, status='redesenhado')
    return ('✅ Conceito grátis gerado para %s (sem gastar crédito): sites/%s/%s.html\n'
            '🔗 comparativo: comparar.html   ·   próxima aba "Comparador" mostra antes/depois.' % (l['nome'], slug, slug))

TPL_DEMO = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__MARCA__ — site renovado (conceito)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;800&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root{--cor1:__COR__;--cor2:__COR2__;--ink:#201D1A;--paper:#F6F3EE;--white:#FFFFFF;--muted:#6E6A63;--line:#E7E2D8}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',-apple-system,'Segoe UI',sans-serif;color:var(--ink);background:var(--paper);line-height:1.65;-webkit-font-smoothing:antialiased}
h1,h2,h3{font-family:'Playfair Display',serif;line-height:1.15}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px}
.badge{position:fixed;top:14px;right:14px;z-index:50;background:#14110E;color:#F2EDE4;font-size:10.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;padding:7px 12px;border-radius:999px;box-shadow:0 4px 14px rgba(0,0,0,.25)}
.hero{position:relative;color:#fff;padding:clamp(90px,14vh,150px) 0;background-image:__HERO_BG__}
.hero::after{content:'';position:absolute;inset:0;background:linear-gradient(112deg,rgba(15,13,11,.88) 18%,rgba(15,13,11,.62) 52%,rgba(15,13,11,.28))}
.hero .wrap{position:relative;z-index:1}
.hero .kicker{display:inline-block;font-size:12.5px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#E8D9B5;border:1px solid rgba(255,255,255,.35);padding:7px 14px;border-radius:999px;margin-bottom:22px}
.hero h1{font-size:clamp(38px,6.4vw,66px);max-width:760px}
.hero p{font-size:clamp(16px,2vw,20px);max-width:580px;margin-top:20px;color:#E7E1D5}
.cta{display:inline-flex;align-items:center;gap:9px;margin-top:30px;padding:16px 30px;border-radius:13px;background:var(--cor1);color:#fff;font-weight:800;font-size:16px;text-decoration:none;transition:.2s;box-shadow:0 10px 26px rgba(0,0,0,.25)}
.cta:hover{transform:translateY(-2px);background:var(--cor2)}
.barra{background:#14110E;color:#E7E1D5}
.barra .wrap{display:flex;gap:34px;flex-wrap:wrap;padding-top:20px;padding-bottom:20px}
.barra b{font-size:15px;color:#fff;display:block}
.barra span{font-size:12px;color:#B9B2A5}
section{padding:clamp(70px,10vh,110px) 0}
h2.sec{font-size:clamp(28px,3.6vw,40px);margin-bottom:8px}
.lead-sec{color:var(--muted);max-width:560px;margin-bottom:36px;font-size:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}
.card{background:var(--white);border:1px solid var(--line);border-radius:18px;padding:26px 24px;box-shadow:0 2px 10px rgba(0,0,0,.04);transition:.2s}
.card:hover{transform:translateY(-4px);box-shadow:0 16px 34px rgba(0,0,0,.10)}
.card .ico{width:46px;height:46px;border-radius:12px;background:var(--cor1);color:#fff;display:flex;align-items:center;justify-content:center;font-size:22px;margin-bottom:16px}
.card h3{font-size:19px;margin-bottom:8px}
.card p{color:var(--muted);font-size:14px}
.sobre{background:var(--white)}
.sobre .dupla{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:center}
.sobre p{color:#57524B;font-size:16px;margin-bottom:14px}
.local{background:#14110E;color:#E7E1D5}
.local .dupla{display:grid;grid-template-columns:1fr 1fr;gap:36px}
.local h2{color:#fff}
.local b{color:#fff;font-size:16px;display:block;margin-top:14px}
.cta-fim{text-align:center}
.cta-fim h2{font-size:clamp(30px,4.4vw,48px);max-width:700px;margin:0 auto}
footer{border-top:1px solid var(--line);background:#EFEBE3;padding:34px 0;font-size:13px;color:var(--muted)}
footer .wrap{display:flex;gap:26px;flex-wrap:wrap;justify-content:space-between;align-items:center}
footer a{color:var(--cor2);font-weight:700;text-decoration:none}
.zap{position:fixed;left:18px;bottom:18px;width:60px;height:60px;border-radius:50%;background:#25D366;display:flex;align-items:center;justify-content:center;font-size:30px;box-shadow:0 10px 26px rgba(0,0,0,.30);text-decoration:none;transition:.2s}
.zap:hover{transform:scale(1.08)}
@media(max-width:760px){.sobre .dupla,.local .dupla{grid-template-columns:1fr}.hero{padding:80px 0}}
</style>
</head>
<body>
<div class="badge">conceito · site renovado</div>
<header class="hero">
 <div class="wrap">
  <span class="kicker">__KICKER__</span>
  <h1>__MARCA__</h1>
  <p>__SUB__</p>
  <a class="cta" href="__CTA__">__CTA_TXT__</a>
 </div>
</header>
<div class="barra"><div class="wrap">__PROVA__</div></div>
<section id="servicos"><div class="wrap">
 <h2 class="sec">O que oferecemos</h2>
 <p class="lead-sec">__SERV_LEAD__</p>
 <div class="grid">__CARDS__</div>
</div></section>
<section class="sobre" id="sobre"><div class="wrap">
 <div class="dupla">
  <div><h2 class="sec">__SOBRE_T__</h2><p class="lead-sec">__SOBRE_LEAD__</p></div>
  <div>__SOBRE_P__</div>
 </div>
</div></section>
<section class="local" id="contato"><div class="wrap">
 <div class="dupla">
  <div><h2 class="sec">Fale com a gente</h2>
   <p class="lead-sec">__CONTATO__</p>
   __LOCAL__
  </div>
  <div style="border-radius:20px;min-height:240px;background:#00000022;padding:26px">
    <b style="color:#fff">Como falar</b>
    <p style="margin-top:12px;color:#C9C1B2">Prefere direto pelo WhatsApp? Resposta rápida, sem cadastro.</p>
    <a class="cta" href="__CTA__">Chamar no WhatsApp ↗</a>
  </div>
 </div>
</div></section>
<section class="cta-fim"><div class="wrap">
 <h2>Pronto pra dar o próximo passo?</h2>
 <a class="cta" href="__CTA__">__CTA_TXT__</a>
</div></section>
<footer><div class="wrap">
 <span>© <span id="ano"></span> __MARCA__ · __CIDADE__</span>
 <span>__FOOT__</span>
</div></footer>
<a class="zap" href="__CTA__" aria-label="WhatsApp">💬</a>
<script>document.getElementById('ano').textContent=new Date().getFullYear();</script>
</body>
</html>
"""

# ---------------- F3: PUBLICAÇÃO ----------------
def publicar(slug, simular=False):
    l = _lead(slug)
    if not l: return '❌ Lead não encontrado.'
    cfgu = _cfg_user(); hg = cfgu.get('hostgator', {}); ass = cfgu.get('assinatura', {})
    if not hg.get('dominio'):
        return '⚠️ Preencha a Conexão HostGator na aba Configurações (domínio, usuário, servidor e senha) antes de publicar.'
    dominio, base = hg['dominio'], hg.get('pastaBase', 'clientes')
    url_nova = 'https://%s/%s/%s/' % (dominio, base, slug)
    # capa
    tpl = open(os.path.join(MODELOS, 'capa-proposta-template.html'), encoding='utf-8').read()
    subs = {'__NOME_CLIENTE__': l['nome'], '__AUTOR__': ass.get('nome') or 'Seu Nome',
            '__AUTOR_URL__': quote(ass.get('nome') or 'designer'), '__APRESENTACAO__': ass.get('apresentacao') or '',
            '__WHATSAPP__': ass.get('whatsapp') or '', '__URL_NOVA__': url_nova, '__URL_ANTIGA__': l['siteAntigo'] or ''}
    for k, v in subs.items(): tpl = tpl.replace(k, v)
    pasta_site = os.path.join(PASTA, 'sites', slug)
    os.makedirs(pasta_site, exist_ok=True)
    open(os.path.join(pasta_site, 'proposta.html'), 'w', encoding='utf-8').write(tpl)
    # fila do publicador
    fila = os.path.join(PASTA, 'fila-publicacao.txt')
    with open(fila, 'a', encoding='utf-8') as f:
        f.write('sites/%s/%s.html|public_html/%s/%s/index.html\n' % (slug, slug, base, slug))
        f.write('sites/%s/proposta.html|public_html/%s/%s/proposta.html\n' % (slug, base, slug))
    _upd(slug, urlNova=url_nova)
    return ('📤 Fila de publicação criada pra %s. O publicador automático sobe em até 1 min (se instalado) — ou dê 2 cliques no publicar-agora. '
            'Depois me diga "publicou %s" que eu marco no CRM. URL: %s' % (l['nome'], slug, url_nova))

def marcar_publicado(slug):
    l = _lead(slug)
    if not l: return '❌ Lead não encontrado.'
    _upd(slug, status='publicado')
    return '✅ %s marcado como publicado (%s). Próximo: "proposta %s".' % (l['nome'], l.get('urlNova'), slug)

# ---------------- F3: PROPOSTA + FOLLOW-UP ----------------
def _gmail_url(para, assunto, corpo):
    return 'https://mail.google.com/mail/?view=cm&fs=1&to=%s&su=%s&body=%s' % (quote(para), quote(assunto), quote(corpo))

def proposta(slug, simular=False):
    l = _lead(slug)
    if not l: return '❌ Lead não encontrado.'
    if not l.get('email'): return '⚠️ Esse lead não tem e-mail — aborde pelo WhatsApp: %s' % (l.get('whatsapp') or l.get('telefone'))
    capa = (l.get('urlNova') or '') + 'proposta.html'
    if simular:
        assunto = '%s, preparei algo sobre o seu site' % l['nome'].split()[0]
        corpo = 'Olá! Vi suas avaliações no Google (nota %s) e preparei uma nova versão do seu site: %s\n\nAbraço' % (l['nota'], capa)
    else:
        r = motor.chat(_chave(),
            'Escreva e-mail de prospecção B2B curto (120-180 palavras) em PT-BR. REGRAS: elogio específico com a nota/avaliações reais; 1-2 defeitos objetivos do site como oportunidade; UM único link (a capa); zero preço; zero palavras de vendedor (grátis, promoção, imperdível); assunto-pergunta ≤60 caracteres com o nome; texto que pareça escrito à mão. Responda APENAS JSON {"assunto": "...", "corpo": "..."}',
            'Cliente: %s (%s, %s). Nota %s com %s avaliações. Defeito do site: %s. Link da capa: %s. Assinatura: %s — %s, WhatsApp %s'
            % (l['nome'], l['nicho'], l['cidade'], l['nota'], l['avaliacoes'], l['motivo'], capa,
               _cfg_user().get('assinatura', {}).get('nome',''), _cfg_user().get('assinatura', {}).get('apresentacao',''), _cfg_user().get('assinatura', {}).get('whatsapp','')))
        assunto, corpo = r['assunto'], r['corpo']
    json.dump({'assunto': assunto, 'corpo': corpo}, open(os.path.join(PASTA, 'sites', slug, 'proposta-email.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    _upd(slug, status='proposta', dataProposta=datetime.date.today().isoformat())
    return ('✉️ Proposta pronta pra %s!\n\nASSUNTO: %s\n\n%s\n\n👉 ABRIR NO SEU GMAIL (já preenchido, é só revisar e enviar):\n%s'
            % (l['nome'], assunto, corpo, _gmail_url(l['email'], assunto, corpo)))

def followups(simular=False):
    limite = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    pend = [l for l in _leads('proposta') if (l.get('dataProposta') or '9999') <= limite and 'follow-up' not in (l.get('obs') or '').lower()]
    if not pend: return '✅ Nenhum follow-up pendente (propostas com 3+ dias sem resposta e sem follow-up).'
    out = []
    for l in pend:
        corpo = ('Olá, %s! Te escrevi há alguns dias sobre a nova versão do seu site — conseguiu ver a página? %sproposta.html\n\nQualquer dúvida estou por aqui. Abraço!'
                 % (l['nome'].split()[0], l.get('urlNova') or ''))
        assunto = 'Conseguiu ver a página, %s?' % l['nome'].split()[0]
        _upd(l['slug'], obs=((l.get('obs') or '') + ' | Follow-up enviado em %s' % datetime.date.today().isoformat()).strip(' |'))
        out.append('• %s → %s' % (l['nome'], _gmail_url(l['email'], assunto, corpo)))
    return '🔔 %d follow-up(s) pronto(s) — abre cada link, revisa e envia:\n' % len(pend) + '\n'.join(out)

# ---------------- F3: CONTRATO ----------------
def contrato(slug, simular=False):
    l = _lead(slug)
    if not l: return '❌ Lead não encontrado.'
    if l.get('status') != 'fechado': return '⚠️ %s ainda não está como FECHADO no CRM. Diga: "fechou %s por 700" primeiro.' % (l['nome'], slug)
    ct = _cfg_user().get('contratante', {})
    dados_base = {'NOME_CLIENTE': l['nome'], 'NOME_NEGOCIO': l['nome'], 'CIDADE_UF_CLIENTE': l.get('cidade') or 'preencher',
        'ENDERECO_CLIENTE': l.get('endCliente') or 'preencher', 'CPF_CNPJ_CLIENTE': l.get('docCliente') or 'preencher',
        'NOME_PRESTADOR': ct.get('nome') or 'preencher', 'CIDADE_UF_PRESTADOR': ct.get('cidadeUf') or 'preencher',
        'ENDERECO_PRESTADOR': ct.get('endereco') or 'preencher', 'CPF_CNPJ_PRESTADOR': ct.get('cpfCnpj') or 'preencher',
        'URL_SITE_ANTIGO': l.get('siteAntigo') or '-', 'URL_PUBLICADA': l.get('urlNova') or '-',
        'VALOR': ('%.2f' % (l.get('valor') or 0)).replace('.', ','), 'MANUTENCAO': l.get('manutencao') or 0}
    if simular:
        campos = {**dados_base, 'CPF_CNPJ_CLIENTE_LABEL': 'inscrito(a) no CPF', 'CPF_CNPJ_PRESTADOR_LABEL': 'inscrito(a) no CPF',
            'VALOR_EXTENSO': 'setecentos reais', 'FORMA_PAGAMENTO': '50% na assinatura e 50% na entrega, via Pix',
            'PRAZO_ENTREGA': '7 (sete) dias úteis', 'RODADAS_AJUSTES': '1 (uma)', 'CIDADE_FORO': dados_base['CIDADE_UF_CLIENTE'],
            'CIDADE_ASSINATURA': dados_base['CIDADE_UF_CLIENTE'], 'DATA_EXTENSO': datetime.date.today().strftime('%d/%m/%Y'),
            'CLAUSULA_MANUTENCAO': '', 'N_CONTEUDO': '4', 'N_HOSPEDAGEM': '5', 'N_RESCISAO': '6', 'N_FORO': '7', 'PLACEHOLDERS': ''}
    else:
        campos = motor.chat(_chave(),
            'Preencha os placeholders de um contrato de prestação de serviço (criação de site) em PT-BR. Regras: VALOR_EXTENSO por extenso; labels "inscrito(a) no CPF" ou "inscrita no CNPJ" conforme o documento; se houver manutenção mensal > 0, CLAUSULA_MANUTENCAO = "<h2>Cláusula 4ª — Da manutenção mensal</h2><p>O CONTRATANTE contrata ainda o serviço de manutenção mensal da página (hospedagem, pequenas atualizações de texto/imagens e suporte), pelo valor de R$ [valor] mensais, com vigência a partir da publicação e renovação automática mensal.</p>" e N_CONTEUDO=5,N_HOSPEDAGEM=6,N_RESCISAO=7,N_FORO=8; senão CLAUSULA_MANUTENCAO="" e N_CONTEUDO=4..N_FORO=7. FORMA_PAGAMENTO padrão "50%% na assinatura e 50%% na entrega, via Pix". PRAZO_ENTREGA "7 (sete) dias úteis". RODADAS_AJUSTES "1 (uma)". DATA_EXTENSO = data de hoje por extenso. PLACEHOLDERS="". Campos faltantes = "preencher". Responda APENAS JSON com TODAS as chaves: CPF_CNPJ_CLIENTE_LABEL, CPF_CNPJ_PRESTADOR_LABEL, VALOR_EXTENSO, FORMA_PAGAMENTO, PRAZO_ENTREGA, RODADAS_AJUSTES, CIDADE_FORO, CIDADE_ASSINATURA, DATA_EXTENSO, CLAUSULA_MANUTENCAO, N_CONTEUDO, N_HOSPEDAGEM, N_RESCISAO, N_FORO, PLACEHOLDERS.',
            json.dumps({**dados_base, 'hoje': datetime.date.today().isoformat()}, ensure_ascii=False))
        campos = {**dados_base, **campos}
        if dados_base['MANUTENCAO']:
            campos['CLAUSULA_MANUTENCAO'] = campos.get('CLAUSULA_MANUTENCAO', '').replace('[valor]', ('%.2f' % dados_base['MANUTENCAO']).replace('.', ','))
    campos['VALOR_MANUTENCAO'] = ('%.2f' % (dados_base['MANUTENCAO'] or 0)).replace('.', ',')
    if dados_base['MANUTENCAO']:
        campos['TEXTO_HOSPEDAGEM'] = 'Enquanto vigorar a manutenção mensal, a hospedagem da página é de responsabilidade do(a) CONTRATADO(A).'
    else:
        campos['TEXTO_HOSPEDAGEM'] = 'A página será entregue publicada; a partir da entrega, a contratação e renovação de hospedagem e domínio próprios são de responsabilidade do CONTRATANTE, com suporte do(a) CONTRATADO(A) na migração, se solicitado.'
    tpl = open(os.path.join(MODELOS, 'contrato-template.html'), encoding='utf-8').read()
    for k, v in campos.items(): tpl = tpl.replace('{{%s}}' % k, str(v))
    pasta_site = os.path.join(PASTA, 'sites', slug); os.makedirs(pasta_site, exist_ok=True)
    open(os.path.join(pasta_site, 'contrato-%s.html' % slug), 'w', encoding='utf-8').write(tpl)
    docx_msg = ''
    try:
        dj = os.path.join(pasta_site, 'contrato-dados.json')
        json.dump(campos, open(dj, 'w', encoding='utf-8'), ensure_ascii=False)
        r = subprocess.run([sys.executable, os.path.join(MODELOS, 'gerar-docx.py'), dj, os.path.join(pasta_site, 'contrato-%s.docx' % slug)],
                           capture_output=True, text=True, timeout=60)
        docx_msg = ' + Word travado gerado' if r.returncode == 0 else ' (Word não gerado: instale python-docx com "pip install python-docx")'
    except Exception:
        docx_msg = ' (Word não gerado: instale python-docx)'
    _upd(slug, contratoStatus='enviado', contratoEm=datetime.date.today().isoformat())
    return '📄 Contrato do %s gerado%s — veja na aba Contratos do painel (folha pra imprimir). Campos faltantes estão como "preencher".' % (l['nome'], docx_msg)

# ---------------- FECHAMENTO / FINANCEIRO / LISTA ----------------
def fechar(slug, valor, manutencao=None):
    l = _lead(slug)
    if not l: return '❌ Lead não encontrado.'
    _upd(slug, status='fechado', valor=valor, manutencao=manutencao)
    return '🎉 %s FECHADO por R$ %.2f%s! Próximo: "contrato %s".' % (l['nome'], valor, (' + R$ %.2f/mês' % manutencao) if manutencao else '', slug)

def financeiro():
    c = sqlite3.connect(DB)
    total, recebido, mrr, n = c.execute("SELECT COALESCE(SUM(valor),0), COALESCE(SUM(CASE WHEN pago=1 THEN valor ELSE 0 END),0), COALESCE(SUM(manutencao),0), COUNT(*) FROM leads WHERE status='fechado'").fetchone()
    c.close()
    return '💰 Financeiro: %d fechados · R$ %.2f fechado · R$ %.2f recebido · R$ %.2f a receber · MRR R$ %.2f · projeção 12m R$ %.2f' % (n, total, recebido, total - recebido, mrr, total + mrr * 12)

def listar():
    ls = _leads()
    if not ls: return 'CRM vazio — comece com: prospectar [nicho] em [cidade]'
    return 'Seus leads (use o nome OU o slug nos comandos):\n' + '\n'.join('• %s  —  %s%s  ·  slug: %s' % (l['nome'], l['status'], (' · R$ %.0f' % l['valor']) if l.get('valor') else '', l['slug']) for l in ls)

# ---------------- ASSISTENTE ----------------
AJUDA = ('Comandos que eu entendo:\n• prospectar [nicho] em [cidade]  (ex.: prospectar 5 nutricionista em São Paulo)\n'
         '• listar  — mostra seus leads por score\n• followups  — quem contatar de novo\n• ajuda\n\n'
         'Dica: dá pra prospectar direto pelo formulário no topo da aba Leads, sem digitar comando.')

def assistente(msg, simular=False):
    m = msg.lower().strip()
    try:
        if m.startswith('prospectar'):
            r = re.search(r'prospectar\s+(?:(\d+)\s+)?(.+?)\s+em\s+(.+)', m)
            if not r: return 'Formato: prospectar [nicho] em [cidade]'
            qtd = int(r.group(1)) if r.group(1) else motor.CFG['prospeccao'].get('leads_por_busca', 5)
            motor.CFG['prospeccao']['leads_por_busca'] = qtd
            nicho, cidade = r.group(2), r.group(3)
            import io, contextlib
            if simular:
                buf0 = io.StringIO()
                with contextlib.redirect_stdout(buf0):
                    sys.argv = ['motor.py', nicho, cidade, '--simular']
                    motor.main()
                return buf0.getvalue()
            # tenta o modo real (pago); se a conta estiver sem saldo, cai pro modo GRÁTIS (sites reais)
            motor.SEM_SALDO = False
            motor.AVISO[:] = []
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                sys.argv = ['motor.py', nicho, cidade]
                motor.main()
            resp = buf.getvalue()
            if motor.AVISO:
                resp = '⚠️ ' + '\n'.join('• %s' % a for a in motor.AVISO) + '\n\n' + resp
            if '0 leads no dossiê' in resp and motor.SEM_SALDO:
                buf2 = io.StringIO()
                with contextlib.redirect_stdout(buf2):
                    motor.main_grátis(nicho, cidade, qtd)
                resp = ('⚠️ Conta AIsa sem saldo — busquei leads REAIS em sites públicos (modo grátis, sem custo).\n'
                        'Recarregar em aisa.one dá também a nota do Google e a análise por IA.\n\n'
                        + buf2.getvalue())
            return resp
        if m.startswith('redesenhar') or m.startswith('demo'):
            termo = msg[len('redesenhar'):] if m.startswith('redesenhar') else msg[len('demo'):]
            s, err = _resolver_ou_erro(termo); return err or redesenhar(s, simular)
        if m.startswith('publicar'):
            s, err = _resolver_ou_erro(msg[len('publicar'):]); return err or publicar(s, simular)
        if m.startswith('publicou'):
            s, err = _resolver_ou_erro(msg[len('publicou'):]); return err or marcar_publicado(s)
        if m.startswith('proposta'):
            s, err = _resolver_ou_erro(msg[len('proposta'):]); return err or proposta(s, simular)
        if m.startswith('followup'): return followups(simular)
        if m.startswith('fechou'):
            r = re.search(r'fechou\s+(\S+)\s+por\s+r?\$?\s*([\d.,]+)', m)
            if not r: return 'Formato: fechou [nome] por [valor] (e [valor] de manutenção)'
            rm = re.search(r'(?:manuten\w*|mensal)\D{0,15}?([\d.,]+)', m[r.end():])
            v = float(r.group(2).replace('.', '').replace(',', '.')) if ',' in r.group(2) else float(r.group(2))
            mn = None
            if rm:
                g = rm.group(1)
                mn = float(g.replace('.', '').replace(',', '.')) if ',' in g else float(g)
            s = _resolver(r.group(1))
            if not s:
                _s, err = _resolver_ou_erro(r.group(1)); return err
            return fechar(s, v, mn)
        if m.startswith('contrato'):
            s, err = _resolver_ou_erro(msg[len('contrato'):]); return err or contrato(s, simular)
        if m.startswith('financeiro'): return financeiro()
        if m.startswith('listar'): return listar()
        if m in ('ajuda', 'help', '?'): return AJUDA
        if simular or not _chave(): return 'Não entendi. ' + AJUDA
        try:
            return motor.chat(_chave(), 'Você é o assistente do Prospector (prospecção e venda de sites). Responda curto em PT-BR. Se o usuário quiser uma ação, indique o comando: ' + AJUDA, msg, json_mode=False)
        except Exception as _e:
            return ('⚠️ A conta AIsa está sem saldo (%s) — recarregue em aisa.one pra eu responder livremente. '
                    'Enquanto isso, posso: %s' % (_e, AJUDA.replace('\n', ' ')))
    except Exception as e:
        import traceback, datetime
        try:
            with open(os.path.join(PASTA, 'motor-log.txt'), 'a', encoding='utf-8') as _f:
                _f.write('\n=== %s ASSISTENTE %s ===\n%s\n' % (datetime.datetime.now(), e, traceback.format_exc()))
        except Exception: pass
        return '⚠️ Erro: %s (detalhe em motor-log.txt)' % e

if __name__ == '__main__':
    _args = [a for a in sys.argv[1:] if a != '--simular']
    print(assistente(' '.join(_args) or 'ajuda', simular='--simular' in sys.argv))