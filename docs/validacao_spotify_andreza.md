# Andreza Lira — Validação do ETL 1 / Spotify

## Atualização: acesso real em 08/11/2026

Esta atualização substitui a situação anterior de ausência de credenciais descrita no histórico abaixo. As credenciais foram configuradas localmente e a autenticação retornou HTTP 200. Uma consulta inicial de faixa também foi bem-sucedida.

Foi iniciada a coleta real dos 400 IDs únicos dos 30 CSVs. O registro da coleta contabilizou respostas bem-sucedidas para 300 faixas e 296 artistas antes de o Spotify impor HTTP 429. Uma consulta diagnóstica confirmou o limite e retornou `Retry-After: 85962` segundos, aproximadamente 24 horas. Não foram registradas faixas com HTTP 404 nesse trecho. Isso não permite concluir que as 400 faixas serão encontradas.

O processo original acumula os payloads em memória antes da carga. A sessão não estava mais disponível ao tentar interromper a espera longa do cliente. Portanto, os logs comprovam as respostas recebidas, mas esses payloads não estão persistidos na tabela RAW. O arquivo `spotify_andreza_real.db` foi criado com esquema e não comprova carga concluída. Não há validação final de gêneros, álbuns, duração ou lançamento dos 400 IDs.

Foi preparado `validar_spotify_real.py` para salvar cada resposta completa no banco assim que recebida, manter cache de artistas e reutilizar respostas salvas ao executar novamente. Ele encerra a coleta de forma controlada diante de 429 e identifica a carga como parcial. O teste de pausa e retomada com API falsa passou: preservou a primeira faixa, interrompeu na segunda e retomou sem consultar novamente a primeira. Esse novo comportamento não foi testado contra a API real após o limite para evitar novas requisições durante a espera.

Retomada estimada: **09/11/2026 após aproximadamente 01h54, horário de Brasília**. O servidor pode estabelecer novos limites. Depois desse horário, executar no diretório do projeto, com Python e dependências instalados:

```powershell
python validar_spotify_real.py
```

Se houver outra pausa por limite, aguardar o prazo informado pelo Spotify e executar novamente o mesmo comando. O banco e o cache são reutilizados. A conclusão deve ser confirmada no JSON `spotify_validacao_real.json`: 400 respostas persistidas e ausência de IDs pendentes. O comando grava os resultados na pasta `outputs` deste ambiente. Não publicar `.env`, tokens ou segredos.

**Fala atualizada para o professor:** “Validei os 30 CSVs e configurei o acesso real ao Spotify. A API respondeu a 300 faixas e 296 artistas durante a tentativa, mas impôs um limite de requisições com espera de aproximadamente 24 horas. Registrei esse impedimento e preparei uma coleta com salvamento por faixa e retomada. A validação completa dos metadados permanece pendente. Os testes anteriores passaram e acrescentei um teste de pausa e retomada que também passou.”

## Histórico da validação inicial

Data: 08/11/2026. Repositório: https://github.com/gabriellemnunes/projeto-spotify-youtube
Versão analisada: `469a7b6914733f51d428a1ed99fb5b6b751f07e9`.

## Resultado e situação das tarefas

Foi concluída a auditoria dos 30 CSVs e a carga isolada dos dados dos Charts. O enriquecimento real pela API Spotify permanece pendente porque não há `SPOTIFY_CLIENT_ID` e `SPOTIFY_CLIENT_SECRET`. A usuária confirmou que ainda não possui essas credenciais. Nenhum resultado de API foi inventado ou substituído por simulação no banco entregue.

| Tarefa | Resultado comprovado |
|---|---|
| Executar ETL 1 real com 30 CSVs | Parcial: leitura, transformação e carga dos Charts executadas; fluxo real completo depende das credenciais |
| Confirmar enriquecimento Spotify | Pendente; nenhuma consulta autenticada executada |
| Validar artistas, gêneros, álbuns e duração | Nomes de artistas dos CSVs conferidos estruturalmente; demais metadados oficiais pendentes |
| Verificar falhas e faixas não encontradas | Tratamento testado com API falsa; ocorrências reais ainda não medidas |
| Registrar resultados | Relatório, JSON de auditoria, banco SQLite e código com correção entregues |

## Dados conferidos

- 30 arquivos com 200 linhas cada: 6.000 linhas no total.
- Países: Argentina, Brasil, Espanha, Japão, México e Estados Unidos.
- Datas identificadas nos arquivos: 01, 08, 15, 22 e 29 de outubro de 2026.
- O código seleciona `head(50)` de cada arquivo: 1.500 observações de ranking e 400 IDs únicos de faixas. As outras 4.500 posições não entram no ETL por essa regra.
- Todos os 30 arquivos passaram nos testes de colunas obrigatórias, ausência de nulos obrigatórios, posições 1–200, URIs válidas e únicas por arquivo, streams não negativos e semanas no chart positivas.
- Nenhuma duplicidade na chave país/data/faixa do Top 50.
- Índice próprio de popularidade calculado: mínimo 8,9 e máximo 100. Não é a popularidade oficial do Spotify. Fórmula: `100 × (0,6 × streams/maior_streams_do_país_semana + 0,4 × (51−posição)/50)`.

A estrutura dos arquivos foi validada. Isso não comprova, por si só, a autenticidade de cada número por comparação com o portal Charts. Datas e países foram obtidos dos nomes dos arquivos, conforme o código existente.

## Extração, transformação e carga

Foi executado `auditar_etl1.py`, que chama as funções existentes de leitura dos Charts, conversão RAW e transformação. Foi criado o banco `spotify_charts_sem_enriquecimento.db` com 1.500 linhas em `raw_spotify_chart`, 1.500 em `spotify_chart` e 400 em `spotify_faixa`. `raw_spotify_track` permanece vazia.

As faixas desse banco têm apenas informações derivadas dos CSVs. Duração, álbum, lançamento e gêneros permanecem ausentes. A separação de artistas por vírgula é uma aproximação do fallback e precisa ser substituída pelos artistas estruturados da API para validação semântica.

Cada carga foi repetida e as quantidades permaneceram iguais, confirmando o upsert sem duplicação nesse cenário. O banco é uma evidência de auditoria CSV, não uma execução completa do pipeline real e não deve substituir o banco de produção do grupo.

O JSON de auditoria contém inventário, SHA-256 de cada CSV e cobertura das 30 combinações país/semana.

## Correção realizada e testes

Foi identificado um defeito em `transformar_faixas`: quando todas as buscas de metadados falhavam, o DataFrame não tinha colunas como `duracao_ms`, causando erro ao transformar o fallback dos Charts. A correção preserva o esquema mesmo sem respostas da API. Um teste novo verifica deduplicação das faixas, preservação do nome e quantidade de artistas e ausência explícita dos metadados indisponíveis.

Verificação executada: **63 testes passaram em 6,23 segundos**, abrangendo `test_csvs_spotify.py`, `test_extract_spotify.py`, `test_etl1_sem_metadados.py` e `test_transformacoes.py`. Os testes de extração usam um cliente falso e cobrem 429, 503, limite de tentativas, 404 sem repetição, artista sem gênero, falha na consulta de artista, cache e preservação da faixa sem metadados. Não representam chamadas reais.

A validação da configuração real para a etapa 1 foi executada e interrompeu corretamente com: `ValueError: Modo real exige as variáveis: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET`.

## Pontos a verificar quando houver acesso real

1. Obter credenciais de um app autorizado no Spotify Developer e preencher `.env` localmente. Não compartilhar o segredo nem versionar esse arquivo. Consultar as condições atuais de acesso no painel do Spotify.
2. Configurar `MODO=real`, os seis países e um banco novo. Para SQLite local, remover a `DATABASE_URL` de PostgreSQL do exemplo ou apontar explicitamente para um arquivo separado.
3. Executar `python -m src.pipeline --modo real --etapas 1`. Essa opção limita a execução ao trabalho da Andreza e não exige a chave do YouTube.
4. Comparar os 400 IDs esperados com as respostas em `raw_spotify_track` e registrar sucesso, 404, falha de autenticação, limite de requisições e falhas transitórias separadamente.
5. Validar IDs retornados, nomes e artistas oficiais, duração positiva, álbum, precisão da data de lançamento, artistas convidados e gêneros. Gênero ausente não prova erro: a API pode retornar lista vazia.
6. Verificar falhas de artistas nos logs: uma faixa pode ser carregada mesmo se a consulta de gêneros falhar. O código atual não distingue esse caso de um artista legitimamente sem gêneros na tabela tratada.
7. Registrar cobertura de cada campo, divergências com o CSV e exemplos de respostas. A taxa de sucesso e a quantidade de faixas não encontradas só podem ser informadas depois dessa coleta.

## Fala sugerida para o professor

“Minha responsabilidade foi validar o ETL 1, que combina os rankings semanais do Spotify Charts com os metadados da API. Com apoio de automação, auditei os 30 arquivos dos seis países nas cinco semanas de outubro. Eles possuem 6.000 linhas, mas a regra do projeto usa o Top 50 de cada arquivo, resultando em 1.500 posições e 400 faixas únicas.

Validei estrutura, posições, identificadores, campos obrigatórios e duplicidades. Executei as transformações e a carga em um banco isolado e repeti a carga para verificar que ela não duplicava os registros. Também corrigi uma falha que ocorria quando nenhuma faixa recebia metadados e executei 63 testes relacionados aos CSVs, às transformações e ao tratamento de erros.

O enriquecimento real ficou pendente porque ainda não tenho as credenciais do Spotify Developer. Portanto, não afirmo que gêneros, álbuns e duração foram confirmados pela API. Entreguei as evidências do que foi executado e o procedimento para concluir essa etapa assim que o acesso estiver disponível.”

## Perguntas que podem surgir

**Por que 400 faixas e 1.500 posições?** A mesma faixa aparece em várias semanas e pode aparecer em vários países. Metadados são buscados uma vez por ID único.

**Como são tratados os gêneros?** A API consulta os artistas; a transformação reúne seus gêneros sem repetição. A ausência de gêneros é preservada como dado ausente.

**O que acontece se uma faixa não for encontrada?** O extrator registra o erro e mantém nome e artistas do CSV. A correção também permite transformar os dados quando todas as consultas falham.

**O que é RAW?** É a camada que preserva os dados extraídos antes das regras de transformação. Neste trabalho, a RAW dos Charts foi preenchida; a RAW de respostas Spotify não foi.

**O que falta para concluir?** Credenciais válidas, coleta autenticada e uma nova auditoria que quantifique os metadados recebidos e as falhas reais.
