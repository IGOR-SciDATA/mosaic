# Fase 14 — Biblioteca de agentes reutilizáveis por projeto

## Escopo desta entrega

Esta fase adiciona CRUD de perfis de agente por projeto e invocação pontual com `/slug`. Não implementa swarm, delegação paralela, nova conversa automática, nova tabela ou alteração de permissões. A execução continua no Core e no Task Engine existentes.

## Persistência e isolamento

Os perfis ficam em `Project.state["agent_library"]`, no JSON já existente. Slugs são únicos dentro do projeto e aceitam apenas letras minúsculas, números e hífens simples. Cada projeto pode manter até 30 perfis; cada perfil possui nome, descrição, instruções, versão, SHA-256 e Skills versionadas com hash individual.

A edição de um perfil incrementa sua versão. Uma Skill preserva sua versão quando conteúdo e estado habilitado não mudam; alterações incrementam a versão e recalculam o hash. Skills desabilitadas não são incluídas nas instruções ativas do perfil. A biblioteca inteira é excluída do contexto geral do projeto para evitar que perfis inativos sejam injetados em conversas comuns.

## Invocação

Em uma conversa de projeto, escreva:

```text
/backend-reviewer Revise este endpoint e identifique riscos.
```

O Core resolve o slug no projeto da conversa, remove o comando do objetivo persistido e injeta as instruções e Skills habilitadas somente nessa execução. Não cria nem troca de conversa. Slug inexistente, comando vazio e invocação sem projeto falham claramente.

Em tarefas iniciadas por `POST /tasks/start` ou em Tasks pendentes executadas por `POST /tasks/{id}/run`, o Core persiste um snapshot do agente dentro de `Task.plan.agent_library_snapshot`. A retomada usa esse snapshot, e não a versão atual da biblioteca. Snapshots são validados por SHA-256 antes de serem aplicados. A orientação do agente e as Skills nunca concedem permissões; políticas, ferramentas e aprovações continuam sob controle do Core.

## API

- `GET /projects/{project_id}/agents`
- `POST /projects/{project_id}/agents`
- `GET /projects/{project_id}/agents/{slug}`
- `PUT /projects/{project_id}/agents/{slug}`
- `DELETE /projects/{project_id}/agents/{slug}`

O frontend expõe a aba **Biblioteca** para criar, editar e remover perfis e Skills.

## Verificação

Execute `python -m pytest -q` no diretório backend e `npm run build` no frontend. A suíte específica cobre CRUD, unicidade de slug, isolamento por projeto, versão/hash de Skills, integridade e imutabilidade do snapshot, invocação em conversas, snapshot persistido em Task, comando desconhecido e ausência de injeção de perfis inativos no contexto comum.

O teste automatizado de unidade/integrado não substitui uma validação manual de interface e de runtime com o provider configurado. Não declare a Fase 14 como concluída até a CI, revisão de segurança e validação do diff terminarem.
