# Fase 13 — OpenAI Responses API

## Configuração

A OpenAI é um provider explícito do Mosaic. A chave deve existir somente no ambiente do processo backend:

```bash
export OPENAI_API_KEY="sua-chave"
```

Reinicie o backend após configurar a variável. Não coloque a chave no frontend, em `Model.configuration`, no banco, em prompts ou em arquivos versionados. O endpoint `GET /models/status?provider=openai` informa se a variável está configurada; isso não representa um teste de conectividade ou de quota.

## Cadastro do modelo

Na interface, abra **Configurações → Cadastrar modelo**, escolha **OpenAI API (Responses)** e informe um identificador de modelo habilitado para sua conta, por exemplo `gpt-4.1-mini`. A seleção fica persistida no campo `Model.provider`. O Mosaic não troca automaticamente para Ollama se a credencial, rede, modelo ou quota falhar.

O campo `num_predict`, quando positivo, é mapeado para `max_output_tokens`. Parâmetros exclusivos do Ollama são ignorados pelo adaptador OpenAI. Timeout pode ser configurado como `request_timeout_seconds` (1 a 600 segundos); não é necessário persistir qualquer segredo na configuração do modelo.

## Comportamento e limites

- Usa `POST /v1/responses` para respostas e streaming SSE.
- Adapta chamadas de ferramentas ao formato de funções da Responses API; o Core continua validando e executando ferramentas.
- Mensagens de erro são sanitizadas; o corpo de erro remoto e a chave não são registrados pelo provider.
- Erros de autenticação, modelo inexistente, quota/limite, rede e timeout não acionam fallback silencioso.
- O status da OpenAI significa apenas que `OPENAI_API_KEY` está presente no ambiente backend. A chamada real valida permissões, modelo, rede e quota.

## Verificação

Execute os testes do backend com `pytest`. Para smoke test real, configure a variável no ambiente local autorizado e selecione explicitamente um modelo OpenAI; nunca compartilhe a chave nos logs, screenshots ou relatórios.
