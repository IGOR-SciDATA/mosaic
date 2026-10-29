# Regra arquitetural — compatibilidade com plugins Claude Code

**Versão:** 1.0  
**Status:** requisito normativo para a implementação de MCP e extensões do Mosaic  
**Data:** 2026-10-29

## 1. Regra obrigatória

O Mosaic DEVE usar como referência de compatibilidade o formato e os padrões de plugins existentes do Claude Code, usando o plugin oficial do GitHub como primeiro caso real de implementação e teste.

Esta regra não é apenas uma inspiração visual ou conceitual. A implementação deve provar que consegue interpretar a estrutura de um plugin de referência, resolver sua configuração MCP e utilizar as ferramentas disponibilizadas por ele sem exigir que o Claude Code esteja instalado ou em execução.

O formato nativo de plugin do Mosaic não pode substituir essa compatibilidade como caminho principal. Um formato interno pode existir como camada de normalização ou extensão futura, desde que não impeça a leitura e a execução dos plugins de referência suportados.

## 2. Plugin de referência obrigatório: GitHub

A implementação deve estudar e testar, no mínimo, os seguintes artefatos do plugin GitHub oficial:

- `.claude-plugin/plugin.json`: metadados e identidade do plugin;
- `.mcp.json`: declaração do servidor MCP e sua configuração;
- o endereço do servidor MCP e o mecanismo de autenticação declarados pelo plugin;
- a origem e os metadados do pacote no catálogo/marketplace oficial.

Referências oficiais:

- Plugin GitHub: https://claude.com/plugins/github
- Repositório do servidor MCP GitHub: https://github.com/github/github-mcp-server
- Plugin no repositório oficial: https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/github
- Repositório de plugins oficiais: https://github.com/anthropics/claude-plugins-official
- Especificação MCP: https://modelcontextprotocol.io/

Os arquivos e campos reais devem ser inspecionados na versão/commit usado no teste. Não se deve assumir que todos os plugins terão exatamente os mesmos componentes ou campos.

## 3. Separação obrigatória de camadas

A implementação deve manter separadas estas responsabilidades:

1. **Compatibilidade de pacote:** localizar, ler e validar metadados e configurações do formato de plugin de referência.
2. **Cliente MCP:** conectar ao servidor configurado, autenticar, negociar capacidades, descobrir ferramentas e executar chamadas de acordo com o protocolo MCP suportado.
3. **Adaptador de ferramentas:** converter ferramentas MCP em ferramentas disponíveis ao Mosaic, com nomes qualificados, schemas validados e origem rastreável.
4. **Autoridade do Mosaic Core:** aplicar permissões, políticas, aprovações, limites, redaction de segredos, auditoria e persistência.
5. **Catálogo/marketplace:** descobrir versões e origens de pacotes; catálogo não deve executar plugins nem conceder confiança automaticamente.

O formato de plugin Claude Code é um formato de empacotamento/configuração específico do ecossistema. MCP é o protocolo de comunicação entre cliente e servidor. A compatibilidade com um não deve ser confundida com suporte automático a todos os recursos do outro.

## 4. Escopo inicial e comportamento esperado

O primeiro marco de compatibilidade deve:

- ler e validar o manifesto do plugin de referência;
- interpretar sua configuração MCP sem exigir o runtime Claude Code;
- suportar o transporte e a autenticação necessários ao caso GitHub, usando mecanismos seguros;
- conectar ao servidor MCP oficial do GitHub;
- listar e validar as tools anunciadas pelo servidor;
- expor somente tools explicitamente habilitadas e autorizadas;
- executar ao menos uma operação de leitura através do fluxo normal de ferramentas do Mosaic;
- provar uma operação de escrita controlada, como criar branch ou pull request, somente após aprovação explícita;
- registrar origem, tool, task, resultado redigido e status;
- tratar desconexão, timeout, falha de autenticação, schema inválido e mudança no conjunto de tools.

Se o servidor oficial mudar seu transporte, autenticação ou formato de configuração, a implementação deve documentar a diferença e adaptar o conector sem remover a regra de compatibilidade do pacote.

## 5. Preparação para marketplace

A arquitetura deve permitir adicionar outros plugins do ecossistema sem escrever uma integração especial para cada fornecedor, desde que os componentes usados sejam suportados pelo Mosaic.

Para isso:

- separar parser/resolvedor do formato de plugin do cliente MCP genérico;
- tratar nomes, versões, origem, publisher e hashes como metadados de proveniência;
- instalar inicialmente em staging e manter extensões desabilitadas até ativação explícita;
- validar estritamente os campos e rejeitar componentes desconhecidos ou não suportados;
- mostrar permissões solicitadas e mudanças de versão ao usuário;
- não executar hooks, scripts ou comandos arbitrários só porque aparecem em um pacote;
- não declarar todo plugin Claude Code automaticamente compatível;
- manter compatibilidade incremental e documentada por tipo de componente.

O primeiro suporte deve priorizar plugins que declaram servidores MCP. Skills, comandos, hooks, agentes, LSP e demais componentes específicos do Claude Code precisam ser avaliados e adicionados em fases separadas, conforme seus modelos de segurança e execução. A presença desses componentes num pacote não autoriza ignorá-los silenciosamente: devem ser reconhecidos, reportados como suportados ou não suportados e tratados de forma segura.

## 6. Segurança não negociável

- Segredos não podem aparecer em prompts, logs, eventos ou resultados de ferramentas.
- A instalação ou descoberta não ativa automaticamente um plugin.
- Nenhum plugin ou servidor pode definir sua própria política de confiança.
- Todas as chamadas passam pela validação e política do Mosaic Core.
- Ações de escrita e de impacto externo exigem a aprovação determinada pela política.
- Conteúdo retornado por servidores é dado não confiável e não pode substituir instruções centrais.
- Desabilitar ou desconectar um servidor impede novas chamadas às suas ferramentas.
- Mudanças relevantes em tools, schemas, versões ou permissões devem ser detectadas e revalidadas.

## 7. Critérios de aceite da regra

A regra só será considerada implementada quando houver evidência verificável de que:

1. o Mosaic interpreta os artefatos reais do plugin GitHub de referência;
2. conecta ao servidor MCP sem depender do Claude Code;
3. descobre e lista as ferramentas reais;
4. executa uma ferramenta de leitura pelo caminho normal do Core;
5. bloqueia uma ação de escrita até a aprovação exigida;
6. não expõe credenciais em logs, prompts ou resultados;
7. desconectar/desabilitar remove as ferramentas das novas chamadas;
8. testes automatizados cobrem parser/configuração, adapter, políticas e falhas;
9. um teste end-to-end documenta a configuração, os resultados e as limitações;
10. a documentação distingue claramente recursos realmente suportados de componentes ainda não suportados.

Pesquisa estática, mocks isolados ou um servidor MCP falso não bastam, sozinhos, para declarar compatibilidade real com o plugin GitHub. Podem validar partes do sistema, mas devem ser complementados por teste de integração real.

## 8. Aplicação ao trabalho de implementação

Esta regra deve ser lida em conjunto com:

- `docs/MOSAIC_MCP_AND_COMMUNITY_PLUGINS_RESEARCH_v1.0.md`
- `docs/MOSAIC_GITHUB_MCP_REFERENCE_IMPLEMENTATION_v1.0.md`
- o contrato de implementação do MVP e a arquitetura atual do Mosaic.

Se algum documento anterior sugerir apenas um formato próprio de plugin ou tratar o GitHub somente como servidor MCP manual, esta regra prevalece: o primeiro objetivo é provar compatibilidade com o formato real do plugin GitHub de referência e, a partir dele, estabelecer uma base reutilizável para interoperabilidade com o marketplace.
