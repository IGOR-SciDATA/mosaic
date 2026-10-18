# Mosaic — Resiliência e recuperação v1.0

**Status:** política de recuperação implementada em branch; aceite depende da CI.  
**Princípio:** após reinício, o Core nunca presume que uma ferramenta interrompida pode ser repetida com segurança.

## Política no startup

- Tasks persistidas em `planning`, `executing` ou `validating` são marcadas como `failed`, com evidência estruturada `recovery.status=interrupted_by_restart`.
- A Task fica identificada como recuperável, mas a retomada exige ação explícita do usuário. Não existe retry automático.
- ToolCalls que estavam em `executing` são marcadas como falhas; se não havia ToolResult, o Core registra um resultado de interrupção.
- Actions em execução são marcadas como falhas e exigem revisão.
- Tasks em `awaiting_approval`, ToolCalls pendentes e decisões de aprovação não são aprovadas nem executadas automaticamente.
- A rotina é idempotente: Tasks já terminais não são reprocessadas e eventos de interrupção não são duplicados por uma segunda chamada de recuperação.

## Limites de segurança

- Um efeito externo pode ter ocorrido antes do crash, mesmo quando o ToolResult não foi persistido. O Core registra a interrupção e não tenta repetir a operação.
- A recuperação não afirma que um artefato parcial está válido. A verificação de hash/reabertura permanece responsável por confirmar a integridade.
- Não há retry automático de provider ou ferramenta, nem fallback de modelo.
- A política é implementada no backend e executada durante a inicialização da API; a UI não é autoridade de estado.

## Evidência e validação

`backend/tests/test_recovery.py` cobre Task órfã, ToolCall/ToolResult interrompidos, Action interrompida, preservação de aprovação pendente, idempotência e cancelamento antes da escrita de um artefato.

Ainda exige validação adicional: crash real de processo entre cada etapa de escrita, E2E com provider local real, orçamento computacional por Task e avaliação de prompt injection/exfiltração. Estes pontos não são considerados concluídos por testes unitários ou pelo build frontend.
