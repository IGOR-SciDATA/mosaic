# REA — Estudo e Análise: suporte a MCP Servers e Plugins da comunidade no Mosaic
**Versão:** 1.0  
**Status:** Pesquisa e proposta arquitetural — não implementada  
**Data:** 2026-10-29  
**Escopo:** analisar o modelo de MCP Servers e plugins do Claude Code, compará-lo com a arquitetura atual do Mosaic e propor uma implementação incremental, local-first e segura.

## 1. Resumo executivo

A recomendação é construir no Mosaic duas capacidades relacionadas, mas separadas:

1. **MCP Client no Mosaic Core:** conecta-se a servidores MCP locais ou remotos, descobre suas tools/resources/prompts, normaliza as tools para o catálogo do agente e executa chamadas através do ponto central de política, aprovação, persistência e auditoria do Mosaic.
2. **Sistema de Plugins do Mosaic:** pacote instalável que pode agrupar servidores MCP, Skills, comandos/prompt templates e, em fases posteriores, agentes declarativos e hooks limitados. Um marketplace é um catálogo de fontes de plugins, não um runtime privilegiado.

O Mosaic deve aproveitar o padrão interoperável MCP em vez de inventar um protocolo próprio de integração. Mas não deve copiar sem distinção o runtime completo do Claude Code: a arquitetura do Mosaic é um Core local com política explícita, Task Engine persistente e Tool Registry. Qualquer tool de comunidade deve passar pelo mesmo controle das tools nativas.

**Decisão recomendada:** primeiro implementar MCP Client para servidores MCP confiáveis e uma experiência de conexão manual; depois instalar pacotes de plugins declarativos; só então abrir um marketplace comunitário. O marketplace não deve preceder os controles de instalação, revisão, atualização e isolamento.

## 2. Fontes e método

### Fontes primárias do Claude / Anthropic
- Claude Code MCP: https://code.claude.com/docs/en/mcp
- Claude Code plugins: https://code.claude.com/docs/en/plugins
- Plugin marketplaces: https://code.claude.com/docs/en/plugin-marketplaces
- Repositório de plugins oficiais: https://github.com/anthropics/claude-plugins-official
- Referência de plugins da plataforma: https://platform.claude.com/docs/en/manage-claude/plugins-api
- Marketplace de plugins: https://claude.com/marketplace/plugins

### Fontes primárias do Model Context Protocol
- Documentação oficial: https://modelcontextprotocol.io/
- SDK Python oficial: https://py.sdk.modelcontextprotocol.io/
- SDK TypeScript oficial: https://ts.sdk.modelcontextprotocol.io/
- Primeiros passos Python e distinção entre tools/resources/prompts: https://py.sdk.modelcontextprotocol.io/get-started/first-steps/
- Cliente TypeScript e transportes: https://ts.sdk.modelcontextprotocol.io/client

### Fontes do Mosaic inspecionadas estaticamente
- `backend/app/tools/base.py`
- `backend/app/tools/registry.py`
- `backend/app/tools/builtin.py`
- `backend/app/tools/safe_http.py`
- `backend/app/services/tools.py`
- `backend/app/services/agent_decision.py`
- `backend/app/models/tool_call.py` e repositórios relacionados
- `backend/app/db/database.py`
- `docs/PHASE1_TOOL_HARDENING.md`
- `docs/MOSAIC_AGENT_PROFILES_AND_ARTIFACT_TOOLS_ROADMAP_v1.0.md`
- `docs/MOSAIC_OFFICIAL_HARNESS_CONTRACT_v1.2.md`

**Limitação da auditoria:** esta é uma leitura estática de código e documentação pública. Não foi executada uma conexão real a um servidor MCP, nem foram rodados testes de runtime nesta pesquisa. As recomendações de produto e segurança abaixo são análise arquitetural, não alegações sobre recursos já existentes no Mosaic.

## 3. Como funciona MCP no Claude Code

### 3.1 MCP é um protocolo de integração, não o plugin em si

O Model Context Protocol padroniza a comunicação entre uma aplicação cliente/host e servidores que expõem capacidades. O servidor pode oferecer três primitivas principais:

| Primitiva | Quem normalmente decide usá-la | Propósito | Exemplo |
|---|---|---|---|
| Tools | Modelo, sob controle do host | Executar uma operação | Pesquisar issues, consultar banco, criar tarefa |
| Resources | Aplicação/host | Fornecer dados identificados por URI | Ler documentação ou um recurso do serviço |
| Prompts | Usuário/host | Template de interação reutilizável | Revisar um PR com um formato predefinido |

O protocolo inclui inicialização e negociação de capacidades, listagem/execução de tools, leitura de resources e recuperação de prompts. O conjunto efetivamente suportado depende do cliente e do servidor; o Mosaic pode começar com tools sem implementar todas as capacidades MCP.

### 3.2 Cliente e servidor

- **MCP Server:** o programa/serviço que expõe tools, resources e/ou prompts.
- **MCP Client:** componente dentro do aplicativo que fala MCP com o servidor.
- **Host:** o aplicativo que decide quais servidores conectar, quais tools ficam disponíveis ao modelo e como aplicar política e aprovação.

No Mosaic, o host deve ser o Mosaic Core. O Core cria e mantém o cliente MCP, descobre as capacidades e decide o que é publicado no catálogo do agente. O servidor MCP não deve chamar diretamente a API interna de execução de tools nem ganhar privilégios só por estar conectado.

### 3.3 Transportes

Os transportes mais relevantes para compatibilidade são:

- **stdio:** o cliente inicia um processo local e troca mensagens pelo stdin/stdout. É útil para servidores que rodam no computador do usuário, mas significa executar um programa instalado localmente com as permissões do processo Mosaic.
- **Streamable HTTP:** conexão com servidor remoto por HTTP; é a opção moderna recomendada para novas integrações remotas.
- **HTTP + SSE legado:** pode ser necessário para compatibilidade com servidores antigos, mas não deve ser o primeiro transporte a implementar se isso atrasar a base Streamable HTTP.

O cliente deve ter timeout, cancelamento, limites de tamanho, tratamento de falha e encerramento de processo. Não deve permitir que uma configuração MCP determine livremente executáveis, diretórios ou variáveis de ambiente sem validação e consentimento do usuário.

### 3.4 Ciclo de uma tool MCP

1. O Mosaic conecta ao servidor e negocia versão/capacidades.
2. O Mosaic lista tools e valida seus nomes, descrições e schemas.
3. O Core filtra as tools por status, permissões, projeto e configuração do usuário.
4. O catálogo autorizado é exposto ao modelo com nomes qualificados, por exemplo `mcp__github__search_issues`.
5. O modelo propõe uma chamada usando o schema anunciado.
6. O Core valida argumentos e aplica sua política de aprovação.
7. O cliente MCP chama a tool remota/local.
8. O resultado é limitado, normalizado e tratado como **dado não confiável**, não como instrução.
9. O Mosaic persiste status, resultado redigido, duração e referência ao servidor/tool nos registros operacionais.
10. A resposta é devolvida ao agente, que decide o próximo passo dentro do loop existente.

O servidor pode falhar, ficar indisponível ou mudar sua lista de tools. O Mosaic precisa lidar com isso sem aceitar silenciosamente mudanças de schema durante uma conversa ou tarefa em andamento.

## 4. Como funcionam os plugins no Claude Code

### 4.1 Plugin é um pacote, não um servidor

No ecossistema Claude Code, um plugin pode agrupar diferentes componentes:

- **Skills:** instruções e arquivos de apoio carregados quando relevantes.
- **Commands:** prompts reutilizáveis acionados pelo usuário.
- **Agents/subagents:** perfis auxiliares com instruções próprias.
- **Hooks:** ações disparadas por eventos do ciclo de trabalho.
- **MCP servers:** configurações que conectam a ferramentas e sistemas externos.
- **LSP e outros componentes:** integrações adicionais específicas do ambiente.

A estrutura e os componentes suportados dependem da versão do Claude Code. O ponto conceitual importante é que um plugin pode combinar conhecimento, workflows e integrações em uma unidade instalável.

### 4.2 Manifest e catálogo

Os plugins Claude Code usam um manifesto como `.claude-plugin/plugin.json`; um marketplace é um catálogo que aponta para fontes de plugins. O catálogo não executa a ferramenta e não concede confiança automática. A origem e o conteúdo de cada plugin ainda precisam ser avaliados.

O repositório oficial `anthropics/claude-plugins-official` separa plugins internos e externos. A própria documentação alerta que plugins podem conter MCP servers e software local e recomenda instalar somente fontes confiáveis. Isso é uma lição de arquitetura importante para um marketplace aberto.

### 4.3 Instalação, ativação e atualização

Um sistema semelhante precisa separar estados distintos:

- Encontrado no catálogo.
- Baixado para uma área temporária.
- Validado e inspecionado.
- Instalado, mas desabilitado.
- Habilitado pelo usuário.
- Atualização disponível.
- Desabilitado ou desinstalado.

Baixar um plugin não deve ativá-lo. Atualizar um plugin não deve substituir silenciosamente a versão ativa, ampliar permissões ou executar código sem aviso. O Mosaic deve manter versão/hash do pacote e permitir rollback.

### 4.4 O que não copiar no MVP

Não implementar hooks arbitrários de shell que possam rodar automaticamente em todos os eventos. Não executar scripts incluídos em plugins comunitários por padrão. Não permitir que um plugin modifique o Core, a política global ou o registro de permissões. Também não presumir que toda estrutura do Claude Code seja uma especificação universal do MCP: plugin é um formato de empacotamento específico do produto; MCP é o protocolo interoperável.

## 5. Estado atual do Mosaic e pontos de integração

### 5.1 Tool contract e registro

`Tool` em `backend/app/tools/base.py` define nome, descrição, schema, política, validação e execução. `ToolRegistry` em `backend/app/tools/registry.py` mantém um registro simples e rejeita nomes duplicados. É um bom ponto de integração lógica, mas ferramentas MCP são descobertas dinamicamente e podem ficar indisponíveis; portanto, não basta registrar uma classe estática no startup e esquecer o ciclo de vida do servidor.

**Recomendação:** criar um adaptador `MCPToolAdapter` que implemente o contrato `Tool`, encaminhando a execução a um MCP client gerenciado. O registro dinâmico deve ser namespaced e derivado de servidores instalados/habilitados, com snapshot da lista/schema para cada Task.

### 5.2 Decisão do agente

`backend/app/services/agent_decision.py` constrói o catálogo a partir do registry e instrui o modelo a escolher somente tools anunciadas. Isso é favorável: tools MCP podem ser apresentadas pelo mesmo mecanismo, desde que passem pelo filtro de tools permitidas e pela política do Core.

**Recomendação:** não adicionar um caminho paralelo de chamadas MCP dentro do prompt ou do provider. Uma tool MCP deve parecer uma tool do Mosaic para o loop do agente, mas a execução continua roteada pelo Core.

### 5.3 Política, aprovação e execução

`backend/app/services/tools.py` valida argumentos, resolve workspace e aplica política central antes da execução. `PHASE1_TOOL_HARDENING.md` documenta limites do filesystem, terminal e web, além de reconhecer que a allowlist de comandos não é um sandbox de sistema operacional.

**Recomendação:** tools MCP externas devem ter política por servidor e por tool, com escopo, nível de risco, timeout e necessidade de aprovação. O servidor não define a própria política de confiança. Uma tool remota que apaga registros ou envia mensagens deve exigir aprovação independentemente do que o servidor declara em sua descrição.

### 5.4 Persistência e histórico

O banco atual contém `tool_calls`, `tool_results`, `task_events` e `settings`. A infraestrutura pode registrar execuções, mas a inspeção não encontrou um sistema de instalação/marketplace MCP já implementado.

**Recomendação:** introduzir repositórios/entidades para servidores e plugins quando a implementação começar, com migração explícita e testes. Evitar guardar tokens secretos em JSON de configuração ou no histórico de tool calls. Guardar referências a credenciais no armazenamento local apropriado; logs devem ser redigidos.

### 5.5 Skills e agentes

O Mosaic já tem documentação para Skills e perfis de agente. Um plugin pode empacotar Skills e servidores MCP, reutilizando a biblioteca existente. O pacote não deve sobrescrever uma Skill de mesmo nome sem namespacing.

**Recomendação:** nomes de Skills e tools qualificados por plugin/servidor, por exemplo `plugin__data-analysis__summarize_csv` e `mcp__github__create_issue`, com metadados de origem visíveis na UI.

## 6. Arquitetura-alvo proposta

```text
Plugin Catalog / Git repository / local package
                 │
                 ▼
        Plugin Installer (staging)
     download → hash → inspect → validate
                 │
                 ▼
         Installed Plugin Store
       version / status / provenance
                 │
        user explicitly enables
                 ▼
      Plugin Manifest Resolver
       ┌─────────┼──────────┐
       ▼         ▼          ▼
     Skills    Commands   MCP Server Specs
       │         │          │
       ▼         ▼          ▼
  Skill Store  Prompt UI  MCP Connection Manager
                            │
                    list tools/resources/prompts
                            │
                            ▼
                    MCPToolAdapter(s)
                            │
                            ▼
                    Mosaic Tool Registry view
                            │
                            ▼
 Agent → Core validation → policy/approval → execution
                            │
                            ▼
                ToolCall / ToolResult / Task Events
```

**Autoridade única:** o Core é o único ponto que valida argumentos, aprova ações, resolve escopo e registra resultados. O plugin/servidor contribui com capacidades; não ganha autoridade sobre o Core.

## 7. Formato de plugin do Mosaic: proposta mínima

Começar com um manifesto declarativo, versionado e limitado. Exemplo conceitual:

```json
{
  "schema_version": 1,
  "id": "community.data-tools",
  "name": "Data Tools",
  "version": "1.0.0",
  "description": "Ferramentas para análise de dados",
  "publisher": "community",
  "license": "MIT",
  "components": {
    "mcp_servers": [
      {
        "id": "data",
        "transport": "stdio",
        "command": "uv",
        "args": ["run", "server.py"],
        "working_directory": ".",
        "env_refs": ["DATA_API_KEY"]
      }
    ],
    "skills": ["skills/data-analysis/SKILL.md"],
    "commands": ["commands/summarize-data.md"]
  },
  "permissions_requested": [
    "network:api.example.com",
    "workspace:read"
  ]
}
```

Este manifesto é uma sugestão de design, **não** um formato existente ou aprovado. A instalação deve rejeitar campos desconhecidos ou não suportados. `command`, `args`, diretório de trabalho e variáveis de ambiente exigem validação e consentimento; `env_refs` aponta para segredos já configurados pelo usuário e nunca inclui valores secretos no pacote.

O primeiro MVP não suporta scripts/hooks executáveis arbitrários. O pacote deve ser conteúdo inspecionável. O servidor MCP em si pode ser um programa externo e, por isso, exige uma etapa de confiança explícita separada da instalação do pacote.

## 8. Modelo de permissões e segurança

### 8.1 Níveis de risco

Sugestão inicial de categorias:

- **Leitura local limitada:** consulta de arquivos dentro de um workspace aprovado.
- **Leitura remota:** consulta de APIs/serviços externos.
- **Escrita local:** criação ou alteração de arquivos.
- **Ação remota reversível:** criação/edição de tickets, comentários, atualização de registros.
- **Ação remota sensível/irreversível:** excluir dados, enviar mensagens/publicações, alterar permissões, pagamentos ou executar comandos.

O nível real é determinado pelo contrato e comportamento da tool, não apenas por seu nome/descrição. Na dúvida, elevar risco e exigir confirmação.

### 8.2 Regras obrigatórias

1. Plugins e servidores ficam desabilitados até ativação explícita.
2. Toda tool externa é namespaced, validada e submetida à política central.
3. Tool schemas são validados; argumentos extras são rejeitados quando o schema não os permite.
4. O Core limita duração, tamanho de input/output, concorrência e cancelamento.
5. Tools externas recebem somente as credenciais e escopos necessários; nunca o ambiente inteiro do Mosaic.
6. Saídas MCP são dados não confiáveis e não podem sobrescrever instruções de sistema ou política.
7. Nunca executar `command`/scripts comunitários silenciosamente; mostrar executável, argumentos, fonte, versão e permissões solicitadas.
8. Não publicar segredos nos prompts, eventos, erros, outputs ou metadados.
9. Mudanças de schema/tool list devem ser detectadas; a Task usa snapshot fixo ou é interrompida para revalidar.
10. Desconectar ou desabilitar um servidor remove suas tools do catálogo de novas chamadas e cancela operações pendentes de acordo com a política.
11. Plugins não podem registrar nomes que colidam com tools nativas ou de outro servidor.
12. Atualizações devem ser inspecionadas, mostrar o diff/hash e exigir confirmação quando mudarem permissões ou componentes executáveis.

### 8.3 Limites de isolamento

Um processo MCP local normalmente executa com as permissões do usuário que roda o Mosaic, a menos que haja sandbox de sistema operacional. Um subprocesso, allowlist ou aprovação não equivale a isolamento forte. Para execução comunitária, considerar container/OS sandbox no futuro; no MVP, preferir servidores remotos confiáveis e servidores locais explicitamente aprovados.

Para transporte HTTP remoto:
- exigir HTTPS por padrão fora de loopback;
- validar URLs, redirecionamentos e destinos de rede para mitigar SSRF;
- suportar autenticação sem persistir tokens em texto aberto;
- definir timeout, limites de payload e rate limits;
- evitar aceitar endpoints privados/metadata cloud como destinos remotos configuráveis sem política explícita.

## 9. Compatibilidade e estratégias de implementação

### Opção A — Integrar uma biblioteca MCP existente (recomendada)

Usar o SDK oficial Python MCP como cliente para o backend Python/FastAPI do Mosaic. Isso reduz implementação manual de JSON-RPC, negociação, listagem de tools, transportes e tratamento do protocolo.

Vantagens:
- protocolo mais completo e menos código próprio;
- melhor compatibilidade com servidores MCP da comunidade;
- manutenção alinhada com as mudanças do padrão.

Cuidados:
- fixar versão compatível e auditar dependências;
- começar pelas capacidades/transportes realmente necessários;
- cobrir a integração com testes de contrato;
- verificar compatibilidade do SDK escolhido com a versão Python suportada pelo projeto.

### Opção B — Implementar JSON-RPC/transportes manualmente

Não recomendada. Criar cliente próprio tende a introduzir bugs de sessão, framing, reconexão, timeout, capacidades, cancelamento e compatibilidade. Só faria sentido para um subconjunto muito estreito com justificativa concreta.

### Transportes do MVP

1. **Fase 1: Streamable HTTP** para servidores remotos.
2. **Fase 2: stdio** para servidores locais, após definir gestão de processos, environment allowlist, working directory e controles de execução.
3. **Fase 3: compatibilidade SSE legado**, se a demanda comunitária justificar.

A ordem pode ser alterada se os primeiros plugins-alvo forem todos locais, mas a superfície de risco do stdio precisa ser explicitamente reconhecida.

## 10. API e UI propostas

Rotas conceituais; não existem ainda:

- `GET /api/plugins/catalogs` — listar fontes configuradas.
- `POST /api/plugins/catalogs` — adicionar catálogo/repositório.
- `GET /api/plugins/discover` — pesquisar plugins disponíveis.
- `POST /api/plugins/install` — baixar para staging e validar, sem ativar.
- `GET /api/plugins/installed` — listar plugins, versões, origem e status.
- `POST /api/plugins/{id}/enable` / `disable` / `uninstall`.
- `GET /api/mcp/servers` — servidores configurados e estado de conexão.
- `POST /api/mcp/servers` — adicionar servidor.
- `POST /api/mcp/servers/{id}/connect` / `disconnect`.
- `GET /api/mcp/servers/{id}/tools` — ferramentas descobertas, schema, origem e risco.
- `POST /api/mcp/servers/{id}/test` — testar handshake/listagem sem executar tools.

### Experiência na interface

1. Aba **Extensões** com subabas Descobrir, Instaladas, Servidores MCP e Fontes.
2. Tela de detalhes do plugin: publisher, origem, versão, licença, componentes, tools, permissões, hashes e última atualização.
3. Fluxo de instalação em etapas: revisar conteúdo → permissões → instalar desabilitado → ativar.
4. Para cada servidor MCP: estado, latência, última conexão, tools, schema e erros redigidos.
5. Para cada tool proposta pelo agente: origem claramente visível (nativa ou plugin/servidor), resumo do efeito e aprovação exigida.
6. Opções para desligar/desinstalar, revogar credenciais e reverter versão.
7. O agente deve ver somente tools habilitadas e autorizadas para a tarefa, não todas as tools de todos os catálogos indiscriminadamente.

## 11. Plano de implementação por fases

### Fase 0 — Contrato e escolha do SDK
- Aprovar protocolo, transportes, permissões e threat model.
- Confirmar versão Python e dependências do backend.
- Selecionar 1 servidor de teste de leitura e 1 de ação controlada.
- Definir schema persistido, eventos e snapshot de tools.

**Aceite:** ADR aprovado e lista de riscos; nenhum runtime alterado.

### Fase 1 — MCP Client experimental
- Adicionar SDK MCP como dependência versionada.
- Implementar connection manager para Streamable HTTP.
- Handshake, list tools, validação de schema, timeout e disconnect.
- Sem marketplace e sem execução automática.

**Aceite:** testes com servidor fake local para handshake, listagem, erro, timeout, schema inválido e disconnect.

### Fase 2 — Adapter para Tool Registry
- Implementar `MCPToolAdapter` e namespacing.
- Enviar tool calls pelo mesmo caminho de validação/política/aprovação.
- Persistir origem, servidor, nome remoto e snapshot/schema.
- Limitar outputs e redigir erros.

**Aceite:** uma tool MCP de leitura conclui via agente e todos os eventos/ToolResults ficam correlacionados; tools não autorizadas não aparecem no catálogo.

### Fase 3 — Gestão manual de servidores
- UI/API para adicionar URL remota, autenticação, conectar/testar, habilitar/desabilitar e remover.
- Credenciais ficam fora do banco de logs e dos prompts.
- Allowlist de destinos, HTTPS, timeout e limites.

**Aceite:** usuário conecta/desconecta sem reiniciar o Mosaic e a lista de tools é atualizada com segurança.

### Fase 4 — Plugins declarativos locais
- Definir manifesto Mosaic v1, schema estrito, namespacing e store versionado.
- Suportar Skills e Commands declarativos e referência a servidores MCP.
- Staging, inspeção, hashes e instalação desabilitada.
- Não executar hooks/scripts arbitrários.

**Aceite:** plugin de exemplo instala, exibe seus componentes, permanece desabilitado até confirmação e pode ser desinstalado sem deixar tools registradas.

### Fase 5 — Catálogos comunitários
- Catálogo versionado que referencia repositórios/releases por versão ou commit imutável.
- Verificação de origem, licença, hash e mudanças de componentes/permissões.
- Relatos de abuso e processo de remoção.
- Sinalização de curadoria, sem alegar que revisão do catálogo garante segurança.

**Aceite:** instalação reproduzível por versão/hash e atualização nunca amplia permissões sem nova confirmação.

### Fase 6 — stdio e isolamento local
- Supervisor de processos com environment allowlist, diretório controlado, timeout, limites e encerramento.
- Mostrar comando/args antes da primeira execução e exigir consentimento.
- Preferir isolamento OS/container quando disponível.

**Aceite:** testes de processo que não inicia, sai inesperadamente, excede limites, recebe cancelamento ou tenta acessar caminhos proibidos; documentação clara de que o isolamento depende do ambiente.

### Fase 7 — Resources e Prompts MCP
- Ler resources e expor prompts de servidores conforme a política do Mosaic.
- Recursos entram no contexto somente quando relevantes e com origem registrada.
- Prompts são invocados explicitamente e nunca podem substituir as instruções centrais.

**Aceite:** resources/prompts com schema inválido, saída grande ou instrução maliciosa são tratados como dados não confiáveis.

### Fase 8 — Hooks e agentes de plugins (futuro)
- Somente depois de um modelo de eventos, permissões e sandbox explícitos.
- Começar com hooks declarativos e não executáveis; qualquer execução de código exige aprovação e isolamento.
- Agentes de plugins devem usar Task Engine existente, snapshots e políticas do Core.

**Aceite:** nenhum plugin cria um runtime paralelo nem contorna as políticas do Core.

## 12. Testes e critérios de segurança

### Protocolo e confiabilidade
- handshake e negociação de capacidades;
- lista de tools vazia, inválida, muito grande ou que muda;
- erro remoto, timeout, retry limitado, cancelamento e servidor desconectado;
- validação de JSON Schema e rejeição de argumentos desconhecidos;
- limite de tamanho e normalização de resultados textuais/estruturados;
- tools com nomes duplicados ou nomes reservados;
- snapshot por Task impede mudança silenciosa de schema durante a execução.

### Autorização e isolamento
- tool de escrita/ação externa exige aprovação de acordo com política do Core;
- servidor não consegue declarar a própria tool como confiável;
- plugin desabilitado não expõe tool/skill/prompt ao modelo;
- instalação não executa código e não ativa o pacote;
- caminho, executable, args e environment de stdio passam por validação;
- secrets não aparecem em logs, contexto, erro ou ToolResult;
- resultados MCP com prompt injection não alteram as instruções do Core;
- acesso entre projetos/conversas é isolado;
- atualização que altera permissões pede nova aprovação;
- desinstalação remove ferramentas dinâmicas e encerra processos/conexões.

### Experiência do usuário
- usuário vê origem, permissões, status e última falha;
- aprovação explica o efeito concreto, não apenas o nome técnico da tool;
- falha de servidor não bloqueia tools nativas nem corrompe a Task;
- rollback restaura versão anterior e não apaga dados criados pelo usuário sem confirmação.

## 13. Decisões em aberto antes de codificar

1. O Mosaic terá marketplace central hospedado pelo projeto ou aceitará catálogos Git arbitrários desde o início?
2. O MVP prioriza servidores remotos HTTP ou servidores locais stdio? Recomendo HTTP primeiro para reduzir risco de execução local.
3. Qual sistema será usado para armazenar segredos no Windows/Linux e como a UI solicitará tokens?
4. Quais permissões devem ser granulares no MVP: por servidor, por tool, por projeto ou uma combinação?
5. Skills serão copiadas para o formato interno do Mosaic ou carregadas do pacote por referência versionada?
6. Plugins terão licença e política de atualização obrigatórias?
7. Qual a versão mínima de Python do backend e qual versão do SDK MCP será fixada?
8. O primeiro release suportará apenas Tools ou Tools + Resources + Prompts? Recomendo Tools primeiro, Resources/Prompts depois.

## 14. Recomendação final

Implementar em camadas: **MCP Client → MCPToolAdapter → integração com política/Tool Registry → gestão manual de servidores → pacote de plugins declarativos → catálogos comunitários → stdio seguro → resources/prompts → hooks e agentes futuros**.

A principal lição do Claude Code é a composição: uma extensão pode reunir tools, conhecimento e workflows em um pacote que o usuário descobre e instala. A principal lição de segurança é que os componentes do pacote podem executar software com as permissões do usuário. O Mosaic deve combinar a experiência extensível do Claude Code com sua arquitetura de Core centralizado e aprovação explícita.

O primeiro marco de produto não é um marketplace visual; é provar que **uma tool MCP comunitária consegue aparecer no catálogo do agente, ser chamada pelo fluxo normal do Mosaic, passar pelas mesmas políticas e deixar uma trilha auditável — sem ganhar privilégios adicionais**.
