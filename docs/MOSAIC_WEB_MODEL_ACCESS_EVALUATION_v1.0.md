# Mosaic — Avaliação de acesso a modelos por interfaces web

**Versão:** 1.0  
**Data da avaliação:** 18/10/2026  
**Escopo:** investigação documental e de termos; nenhuma integração automática foi implementada ou testada.

## 1. Conclusão executiva

**Decisão recomendada: não automatizar, neste momento, o uso de sessões de consumo de ChatGPT, Claude ou Gemini por scraping, automação de DOM ou reutilização de cookies.** Os termos oficiais consultados impõem restrições explícitas a extração programática ou acesso automatizado, e a permissão pode variar por produto, região e contrato. Uma assinatura web não deve ser interpretada como autorização para controlar a interface por software nem como crédito de API.

A alternativa de menor risco para execução automatizada continua sendo um provider oficialmente suportado (API ou integração expressamente autorizada), com seleção explícita por conversa. Quando o objetivo for aproveitar uma sessão web já aberta, o Mosaic pode oferecer um fluxo assistido: o usuário abre o serviço, interage manualmente e importa/cola a resposta que deseja preservar. Esse fluxo não deve alegar que o Core leu ou retomou a sessão automaticamente.

Esta é uma avaliação técnica de produto, não um parecer jurídico. Os termos precisam ser revisados novamente antes de qualquer integração e para o contrato exato aplicável ao usuário e ao serviço.

## 2. Alternativas avaliadas

| Alternativa | Automação | Custo e limites | Risco | Recomendação |
|---|---|---|---|---|
| API oficial do provedor | Sim, dentro do contrato/API | Normalmente tarifação e limites próprios da API; assinatura de consumo não deve ser presumida como crédito de API | Menor ambiguidade contratual; ainda exige segurança, orçamento e tratamento de dados | **Preferida para execução automatizada** |
| Modelo local via provider existente | Sim, dentro do ambiente local | Custo de hardware/energia; qualidade e latência dependem do equipamento/modelo | Dados podem permanecer locais; recursos de hardware são limitados | **Preferida quando privacidade e custo marginal importam** |
| Integração oficial/connector autorizado | Sim, apenas nas capacidades e permissões concedidas | Depende do produto, plano e limites do fornecedor | Escopos, expiração, revogação e proveniência precisam ser tratados | **Avaliar caso a caso** |
| Handoff assistido pelo usuário | Não há extração automática; o usuário copia/exporta e entrega a resposta ao Mosaic | Baixo custo de integração; esforço manual e perda de continuidade automática | Risco menor; exige indicar claramente a origem e que a importação foi manual | **Alternativa imediata segura** |
| Automação de interface de consumo (DOM, scraping, cookies/sessão) | Tecnicamente possível em alguns cenários, mas frágil | Alto custo de manutenção; alterações de UI, limites e bloqueios | **Alto**: conflito potencial com termos, exposição de sessão, instabilidade e falsa aparência de suporte oficial | **Não implementar sem autorização expressa e revisão específica** |

## 3. Evidências de termos oficiais consultados

A consulta foi feita em 18/10/2026. Os termos podem mudar; os links abaixo são a fonte normativa a rever antes de qualquer implementação.

### OpenAI / ChatGPT

Os [Termos de Uso oficiais, vigentes desde 1º de janeiro de 2026](https://openai.com/policies/row-terms-of-use/) proíbem “automatically or programmatically extract data or Output” e também proíbem contornar limites ou medidas de proteção (seção “What you cannot do”). A existência de uma URL de conversa ou de uma assinatura não demonstra autorização para o Mosaic extrair respostas por automação de navegador.

### Anthropic / Claude

Os [Consumer Terms of Service](https://www.anthropic.com/legal/consumer-terms), na versão consultada, efetiva em 8 de outubro de 2025, restringem crawling/scraping e acesso automatizado ou não humano, salvo quando feito via API key ou expressamente permitido (seção 3). A versão consultada identifica escopo regional específico; deve-se confirmar a versão aplicável à conta e ao país antes de qualquer decisão.

### Google / Gemini e serviços Google

Os [Termos de Serviço do Google](https://policies.google.com/terms?hl=pt-BR), versão consultada em 18/10/2026, proíbem meios automatizados de acesso a conteúdo quando violam instruções legíveis por máquina, como regras em páginas web (seção “Não abuse dos nossos serviços”). Isso não equivale a uma autorização geral para automatizar Gemini; os termos específicos do produto e do serviço também precisam ser avaliados.

## 4. Separação entre modelo e acesso

A arquitetura do Mosaic deve preservar:

- `MODEL ≠ ACCESS`: identidade do modelo e mecanismo de acesso são entidades conceitualmente distintas.
- `MOSAIC OWNS STATE`: o Core continua dono da Task, das aprovações, do estado persistido e da verificação.
- Seleção explícita por conversa: sem roteamento, troca de provider ou fallback silencioso.
- Proveniência: registrar provider/método de acesso, origem, horário e limitações conhecidas.
- Nenhuma inferência de acesso: uma URL não prova que o Mosaic pode ler, continuar ou validar a sessão.

## 5. Requisitos mínimos para uma futura integração autorizada

Antes de qualquer prova de conceito automatizada:

1. Identificar o produto, plano, região e termos exatos aplicáveis.
2. Obter autorização documentada do fornecedor ou usar uma API/integração oficialmente suportada.
3. Definir consentimento explícito por usuário e conversa, escopos mínimos, expiração e revogação.
4. Não armazenar senhas, cookies ou tokens de sessão em texto aberto; não importar cookies de navegador.
5. Não contornar CAPTCHA, rate limits, controles de acesso, anti-automação ou mecanismos de proteção.
6. Separar falhas de autenticação, sessão expirada, limite, erro de rede e resposta incompleta.
7. Persistir a proveniência do conteúdo e permitir que o usuário identifique/importa a resposta manualmente quando a integração não estiver autorizada.
8. Executar revisão de segurança, privacidade, termos, custos e manutenção antes de ativar qualquer caminho.
9. Provar um ciclo ida/volta reproduzível e tratamento de erro sem declarar sucesso com base apenas na resposta do modelo.
10. Obter aprovação explícita do MASTER para implementação.

## 6. Decisão para o Mosaic

| Capacidade | Estado |
|---|---|
| Revisão documental de termos oficiais | **Testado** — fontes consultadas em 18/10/2026 |
| Automação de sessão web de consumo | **Planejado / não autorizado** — não implementada |
| Handoff manual com proveniência | **Planejado** — pode ser proposto como fluxo separado |
| API/provider oficial selecionado por conversa | **Presente no código**; cobertura de CI não substitui validação com credenciais reais |
| Prova de ida/volta em integração web autorizada | **Não executada** |

**Resultado:** a investigação documental foi concluída. Não existe base suficiente para aprovar automação de interfaces web de consumo. Manter essa modalidade fora do caminho crítico; priorizar APIs oficiais, providers locais e handoff manual transparente. Nenhuma integração automática foi adicionada.

## 7. Fontes

- OpenAI, *Terms of Use* (effective 2026-01-01): https://openai.com/policies/row-terms-of-use/
- Anthropic, *Consumer Terms of Service* (version reviewed, effective 2025-10-08): https://www.anthropic.com/legal/consumer-terms
- Google, *Termos de Serviço do Google* (versão consultada em 2026-10-18): https://policies.google.com/terms?hl=pt-BR
