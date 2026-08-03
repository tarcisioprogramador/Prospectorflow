# 🎯 Máquina de Leads

Acha clientes SOZINHA, no seu computador — sem Claude, sem ChatGPT. Você digita nicho e cidade, clica um botão, e em ~1 minuto tem uma lista de clientes reais com nota do Google, Instagram, WhatsApp, e-mail e uma nota de oportunidade (🔥 quente / 🌤️ morno / ❄️ frio). O motor é a **AIsa** (uma chave dá acesso a Google, Instagram, web e IA), e você paga só por uso — começa com US$ 2 grátis.

## Instalação (5 minutos)

1. **Duplo clique** em `instalar-standalone.bat` (Windows) ou `instalar-standalone.command` (Mac). Requisito único: **Python** (python.org/downloads → marque "Add to PATH"; no Mac: `brew install python3`).
2. Crie sua conta em **aisa.one** → console → **gerar API key** (ganha US$ 2 grátis pra testar).
3. **Duplo clique** em `iniciar-dashboard.bat` (Mac: `.command`) → o painel abre no navegador em `localhost:8766`.
4. Aba **Configurações → Motor de IA** → cole a chave → **Salvar motor**. (Sem chave, tudo roda em modo simulação pra você conhecer.)

## Como usar — aba 🎯 Leads

- No topo: digite **Nicho** + **Cidade** + **Quantos** → botão **Prospectar**. Em ~1 min a lista aparece, ordenada por score.
- **⚙️ filtros avançados**: nota mínima, avaliações, raio de busca (recolhido por padrão).
- Cada card traz o **dossiê**: nota do Google, se tem site (ou "SEM SITE — maior oportunidade"), Instagram (seguidores/ativo), contatos e uma sugestão de abordagem. Botões diretos: **Ver site · Instagram · WhatsApp · e-mail**.
- **Marcar contatado** move o lead pra aba Contatados (pra follow-up depois).

## ⏰ Agendar (opcional — acorde com os leads prontos)

No formulário, botão **⏰ agendar**: define "todo dia às 9h busca [nicho] em [cidade]". Pra ativar, **duplo clique uma vez** em `instalar-agendador.bat` (Mac: `.command`). A partir daí a máquina roda sozinha no horário.

> ⚠️ Prospecções agendadas consomem créditos da sua conta AIsa automaticamente. Configure com o saldo em mente.

## Custos

Cada prospecção completa custa centavos (sai do seu saldo AIsa). Ao fim de cada rodada o painel mostra o custo por lead. Pré-pago, sem mensalidade. Modelo configurável (mais barato: gemini-2.5-flash).

## Deu algo errado?

- **Painel bagunçado / menu vazio:** duplo clique em `RESETAR-PAINEL.bat`, depois Ctrl+Shift+R no navegador.
- **Python não encontrado:** reinstale marcando "Add to PATH".
- **"modo simulação":** falta a chave — cole em Configurações → Motor de IA.

---
Máquina de Leads · por Helio Arreche · @helioarreche · motor AIsa.one
