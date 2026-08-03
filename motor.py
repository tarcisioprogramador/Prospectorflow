#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prospector Standalone — F1: motor de prospecção via AIsa (sem Claude, sem ChatGPT)
Uso:   python motor.py "nutricionista" "São Paulo"            (usa a chave do config)
       python motor.py "nutricionista" "São Paulo" --simular  (sem chave, dados de exemplo)
Fluxo: AIsa DataForSEO (negócios nota alta) -> filtros -> AIsa Tavily (site) -> AIsa Chat (julgamento) -> prospector.db + dashboard
"""
import json, os, re, sqlite3, sys, datetime, unicodedata
import urllib.request

# Windows: console em cp1252 estoura com emoji -> força UTF-8 (sem quebrar pipe/stringIO)
for _stream in (getattr(sys, 'stdout', None), getattr(sys, 'stderr', None)):
    try:
        if _stream and hasattr(_stream, 'reconfigure'):
            _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PASTA = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(PASTA, 'config-standalone.json'), encoding='utf-8'))
BASE_APIS = 'https://api.aisa.one/apis/v1'
BASE_CHAT = 'https://api.aisa.one/v1'
CUSTO = {'usd': 0.0, 'chamadas': 0}
AVISO = []  # avisos (ex.: sem saldo) que sobem pro painel
SEM_SALDO = False  # True quando o AIsa respondeu "sem saldo" — o painel cai pro modo grátis

def _marca_sem_saldo(texto):
    global SEM_SALDO
    if any(x in str(texto).lower() for x in ('balance', 'recharge', 'payment required')):
        SEM_SALDO = True

def api(url, corpo, chave):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + chave, 'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            CUSTO['chamadas'] += 1
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try: _marca_sem_saldo(e.read().decode('utf-8', 'replace'))
        except Exception: pass
        raise

DOMINIOS_PROIBIDOS = ('instagram.', 'facebook.', 'linktr.ee', 'linkin.bio', 'wa.me', 'whatsapp.',
                      'doctoralia', 'ifood', 'sites.google', 'bit.ly', 'youtube.', 'tiktok.')
# agregadores/diretórios — pular na busca grátis (queremos site individual do negócio)
DIRETORIOS = ('doctoralia', 'tuasaude', 'dietbox', 'dovivo', 'guiamais', 'yellow', 'paginas.amarelas',
              'tripadvisor', 'ecadastro', 'cnpj', 'google.com', 'guia.', 'catalogo', 'top10', 'melhores',
              'ranking', 'empresas', 'wikimapia', 'linkedin', 'reclameaqui', 'facebook',
              'boaconsulta', 'classisp', 'fitlocal', 'nutrimatch', 'crn3', 'nutriconsulta', 'clinicasim',
              'conselho', 'solutudo', 'finda', 'guialocal', 'dentmap', 'odontoavalia')
CIDADES = {  # lat, long das capitais/grandes cidades; outras vão pro geocode via LLM
 'sao paulo': (-23.55052, -46.633308), 'guarulhos': (-23.454, -46.5333), 'campinas': (-22.9099, -47.0626),
 'rio de janeiro': (-22.906847, -43.172896), 'belo horizonte': (-19.916681, -43.934493),
 'curitiba': (-25.4284, -49.2733), 'porto alegre': (-30.0346, -51.2177), 'salvador': (-12.9777, -38.5016),
 'brasilia': (-15.7975, -47.8919), 'fortaleza': (-3.7319, -38.5267), 'recife': (-8.0476, -34.877),
 'goiania': (-16.6869, -49.2648), 'santos': (-23.9608, -46.3336), 'osasco': (-23.5325, -46.7917),
 'taboao da serra': (-23.6019, -46.7526), 'sorocaba': (-23.5015, -47.4526), 'florianopolis': (-27.5954, -48.548)}

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')

MODELOS_FALLBACK = ['gpt-4.1', 'gpt-4o', 'claude-sonnet-4', 'gemini-2.5-flash']
def chat(chave, sistema, usuario, json_mode=True, max_tokens=None):
    import urllib.error
    tentativas = [CFG.get('modelo', 'gpt-4.1')] + [m for m in MODELOS_FALLBACK if m != CFG.get('modelo')]
    ultimo_erro = None
    r = None
    for modelo in tentativas:
        corpo = {'model': modelo, 'messages': [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}]}
        if max_tokens: corpo['max_tokens'] = max_tokens
        try:
            r = api(BASE_CHAT + '/chat/completions', corpo, chave)
            break
        except urllib.error.HTTPError as e:
            ultimo_erro = e
            if e.code in (404, 400):  # modelo inexistente -> tenta o próximo
                continue
            raise
    if r is None:
        raise RuntimeError('Nenhum modelo do gateway respondeu. Verifique a chave/saldo AIsa. Último erro: %s' % ultimo_erro)
    ch = (r or {}).get('choices') or []
    if not ch:
        raise RuntimeError('Resposta vazia do modelo (verifique saldo/chave AIsa).')
    txt = (ch[0].get('message') or {}).get('content') or ''
    if json_mode:
        m = re.search(r'\{.*\}', txt, re.S)
        return json.loads(m.group(0)) if m else {}
    return txt

def api_dfs(url, tarefa, chave):
    """DataForSEO via AIsa exige o corpo como ARRAY de tasks: [ {...} ]."""
    return api(url, [tarefa], chave)

def api_get(url, chave):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + chave}, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            CUSTO['chamadas'] += 1
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try: _marca_sem_saldo(e.read().decode('utf-8', 'replace'))
        except Exception: pass
        raise

def achar_handle_ig(lead, conteudo):
    """Descobre o @ do Instagram: da URL do perfil, do site (link instagram.com/...) ou do conteúdo."""
    import re as _re
    fontes = [lead.get('siteAntigo') or '', lead.get('url') or '', conteudo or '']
    for txt in fontes:
        m = _re.search(r'instagram\.com/([A-Za-z0-9_.]+)', txt)
        if m:
            h = m.group(1).strip('/').lower()
            if h not in ('p', 'reel', 'explore', 'accounts', 'stories'):
                return h
    return None

def enriquecer_instagram(handle, chave, simular):
    """Perfil do IG: seguidores, posts, se é ativo, categoria. So os campos uteis."""
    if not handle: return None
    if simular:
        return {'handle': handle, 'seguidores': 3400, 'posts': 210, 'ativo': True, 'categoria': 'Health/Beauty', 'ultimo_post_dias': 4}
    try:
        r = api_get(BASE_APIS + '/instagram/profile?handle=' + handle + '&trim=true', chave)
        u = ((r or {}).get('data') or {}).get('user') or {}
        seg = (u.get('edge_followed_by') or {}).get('count')
        posts = (u.get('edge_owner_to_timeline_media') or {}).get('count')
        # ultimo post: pega o timestamp mais recente da timeline
        ultimo_dias = None
        edges = (u.get('edge_owner_to_timeline_media') or {}).get('edges') or []
        if edges:
            ts = (edges[0].get('node') or {}).get('taken_at_timestamp')
            if ts:
                ultimo_dias = int((datetime.datetime.now().timestamp() - ts) / 86400)
        return {'handle': handle, 'seguidores': seg, 'posts': posts,
                'ativo': (ultimo_dias is not None and ultimo_dias <= 30),
                'categoria': u.get('category_name'), 'ultimo_post_dias': ultimo_dias}
    except Exception as e:
        _log_erro(e) if '_log_erro' in globals() else None
        return {'handle': handle, 'seguidores': None, 'posts': None, 'ativo': None, 'categoria': None, 'ultimo_post_dias': None}

def score_lead(lead, ig, chave, simular):
    """Score 0-100 + temperatura + abordagem, cruzando nota Google, site ruim e presença no IG."""
    base = 0
    # nota alta = negócio bom (0-30)
    base += min(30, int(((lead.get('nota') or 0) - 4.0) * 30))
    # muitas avaliações = movimento/porte (0-25)
    base += min(25, int((lead.get('avaliacoes') or 0) / 8))
    # site ruim mas EXISTE = dor clara (0-20)
    if lead.get('siteAntigo'): base += 20
    # IG ativo + audiência = se importa com imagem e tem grana (0-25)
    if ig:
        if ig.get('ativo'): base += 12
        s = ig.get('seguidores') or 0
        base += min(13, int(s / 400))
    base = max(0, min(100, base))
    temp = 'quente' if base >= 70 else ('morno' if base >= 45 else 'frio')
    if simular:
        return base, temp, 'E-mail com elogio à nota %s e print do site atual; se responder, agenda call.' % lead.get('nota')
    try:
        r = chat(chave,
            'Você é estrategista de vendas de sites. Dado um lead, sugira em 1 frase curta a MELHOR abordagem (canal e gancho). Responda APENAS JSON {"abordagem":"..."}.',
            'Lead: %s (%s). Nota Google %s (%s aval). Site: %s. Instagram: %s. Motivo do site ser fraco: %s.' % (
                lead.get('nome'), lead.get('nicho'), lead.get('nota'), lead.get('avaliacoes'),
                lead.get('siteAntigo') or 'sem site', json.dumps(ig, ensure_ascii=False) if ig else 'sem IG', lead.get('motivo')))
        return base, temp, (r or {}).get('abordagem') or ''
    except Exception:
        return base, temp, ''

def coordenadas(cidade, chave, simular):
    c = norm(cidade.split(',')[0].split('-')[0].strip())
    if c in CIDADES: return CIDADES[c]
    if simular: return CIDADES['sao paulo']
    try:
        r = chat(chave, 'Responda APENAS JSON.', 'Coordenadas do centro de "%s", Brasil. JSON: {"lat": -00.0, "lng": -00.0}' % cidade)
        if isinstance(r, dict) and 'lat' in r and 'lng' in r:
            return (r['lat'], r['lng'])
    except Exception:
        pass
    try:  # geocoder gratuito (OpenStreetMap) como fallback — não depende de saldo AIsa
        import urllib.parse
        q = urllib.parse.quote(cidade + ', Brasil')
        req = urllib.request.Request(
            'https://nominatim.openstreetmap.org/search?q=%s&format=json&limit=1&countrycodes=br' % q,
            headers={'User-Agent': 'prospector-local/1.0'})
        with urllib.request.urlopen(req, timeout=25) as _r:
            d = json.loads(_r.read().decode('utf-8'))
            if d:
                return (float(d[0]['lat']), float(d[0]['lon']))
    except Exception:
        pass
    AVISO.append('Não achei as coordenadas de "%s" — usando o centro de São Paulo.' % cidade)
    return CIDADES['sao paulo']

def categorias_gmb(nicho, chave, simular):
    if simular: return ['nutritionist']
    try:
        r = chat(chave, 'Você conhece as categorias do Google My Business (identificadores em inglês). Responda APENAS JSON.',
                 'Até 3 categorias GMB mais prováveis para o nicho "%s" no Brasil. JSON: {"categorias": ["slug1"]}' % nicho)
        cats = (r or {}).get('categorias')
        return cats if cats else [nicho]
    except Exception:
        return [nicho]

def _log_erro(e):
    import traceback, datetime
    with open(os.path.join(PASTA, 'motor-log.txt'), 'a', encoding='utf-8') as f:
        f.write('\n=== %s %s ===\n%s\n' % (datetime.datetime.now(), e, traceback.format_exc()))

def buscar_negocios(nicho, cidade, chave, simular):
    if simular:
        return [
            {'title': 'Dra. Exemplo Nutri', 'category': 'Nutricionista', 'phone': '+5511999990001',
             'url': 'https://www.exemplo-nutri-simulada.com.br', 'domain': 'exemplo-nutri-simulada.com.br',
             'rating': {'value': 4.9, 'votes_count': 87}, 'address': 'Av. Paulista, 1000', 'city': cidade,
             'logo': '', 'main_image': '', 'place_topics': {'atendimento': 21, 'resultado': 13}},
            {'title': 'Clinica Sem Site', 'category': 'Nutricionista', 'phone': '+5511999990002',
             'url': None, 'domain': None, 'rating': {'value': 4.8, 'votes_count': 55}, 'address': 'Rua B, 2', 'city': cidade},
            {'title': 'Studio Nutricao Insta', 'category': 'Nutricionista', 'phone': '+5511999990003',
             'url': 'https://instagram.com/studionutri', 'domain': 'instagram.com',
             'rating': {'value': 5.0, 'votes_count': 44}, 'address': 'Rua C, 3', 'city': cidade}]
    p = CFG['prospeccao']
    itens = []
    # ---- Metodo 1: Google Maps SERP (busca por keyword, como uma pessoa faria) ----
    try:
        lat, lng = coordenadas(cidade, chave, simular)
        corpo = {'keyword': '%s em %s' % (nicho, cidade),
                 'location_coordinate': '%.6f,%.6f,%d' % (lat, lng, p.get('raio_km', 25)),
                 'language_code': 'pt', 'depth': 40}
        r = api_dfs(BASE_APIS + '/dataforseo/serp/google/maps/live/advanced', corpo, chave)
        if isinstance(r, dict) and r.get('error'):
            _marca_sem_saldo(r.get('error'))
            AVISO.append('Google Maps sem saldo no AIsa: %s' % r.get('error'))
        else:
            for t2 in (r.get('tasks') or []):
                CUSTO['usd'] += t2.get('cost') or 0
                if t2.get('status_code') not in (20000, 20001) and t2.get('status_message'):
                    AVISO.append('Google Maps: %s' % t2.get('status_message'))
                for res in (t2.get('result') or []):
                    for it in (res.get('items') or []):
                        if (it.get('type') or '') not in ('maps_search', 'local_pack', ''):
                            continue
                        rating = it.get('rating') or {}
                        itens.append({
                            'title': it.get('title'), 'category': it.get('category') or nicho,
                            'phone': it.get('phone'), 'url': it.get('url') or it.get('domain'),
                            'domain': it.get('domain'), 'rating': {'value': rating.get('value'), 'votes_count': rating.get('votes_count')},
                            'address': it.get('address'), 'city': cidade,
                            'logo': it.get('logo') or '', 'main_image': it.get('main_image') or ''})
    except Exception as e:
        _log_erro(e)
    # filtro de nota/avaliacoes no cliente
    def _ok(x):
        rt = x.get('rating') or {}
        return (rt.get('value') or 0) >= p['nota_minima'] and (rt.get('votes_count') or 0) >= p['avaliacoes_minimas']
    itens = [x for x in itens if x.get('title') and _ok(x)]
    itens.sort(key=lambda x: (x.get('rating') or {}).get('votes_count') or 0, reverse=True)
    if itens:
        return itens
    # ---- Metodo 2 (fallback): Business Listings por coordenada+categoria ----
    try:
        lat, lng = coordenadas(cidade, chave, simular)
        corpo = {'categories': categorias_gmb(nicho, chave, simular),
                 'location_coordinate': '%.6f,%.6f,%d' % (lat, lng, p.get('raio_km', 25)),
                 'filters': [['rating.value', '>=', p['nota_minima']], 'and', ['rating.votes_count', '>=', p['avaliacoes_minimas']]],
                 'order_by': ['rating.votes_count,desc'], 'limit': 40}
        r = api_dfs(BASE_APIS + '/dataforseo/business_data/business_listings/search/live', corpo, chave)
        if isinstance(r, dict) and r.get('error'):
            AVISO.append('Listagens sem saldo no AIsa: %s' % r.get('error'))
        else:
            for t2 in (r.get('tasks') or []):
                CUSTO['usd'] += t2.get('cost') or 0
                if t2.get('status_code') not in (20000, 20001) and t2.get('status_message'):
                    AVISO.append('Listagens: %s' % t2.get('status_message'))
                for res in (t2.get('result') or []):
                    itens += res.get('items') or []
    except Exception as e:
        _log_erro(e)
    if not itens and not simular:
        AVISO.append('Nenhum resultado do Google — a conta AIsa está sem saldo ou os filtros estão apertados demais.')
    return itens

# ============ BUSCA GRÁTIS (sem saldo AIsa): DuckDuckGo + site direto ============
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
      'Accept-Language': 'pt-BR,pt;q=0.9'}

def _http_get(url, timeout=25):
    import urllib.parse
    if url.startswith('//'): url = 'https:' + url
    if not url.lower().startswith('http'): url = 'https://' + url
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'replace')

def _decodificar_ddg(href):
    """O DuckDuckGo HTML redireciona via //duckduckgo.com/l/?uddg=<url>&rut=..."""
    m = re.search(r'uddg=([^&]+)', href)
    return urllib.parse.unquote(m.group(1)) if m else href

def _extrair_contatos(html):
    emails = list(dict.fromkeys(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', html)))
    tel = None
    m = re.search(r'(?:\+?55[\s.-]?)?(?:\(\d{2}\)[\s.-]?|\d{2}[\s.-]?)(?:9\d{4}[\s.-]?\d{4}|\d{4}[\s.-]?\d{4})', html)
    if m: tel = re.sub(r'\D', '', m.group(0))
    ig = None
    m = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', html)
    if m:
        h = m.group(1).strip('/').lower()
        if h not in ('p', 'reel', 'explore', 'accounts', 'stories', 'share', 'tag', 'p/ctig'): ig = h
    zap = None
    if tel:
        if len(tel) == 11 and tel.isdigit(): zap = '55' + tel
        elif len(tel) == 13 and tel.startswith('55'): zap = tel
        elif len(tel) == 12 and tel.startswith('55'): zap = tel
    return emails, tel, zap, ig

def buscar_negocios_grátis(nicho, cidade, quantidade):
    """Acha negócios REAIS sem gastar nada: DuckDuckGo acha o site, a gente extrai
    e-mail/WhatsApp/Instagram do próprio site. Sem nota do Google (dado pago)."""
    import urllib.parse
    vistos, negocios = set(), []
    consultas = ['%s em %s' % (nicho, cidade), '%s %s contato' % (nicho, cidade),
                 'site %s %s whatsapp' % (nicho, cidade)]
    for consulta in consultas:
        if len(negocios) >= quantidade: break
        try:
            _, html = _http_get('https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(consulta))
        except Exception:
            continue
        for href, titulo in re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html):
            if len(negocios) >= quantidade: break
            url = _decodificar_ddg(href)
            if not url.lower().startswith('http'): continue
            dom = re.sub(r'^www\.', '', url.split('//')[-1].split('/')[0]).lower()
            if not dom or dom in vistos: continue
            vistos.add(dom)
            baixo = (url + ' ' + dom).lower()
            if any(p in baixo for p in DOMINIOS_PROIBIDOS) or any(p in baixo for p in DIRETORIOS): continue
            try:
                _, conteudo = _http_get(url)
            except Exception:
                continue
            if len(conteudo) < 300 or not re.search(r'<\s*(html|head|body)', conteudo[:2000], re.I):
                continue
            emails, tel, zap, ig = _extrair_contatos(conteudo)
            if not (emails or zap or tel or ig): continue
            negocios.append({'title': (re.sub(r'<[^>]+>', '', titulo) or '').strip() or url,
                             'category': nicho, 'url': url, 'domain': dom,
                             'phone': tel, 'email': emails[0].lower() if emails else None,
                             'whatsapp': zap, 'instagram': ig, 'address': None,
                             'rating': {}, 'city': cidade, 'logo': '', 'main_image': '',
                             'conteudo': conteudo})
    return negocios

def main_grátis(nicho, cidade, qtd):
    """Rodada real e 100% grátis (sem saldo AIsa). Salva os leads e regenera o painel."""
    AVISO[:] = []
    print('🔎 (modo grátis) Buscando %s em %s em sites públicos...' % (nicho, cidade))
    negocios = buscar_negocios_grátis(nicho, cidade, qtd) or []
    print('   %d sites de negócios com contato. Montando o dossiê...' % len(negocios))
    qualificados, descartados = [], []
    for n in negocios:
        nome = n.get('title') or '?'
        emails, tel, zap, ig = n.get('email'), n.get('phone'), n.get('whatsapp'), n.get('instagram')
        if not (emails or zap or tel or ig):
            descartados.append((nome, 'sem contato')); continue
        ig2 = {'seguidores': None, 'posts': None, 'ativo': None, 'categoria': None, 'ultimo_post_dias': None}
        sc = 20  # tem site próprio
        if emails: sc += 15
        if zap: sc += 15
        if tel: sc += 5
        if ig: sc += 10
        sc = min(100, sc)
        temp = 'quente' if sc >= 55 else ('morno' if sc >= 35 else 'frio')
        lead = {'slug': slugify(nome), 'nome': nome, 'nicho': n.get('category') or nicho, 'cidade': cidade,
                'busca': '%s · %s (grátis)' % (nicho, cidade),
                'nota': None, 'avaliacoes': None, 'email': emails, 'telefone': tel,
                'whatsapp': zap, 'siteAntigo': n.get('url'), 'motivo': 'site encontrado em busca gratuita — avaliar manualmente',
                'status': 'novo', 'instagram': ig,
                'igSeguidores': None, 'igPosts': None, 'igAtivo': None, 'igCategoria': None,
                'obs': 'modo grátis · domínio: %s' % n.get('domain'),
                'score': sc, 'temperatura': temp,
                 'abordagem': 'E-mail + WhatsApp com elogio ao conteúdo e proposta de site moderno; sem IA, revisar o gancho antes.',
                 'dossie': json.dumps({'endereco': None, 'ig': ig2,
                                        'motivo': 'site encontrado em busca gratuita — avaliar manualmente'}, ensure_ascii=False)}
        if _ja_contatado(os.path.join(PASTA, 'prospector.db'), lead['slug']):
            print('   ↪ %s — já contatado antes, pulado' % nome)
            continue
        qualificados.append(lead)
        salvar_lead(os.path.join(PASTA, 'prospector.db'), lead)
        emoji = '🔥' if temp == 'quente' else ('🌤️' if temp == 'morno' else '❄️')
        print('   %s %s — score %d — %s%s%s' % (emoji, nome, sc,
              ('e-mail' if emails else ''), (' + WhatsApp' if zap else ''), (' · IG @%s' % ig) if ig else ''))
    for nome, motivo in descartados:
        print('   ✖ %s — %s' % (nome, motivo))
    regenerar_dashboard()
    print('\n📊 %d leads REAIS encontrados de graça (%d 🔥 quentes).' % (len(qualificados), len([l for l in qualificados if l['temperatura'] == 'quente'])))
    print('💡 Dica: com saldo no AIsa a máquina também traz nota do Google e avaliação por IA.')

def extrair_site(url, chave, simular):
    if simular:
        return ('SITE DE EXEMPLO. Nutricionista clinica ha 10 anos. Atendimento presencial e online. '
                'Contato: contato@exemplo-nutri-simulada.com.br | tel (11) 99999-0001. '
                'Pagina unica anos 2010, sem responsivo, texto corrido.') , 0.0
    corpo = {'urls': url, 'format': 'markdown', 'extract_depth': 'basic', 'include_usage': True}
    try:
        r = api(BASE_APIS + '/tavily/extract', corpo, chave)
    except Exception:
        return None, 0.0
    res = r.get('results') or []
    return (res[0].get('raw_content') if res else None), (r.get('usage', {}).get('credits') or 0)

def julgar_site(nicho, conteudo, chave, simular):
    if simular:
        return {'site_ruim': True, 'motivo': 'layout datado, sem CTA, texto corrido (simulação)', 'email': 'contato@exemplo-nutri-simulada.com.br'}
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', conteudo or '')
    email = emails[0].lower() if emails else None
    try:
        r = chat(chave,
            'Você avalia sites de profissionais para redesign. Site RUIM = 2+ sinais: não responsivo, design datado, sem hierarquia, sem CTA na primeira dobra, conteúdo abandonado, template mal preenchido. Responda APENAS JSON.',
            'Nicho: %s. Conteúdo extraído do site (markdown):\n%s\n\nJSON: {"site_ruim": true/false, "motivo": "1 frase objetiva e verificável"}' % (nicho, (conteudo or '')[:4000]))
    except Exception as e:
        AVISO.append('Sem saldo AIsa: avaliação do site por IA pulada (%s).' % e)
        baixo = (conteudo or '').lower()
        for marca in ('wixsite.com', 'blogspot', 'wordpress.com', '000webhostapp', 'template grátis'):
            if marca in baixo:
                return {'site_ruim': True, 'motivo': 'hospedado em plataforma grátis/template (detecção automática)', 'email': email}
        return {'site_ruim': False, 'motivo': 'avaliação por IA indisponível (sem saldo AIsa) — revisar manualmente', 'email': email}
    r['email'] = email
    return r

def slugify(nome):
    s = norm(nome); s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:40]

def _ja_contatado(db, slug):
    try:
        c = sqlite3.connect(db)
        r = c.execute('SELECT contatadoEm FROM leads WHERE slug=?', (slug,)).fetchone()
        c.close()
        return bool(r and r[0])
    except Exception:
        return False

def salvar_lead(db, lead):
    if _ja_contatado(db, lead.get('slug')):
        return
    campos = ['slug','nome','nicho','cidade','nota','avaliacoes','email','telefone','whatsapp',
              'siteAntigo','motivo','status','urlNova','dataProposta','valor','obs',
              'contratoStatus','contratoEm','manutencao','pago','docCliente','endCliente',
              'instagram','igSeguidores','igPosts','igAtivo','igCategoria','score','temperatura','abordagem','dossie','busca']
    c = sqlite3.connect(db)
    c.execute('''CREATE TABLE IF NOT EXISTS leads(slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT,
        nota REAL, avaliacoes INTEGER, email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
        status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
        contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
        docCliente TEXT, endCliente TEXT, instagram TEXT, igSeguidores INTEGER, igPosts INTEGER,
        igAtivo TEXT, igCategoria TEXT, score INTEGER, temperatura TEXT, abordagem TEXT, dossie TEXT,
        contatadoEm TEXT, contatadoPor TEXT, atualizado TEXT)''')
    # garantir colunas novas em bancos antigos
    existentes = [r[1] for r in c.execute("PRAGMA table_info(leads)")]
    for col, tipo in [('instagram','TEXT'),('igSeguidores','INTEGER'),('igPosts','INTEGER'),('igAtivo','TEXT'),
                      ('igCategoria','TEXT'),('score','INTEGER'),('temperatura','TEXT'),('abordagem','TEXT'),
                      ('dossie','TEXT'),('contatadoEm','TEXT'),('contatadoPor','TEXT'),('busca','TEXT')]:
        if col not in existentes:
            try: c.execute('ALTER TABLE leads ADD COLUMN %s %s' % (col, tipo))
            except Exception: pass
    c.execute('INSERT OR REPLACE INTO leads (%s,atualizado) VALUES (%s,?)' % (','.join(campos), ','.join('?'*len(campos))),
              [lead.get(k) for k in campos] + [datetime.datetime.now().strftime('%Y-%m-%d %H:%M')])
    c.commit(); c.close()

def regenerar_dashboard():
    tpl = os.path.join(PASTA, 'dashboard-template.html')
    if not os.path.exists(tpl): return
    c = sqlite3.connect(os.path.join(PASTA, 'prospector.db')); c.row_factory = sqlite3.Row
    leads = [dict(r) for r in c.execute('SELECT * FROM leads')]; c.close()
    t = open(tpl, encoding='utf-8').read().replace('__DADOS__',
        json.dumps({'atualizado': datetime.datetime.now().strftime('%d/%m/%Y %H:%M'), 'leads': leads}, ensure_ascii=False))
    open(os.path.join(PASTA, 'dashboard.html'), 'w', encoding='utf-8').write(t)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    simular = '--simular' in sys.argv
    gratis = '--gratis' in sys.argv
    if len(args) < 2:
        print('Uso: python motor.py "nicho" "cidade" [--simular] [--gratis]'); sys.exit(1)
    nicho, cidade = args[0], args[1]
    if gratis:
        return main_grátis(nicho, cidade, CFG['prospeccao'].get('leads_por_busca', 5))
    chave = CFG.get('aisa_key', '')
    if not chave and not simular:
        print('ERRO: preencha aisa_key no config-standalone.json (conta gratis em aisa.one) ou rode com --simular'); sys.exit(1)
    meta = CFG['prospeccao'].get('leads_por_busca', 5)
    print('🔎 Caçando %s em %s (nota ≥ %s, %s+ avaliações)...' % (nicho, cidade, CFG['prospeccao']['nota_minima'], CFG['prospeccao']['avaliacoes_minimas']))
    negocios = buscar_negocios(nicho, cidade, chave, simular) or []
    print('   %d negócios bem avaliados. Montando o dossiê de cada um...' % len(negocios))
    qualificados, descartados = [], []
    for n in negocios:
        if len(qualificados) >= meta: break
        nome = n.get('title') or '?'
        url, dom = n.get('url'), (n.get('domain') or '')
        rating = n.get('rating') or {}
        # site próprio? (Instagram/diretório NÃO conta como site, mas o lead continua valioso)
        tem_site = bool(url) and not any(p in (dom or url) for p in DOMINIOS_PROIBIDOS)
        conteudo, motivo, email = None, None, None
        if tem_site:
            conteudo, _ = extrair_site(url, chave, simular)
            if conteudo:
                j = julgar_site(nicho, conteudo, chave, simular)
                motivo = j.get('motivo'); email = j.get('email')
            else:
                motivo = 'site fora do ar'
        else:
            motivo = 'NÃO TEM SITE — maior oportunidade' if not url else 'só tem rede social/diretório (sem site próprio)'
        # Instagram
        handle = achar_handle_ig(n, conteudo)
        ig = enriquecer_instagram(handle, chave, simular)
        tel = (n.get('phone') or '').replace('+', '').replace(' ', '')
        zap = tel if tel.startswith('55') else ('55' + tel if len(tel) >= 10 else None)
        # precisa de PELO MENOS um canal de contato
        if not (email or zap or handle):
            descartados.append((nome, 'sem nenhum contato (e-mail/zap/IG)')); continue
        lead = {'slug': slugify(nome), 'nome': nome, 'nicho': (n.get('category') or nicho), 'cidade': cidade,
                'busca': '%s · %s' % (nicho, cidade),
                'nota': rating.get('value'), 'avaliacoes': rating.get('votes_count'), 'email': email,
                'telefone': n.get('phone'), 'whatsapp': zap, 'siteAntigo': url if tem_site else None,
                'motivo': motivo, 'status': 'novo',
                'instagram': handle, 'igSeguidores': (ig or {}).get('seguidores'), 'igPosts': (ig or {}).get('posts'),
                'igAtivo': ('sim' if (ig or {}).get('ativo') else ('não' if ig and ig.get('ativo') is not None else None)),
                'igCategoria': (ig or {}).get('categoria'),
                'obs': 'logo: %s | foto: %s' % (n.get('logo') or '-', n.get('main_image') or '-')}
        sc, temp, abordagem = score_lead(lead, ig, chave, simular)
        lead['score'] = sc; lead['temperatura'] = temp; lead['abordagem'] = abordagem
        lead['dossie'] = json.dumps({'endereco': n.get('address'), 'ig': ig, 'motivo': motivo}, ensure_ascii=False)
        if _ja_contatado(os.path.join(PASTA, 'prospector.db'), lead['slug']):
            print('   ↪ %s — já contatado antes, pulado' % nome)
            continue
        qualificados.append(lead)
        salvar_lead(os.path.join(PASTA, 'prospector.db'), lead)
        emoji = '🔥' if temp == 'quente' else ('🌤️' if temp == 'morno' else '❄️')
        print('   %s %s — score %d — ★%s (%s) — %s%s' % (emoji, nome, sc, rating.get('value'), rating.get('votes_count'),
              ('SEM SITE' if not tem_site else 'site fraco'), (' · IG @%s' % handle) if handle else ''))
    for nome, motivo in descartados:
        print('   ✖ %s — %s' % (nome, motivo))
    regenerar_dashboard()
    quentes = len([l for l in qualificados if l.get('temperatura') == 'quente'])
    print('\n📊 %d leads no dossiê (%d 🔥 quentes) · %d descartados.' % (len(qualificados), quentes, len(descartados)))
    print('💰 Custo da rodada: US$ %.4f + %d chamadas de API (dados + IG + modelo).' % (CUSTO['usd'], CUSTO['chamadas']))
    if qualificados:
        print('   Custo por lead: US$ %.4f.' % (CUSTO['usd'] / len(qualificados)))
    print('🖥  Abra o painel: aba LEADS, ordenados por score (os 🔥 primeiro).')

if __name__ == '__main__':
    main()
