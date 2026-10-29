# Mosaic — GitHub MCP como primeiro caso de interoperabilidade
**Versão:** 1.0  
**Status:** estudo de referência para implementação; não altera o runtime.

## 1. Objetivo

Usar o plugin GitHub do catálogo oficial do Claude Code e o servidor MCP oficial da GitHub como primeiro caso concreto para validar a estratégia de interoperabilidade do Mosaic.

O objetivo não é reimplementar a API do GitHub nem copiar o runtime do Claude Code. É provar que o Mosaic consegue consumir um servidor MCP existente, expor suas ferramentas ao agente e manter as políticas, aprovações, contexto e trilha de auditoria sob autoridade do Mosaic Core.

## 2. Referências primárias

- Plugin no catálogo Claude: https://claude.com/plugins/github
- Repositório do servidor MCP oficial: https://github.com/github/github-mcp-server
- Catálogo oficial de plugins: https://github.com/anthropics/claude-plugins-official
- Diretório do plugin: https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/github
- Manifesto: `external_plugins/github/.claude-plugin/plugin.json`
- Configuração MCP: `external_plugins/github/.mcp.json`

O plugin foi identificado no catálogo oficial como plugin `github`, com autoria da GitHub. Seu arquivo `.mcp.json` declara um servidor remoto HTTP em `https://api.githubcopilot.com/mcp/`, com autenticação por header Authorization derivada de uma variável de ambiente. A documentação atual do servidor oficial também descreve autenticação OAuth para hosts compatíveis e alternativas de autenticação por token, conforme o modo de execução.

## 3. Distinção fundamental

O caso de referência possui três elementos diferentes:

1. **Plugin Claude Code:** pacote/manifesto que registra a extensão no ecossistema Claude Code.
2. **Servidor MCP GitHub:** serviço que publica ferramentas de GitHub por meio do protocolo MCP.
3. **Mosaic MCP Client + Tool Adapter:** componentes que o Mosaic precisa implementar para consumir o serviço e apresentar as ferramentas ao agente.

A compatibilidade mais importante para o MVP é com o **servidor MCP**, não com a interface interna do Claude Code. O pacote Claude serve como exemplo de descoberta, metadados e configuração. O Mosaic não deve exigir que o Claude Code esteja instalado ou em execução.

## 4. Fluxo-alvo

```text
Usuário conecta GitHub
        |
        v
Configuração do servidor MCP oficial
        |
        v
Mosaic MCP Client
  - conecta / autentica
  - negocia capacidades
  - lista ferramentas
        |
        v
MCPToolAdapter
  - namespacing
  - normalização de schema
  - origem e risco
        |
        v
Mosaic Tool Registry
        |
        v
Agent Decision / Task Engine
        |
        v
Validação + política + aprovação do Core
        |
        v
Chamada MCP -> GitHub
        |
        v
ToolResult + Task Events + histórico
```

O diagrama descreve a arquitetura proposta, não uma implementação já concluída.

## 5. Escopo do MVP de referência

### Capacidades para validar

- Conectar a um servidor MCP remoto via Streamable HTTP, conforme suporte do SDK escolhido.
- Completar autenticação sem expor tokens em prompts, logs ou resultados.
- Descobrir tools e seus schemas por meio do protocolo MCP.
- Namespacing estável, por exemplo `mcp__github__<tool_name>`, evitando colisões com ferramentas nativas.
- Apresentar ao agente somente ferramentas habilitadas e autorizadas para a tarefa.
- Executar primeiro operações de leitura.
- Testar uma ação de escrita controlada, como criar uma branch/arquivo de teste ou abrir um pull request, somente com aprovação explícita.
- Registrar origem, nome remoto, argumentos redigidos, resultado, duração e correlação com a Task.
- Lidar com desconexão, timeout, erro de autenticação, schema alterado e saída excessiva.
- Permitir desativar a conexão e remover as ferramentas descobertas do catálogo de novas tarefas.

### Fora do escopo inicial

- Implementar uma API GitHub própria dentro do Mosaic.
- Implementar marketplace completo antes de validar a conexão MCP.
- Executar comandos arbitrários vindos de plugins comunitários.
- Suportar todos os componentes específicos do Claude Code (hooks, agents, comandos internos ou LSP) no primeiro marco.
- Declarar que todo plugin Claude Code é automaticamente compatível com o Mosaic.

## 6. Caminho de teste funcional

1. Adicionar o servidor MCP oficial como integração configurada, sem instalar nem executar o pacote Claude Code.
2. Validar handshake, autenticação e listagem de ferramentas.
3. Selecionar uma tool de leitura e confirmar que ela aparece no catálogo do agente.
4. Pedir ao agente para consultar um repositório explicitamente autorizado.
5. Confirmar que a chamada passa pelo caminho normal de execução e políticas do Core.
6. Testar uma operação de escrita num repositório de teste, com aprovação antes da chamada.
7. Verificar os eventos persistidos e a ausência de credenciais nos logs.
8. Desconectar o servidor e confirmar que novas chamadas não conseguem invocar suas tools.
9. Repetir com schema inválido, timeout, servidor indisponível e output acima do limite.

Não considerar o fluxo validado até executar testes reais contra um servidor de teste e confirmar a persistência e a política no runtime.

## 7. Requisitos de segurança

- Preferir OAuth via fluxo suportado pelo servidor/host quando estiver disponível; oferecer token somente por mecanismo de credenciais seguro e documentar as permissões solicitadas.
- Nunca persistir tokens em texto aberto em tabelas de configuração, prompts, eventos ou resultados.
- Solicitar acesso mínimo necessário e explicar as permissões ao usuário.
- Tratar tools de escrita e operações remotas com impacto como ações sujeitas à política de aprovação do Core.
- Não confiar em descrições de tools, metadados do servidor ou resultados remotos como fonte de política.
- Tratar conteúdo retornado pelo GitHub como dado não confiável (inclusive instruções potencialmente maliciosas em issues, PRs, comentários e arquivos).
- Limitar timeout, tamanho de entrada/saída e concorrência; suportar cancelamento.
- Se houver mudança no conjunto de tools ou nos schemas durante uma tarefa, invalidar ou revalidar o snapshot de capacidades antes de continuar.
- Redigir tokens e outros segredos de mensagens de erro e eventos.

## 8. Critérios de aceite

- [ ] O Mosaic conecta ao servidor MCP configurado sem depender do Claude Code.
- [ ] O agente recebe apenas as tools habilitadas e autorizadas.
- [ ] Uma tool de leitura conclui com sucesso através do fluxo normal do Core.
- [ ] Uma ação de escrita é bloqueada até a aprovação exigida pela política.
- [ ] Tool calls e resultados ficam correlacionados com a Task e a origem MCP.
- [ ] Tokens não aparecem em logs, prompts, eventos ou ToolResult.
- [ ] Desconexão remove as tools das novas chamadas e trata operações pendentes.
- [ ] Erros, timeouts, schemas inválidos e respostas grandes são tratados sem interromper o restante do Mosaic.
- [ ] Testes automatizados cobrem o adapter e o caminho de política.
- [ ] Teste end-to-end documenta servidor, configuração e limitações reais.

## 9. Decisão recomendada

O primeiro marco deve ser **MCP Client + MCPToolAdapter + caminho de política do Core**, usando o servidor GitHub oficial como integração real. A gestão genérica de plugins e catálogos vem depois de provar este fluxo.

A arquitetura deve separar o adaptador de protocolo do provedor: depois de validada com GitHub, a mesma infraestrutura deve aceitar outros servidores MCP sem criar uma integração especial por fornecedor.

## 10. Limitações deste estudo

Este documento é uma análise estática das referências públicas e da arquitetura existente do Mosaic. Não declara que o Mosaic já possui cliente MCP funcional, autenticação OAuth integrada ou execução real de operações GitHub. Esses pontos exigem implementação e testes de integração.
