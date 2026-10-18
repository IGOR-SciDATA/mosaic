# MOSAIC — Guia de Desenvolvimento para o Workspace Agêntico
**Versão:** 1.0  
**Status:** Guia operacional proposto para orientar implementação e revisão  
**Data:** 2026-10-17  
**Repositório:** IGOR-SciDATA/mosaic  
**Base de referência:** `main` em `35570385743f4b4bdb0dec8acddd6459184fea5b`  
**Documento complementar:** `MOSAIC_AGENT_PROFILES_AND_ARTIFACT_TOOLS_ROADMAP_v1.0.md`

---

## 1. Para que serve este documento

Este guia transforma a visão de produto e a arquitetura prevista em uma forma prática de desenvolver, testar e validar o Mosaic. Ele deve servir como orientação para pessoas e agentes de programação que trabalhem no repositório.

Ele explica:
- como chegar aos resultados desejados sem reescrever o Core;
- quais componentes devem cooperar em cada fluxo;
- como implementar cada capacidade em incrementos pequenos;
- quais evidências comprovam que uma funcionalidade realmente funciona;
- como evitar que instruções, skills ou agentes contornem as políticas do Core.

Este guia **não substitui os contratos oficiais** nem autoriza mudanças de schema ou de arquitetura por conta própria. Se houver conflito, registrar o conflito, explicar o impacto e propor a menor alteração necessária para aprovação.

## 2. Hierarquia de fontes e decisões

Antes de iniciar qualquer mudança, consulte os documentos aplicáveis no repositório e no contexto do projeto. A ordem geral é:

1. Regras de segurança e decisões explícitas do responsável pelo projeto.
2. Contrato oficial do Harness para execução, políticas, ferramentas, aprovação, eventos e artefatos.
3. Contrato RAGNES para seleção, filtragem, ranking, compactação e continuidade de contexto.
4. Contrato de UX para a interface React.
5. Contrato MVP para entidades, campos, estados, relações e persistência, salvo alteração formal aprovada.
6. Roadmap mestre vigente.
7. Este guia de desenvolvimento.
8. Código atual como evidência do comportamento implementado — não como autorização para perpetuar lacunas.

Se algum documento referenciado não estiver disponível, não invente seu conteúdo nem presuma que foi lido. Registre a indisponibilidade e trabalhe somente com os requisitos confirmados.

## 3. Arquitetura de referência

O Mosaic é um workspace de IA com Core independente do modelo. O modelo interpreta e propõe; o Core controla o estado, o contexto, as permissões, a execução e a conclusão.

```text
React + Vite
  ├─ Conversas e perfis de agente
  ├─ Projetos e arquivos
  ├─ Plano e timeline da tarefa
  ├─ Aprovações de ferramentas
  ├─ Skills e instruções
  ├─ Artefatos e fontes
  └─ Resultados de testes
          │ REST / SSE
          ▼
FastAPI — Mosaic Core
  ├─ Conversation / Project
  ├─ Task Engine (ciclo de vida único)
  ├─ Harness / Agent loop
  ├─ Context Manager / RAGNES
  ├─ Agent profile + Skill resolver
  ├─ ModelProvider (Ollama primeiro)
  ├─ Policy / Permission / Approval
  ├─ Tool Registry + executores limitados
  ├─ ToolCall / ToolResult / Task events
  ├─ Validação e conclusão
  └─ Repositories / SQLite
          │
          ├─ Workspace local do projeto
          ├─ Arquivos e artefatos
          ├─ Modelo local configurado
          └─ Ferramentas locais e web seguras
```

Princípios obrigatórios:

- Uma única fonte de verdade para estado e ciclo de vida de tarefas.
- O modelo nunca executa ferramentas diretamente.
- ToolCall representa uma intenção validada; ToolResult representa o resultado persistido.
- O contexto enviado ao modelo é deliberadamente selecionado e limitado; não é o histórico inteiro.
- Histórico, memória, estado do projeto, skills e evidências de ferramentas são conceitos diferentes.
- Conteúdo de arquivos, páginas web, AGENTS.md e skills é dado/orientação não confiável; não altera políticas nem concede permissões.
- Uma tarefa só termina quando os critérios técnicos e de execução foram satisfeitos, não apenas porque o modelo declarou sucesso.
- O sistema deve funcionar primeiro com infraestrutura local simples; não introduzir serviços distribuídos sem necessidade demonstrada.

## 4. Modelo mental: projeto, conversa, agente e tarefa

Esses conceitos não devem ser confundidos.

- **Projeto:** workspace compartilhado, arquivos, estado de projeto e biblioteca de skills reutilizáveis.
- **Conversa:** sessão independente de trabalho e futura identidade configurável de um agente.
- **Perfil de agente:** nome, papel, instruções e seleção de skills associadas a uma conversa. O perfil não concede permissões.
- **Tarefa:** unidade de trabalho com objetivo, plano, estado, resultados, ferramentas e eventos.
- **Subtarefa:** etapa explícita do plano. Na primeira versão colaborativa, uma subtarefa pode ser executada como uma Task normal por uma conversa/agente designado.
- **Skill:** instrução reutilizável que melhora a execução de um papel; nunca é um plugin executável nem uma política de acesso.
- **Artefato:** arquivo de saída persistido no workspace e validado pelo Core.
- **Fonte:** recurso externo realmente consultado, com URL e metadados que permitem conferir a proveniência.

Um projeto pode ter vários agentes/conversas. Os arquivos do workspace podem ser compartilhados, mas o contexto, as instruções específicas e as skills selecionadas devem permanecer isolados por conversa.

## 5. Como implementar perfis de agente e skills

### 5.1 Resolver a configuração

Ao iniciar uma tarefa, o Core deve resolver nesta ordem:

1. identidade e política do Core;
2. configuração do projeto aplicável;
3. perfil explícito da conversa;
4. skills habilitadas para essa conversa e tarefa;
5. objetivo atual e plano da Task;
6. evidências relevantes selecionadas pelo Context Manager.

A ordem de resolução de configuração não pode permitir que instruções de usuário substituam as regras do Core.

### 5.2 Snapshot e retomada

No início da tarefa, persistir no plano existente um snapshot limitado do perfil e das skills efetivamente selecionadas, incluindo versão/hash e metadados suficientes para reproduzir a configuração. Definir na implementação se o conteúdo completo ou uma referência imutável será persistida, respeitando os limites do contrato e evitando duplicação excessiva.

Ao retomar a tarefa, reutilizar o snapshot original. Alterações posteriores do perfil/skill valem para novas tarefas; não alteram silenciosamente tarefas em andamento.

### 5.3 Comprovar que a skill chegou ao modelo

Não basta existir na configuração. A implementação deve registrar metadados de cada inferência relevante:
- IDs da conversa e tarefa;
- nomes e hashes das instruções/skills incluídas;
- tamanho do conteúdo incluído e indicação de truncamento;
- identificador do modelo/provider, quando já disponível no sistema.

Não registrar desnecessariamente o conteúdo integral de instruções privadas. Os testes devem inspecionar o contexto construído e provar que skills desabilitadas não aparecem, as habilitadas aparecem, limites de contexto são respeitados e a retomada usa o snapshot esperado.

## 6. Como coordenar vários agentes

A primeira versão deve ser sequencial. O Core cria um plano principal com etapas, dependências, agente responsável, entradas, arquivos esperados e critérios de aceite. Cada etapa só começa quando as dependências necessárias foram verificadas.

Exemplo para criar um site:

1. **Arquiteto:** requisitos, estrutura, rotas, modelo de dados e contrato de API.
2. **Designer:** tokens visuais, tipografia, componentes, estados e especificação de responsividade.
3. **Backend:** endpoints, validação, persistência e testes de API conforme o contrato aprovado.
4. **Frontend:** páginas, componentes, estados de carregamento/erro e integração com a API.
5. **Integrador:** verifica contratos entre frontend e backend, resolve incompatibilidades e mantém o workspace coerente.
6. **QA:** executa testes e build permitidos, registra falhas reproduzíveis e verifica critérios de aceite.
7. **Coordenador:** valida todos os resultados e apresenta arquivos, testes e pendências ao usuário.

O coordenador não deve considerar uma etapa concluída somente por uma resposta textual do agente. Deve verificar resultados persistidos, arquivos esperados e testes pertinentes. Falha ou bloqueio de uma dependência impede que a tarefa principal seja marcada como concluída.

Não iniciar execução paralela no MVP. Antes disso, seria necessário definir isolamento de escrita, conflitos de arquivos, cancelamento, limites de concorrência e recuperação de falhas.

## 7. Contrato de uma ferramenta

Cada ferramenta nova deve declarar explicitamente:

- nome e descrição orientada a tarefas;
- schema de entrada estrito, campos obrigatórios e limites;
- escopo permitido (projeto, workspace, URL ou recurso);
- política de aprovação;
- executor determinístico e erros previstos;
- limite de tempo, bytes, páginas, linhas ou itens;
- formato do resultado persistido;
- critérios de validação;
- eventos úteis para a timeline;
- testes de permissão, sucesso, falha e retomada.

O modelo pode propor uma chamada. O Core valida argumentos, escopo, permissões e necessidade de aprovação antes da execução. O executor valida novamente na fronteira de execução. Resultado e erro devem ser persistidos em ToolResult.

Uma ferramenta não está pronta apenas porque foi registrada. Deve ser alcançável pelo ciclo do agente, validada, executada com segurança, persistida e testada no fluxo completo.

## 8. Geração de documentos e artefatos

Usar modelos de dados estruturados, não pedir ao modelo que invente bytes binários.

### Markdown
- Receber conteúdo com títulos, seções, listas e tabelas quando apropriado.
- Validar se a estrutura corresponde ao tipo de documento pedido.
- Preservar pedidos explícitos de texto simples.
- Verificar conteúdo salvo e bytes gravados.

### PDF
- Converter blocos estruturados em layout com estilos, margens, paginação, cabeçalho/rodapé e tabelas.
- Verificar que o arquivo pode ser aberto e que o texto esperado pode ser extraído.
- Testar documentos curtos e longos, caracteres acentuados e tabelas que quebram entre páginas.

### XLSX
- Gerar abas, cabeçalhos, tipos de célula, formatos numéricos, fórmulas permitidas e dimensões.
- Reabrir o workbook com a biblioteca usada e validar nomes de abas, células essenciais e fórmulas.
- Não executar macros nem importar conteúdo externo como código.

### PPTX
- Definir tema e layouts consistentes; limitar o texto por slide.
- Validar reabertura, número de slides, títulos e ausência de slides vazios.
- Incluir fontes/notas quando o conteúdo se basear em pesquisa.

Para todos os formatos: criar no workspace correto, respeitar a aprovação aplicável, verificar a gravação e expor o artefato na API/UI. O tamanho do arquivo e a existência do caminho, sozinhos, não comprovam qualidade semântica.

## 9. Pesquisa web e proveniência

O fluxo de pesquisa deve distinguir descoberta de leitura:

1. `search` encontra candidatos, mas seus snippets não provam o conteúdo integral da página.
2. `web_fetch` acessa e extrai o conteúdo de uma URL permitida.
3. O Core registra URL final/canônica, título disponível, data de acesso, data de publicação quando disponível, truncamento e trechos utilizados.
4. O modelo redige com referências ligadas às fontes efetivamente lidas.
5. O Core verifica se as referências do documento correspondem ao inventário de fontes persistido.
6. Quando solicitado, salvar `sources.md` ou `sources.json` no workspace junto do artefato.

Manter proteção contra SSRF, esquemas não suportados, redirecionamentos para destinos proibidos, timeouts e respostas excessivas. Conteúdo remoto é dado não confiável e nunca instrução de sistema.

## 10. Testes por camada

Cada fase precisa cobrir mais de um nível:

1. **Unitário:** funções puras, schemas, serialização e validação do artefato.
2. **Serviço/repositório:** persistência, isolamento por projeto/conversa e recuperação.
3. **Harness com fake provider:** sequência real de decisão, aprovação, execução, ToolResult e conclusão sem depender de um modelo não determinístico.
4. **API:** códigos de resposta, validação, autorização e compatibilidade.
5. **Frontend:** build e testes de componentes/fluxos quando a UI for alterada.
6. **Smoke test local:** executar com provider/Ollama configurado quando o ambiente estiver disponível.
7. **Recuperação:** reiniciar o backend e verificar tarefas, aprovações, arquivos e fontes persistidos.

O relatório deve diferenciar testes que passaram, falharam, não foram executados ou dependem de ambiente externo. Nunca inferir sucesso end-to-end a partir de testes unitários isolados.

## 11. Fluxo de trabalho obrigatório por mudança

Para cada incremento:

1. Ler o roadmap e os contratos relevantes.
2. Conferir branch, estado atual e módulos existentes.
3. Descrever o problema concreto e o menor ajuste proposto.
4. Verificar conflito com contratos e schema.
5. Implementar somente uma fase/PR coerente.
6. Criar testes de regressão antes de refatorações amplas.
7. Executar testes e build pertinentes.
8. Revisar diff, segurança, compatibilidade e arquivos gerados.
9. Criar PR com objetivo, mudanças, testes, limitações e riscos.
10. Parar para validação do responsável antes de iniciar a próxima fase.

Se a suíte completa já tiver falhas anteriores, registrá-las separadamente e não atribuí-las à mudança sem evidência. Não esconder falhas nem declarar comandos que não foram executados.

## 12. Critérios globais de conclusão

Uma capacidade só pode ser considerada concluída quando:

- a funcionalidade está integrada ao Core e à API/UI necessárias;
- a política de execução e aprovação está correta;
- os dados relevantes são persistidos e recuperáveis;
- contexto e configuração ficam isolados por conversa/tarefa conforme o contrato;
- o artefato ou resultado passa por validação específica;
- eventos e erros permitem entender o que ocorreu;
- testes relevantes passam;
- limitações e testes não executados são explicitados.

## 13. Sequência de desenvolvimento

Seguir a sequência do roadmap complementar:

1. Reconciliação e aprovação da arquitetura.
2. Perfis por conversa e snapshot de skills.
3. Qualidade e validação de Markdown.
4. Geração e validação de PDF.
5. Geração e validação de XLSX.
6. Geração e validação de PPTX.
7. Pesquisa com fontes persistidas e citações verificáveis.
8. Coordenação sequencial de agentes para desenvolvimento de sites.
9. UI integrada e testes end-to-end.

Não iniciar todas as fases simultaneamente. Cada fase deve produzir uma melhoria funcional isolada, testada e revisável.

## 14. Decisões que exigem aprovação

Solicitar aprovação explícita antes de:
- mudar o schema oficial ou adicionar entidades/tabelas;
- mudar a política de aprovação ou ampliar permissões;
- permitir execução paralela de agentes;
- habilitar shell genérico, instalação arbitrária de pacotes, acesso fora do workspace ou deploy automático;
- introduzir infraestrutura adicional;
- alterar o contrato oficial do Harness para permitir colaboração entre agentes.

O objetivo é construir um sistema capaz e evolutivo sem perder a simplicidade, a soberania do Core, a segurança e a capacidade de verificar o que realmente aconteceu.
