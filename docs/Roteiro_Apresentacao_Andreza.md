# Roteiro de apresentação — Andreza, ETL 1

## Fala de aproximadamente dois minutos

Minha responsabilidade foi o ETL 1, que integra os rankings do Spotify Charts com metadados da API do Spotify. ETL significa extrair, transformar e carregar dados.

Com apoio de automação, validei os 30 arquivos CSV do projeto. Eles abrangem seis países e cinco semanas de outubro de 2026. Cada arquivo tem 200 posições, mas a regra do projeto seleciona as primeiras 50. Assim, o ETL trabalha com 1.500 posições e 400 músicas diferentes. Uma música pode aparecer em mais de um país ou semana.

Conferi a estrutura, as colunas obrigatórias, os identificadores das faixas, as posições, os streams e as duplicidades. Executei a transformação e a carga em um banco separado. Ao repetir a carga, a quantidade de registros permaneceu igual, o que verificou o funcionamento do upsert nesse cenário.

Também foi corrigida uma falha que acontecia quando nenhuma consulta de metadados funcionava. A validação inicial teve 63 testes aprovados. Depois, um teste adicional verificou o salvamento e a retomada da coleta diante de um limite de requisições.

Configurei as credenciais e iniciei a coleta real. Foram registradas respostas para 300 faixas e 296 artistas, mas a API impôs HTTP 429, que indica limite de requisições. Essas respostas não chegaram a formar uma carga completa persistida, porque o extrator inicial guardava os resultados em memória até o final.

Preparei o relatório, as evidências e um comando que salva cada faixa completa assim que ela chega. A validação dos CSVs e a carga dos rankings estão concluídas. A coleta completa da API e a conferência final de artistas, gêneros, álbuns, duração e lançamento permanecem pendentes da liberação do Spotify.

## Respostas curtas

**Por que só 400 músicas?** As 1.500 posições incluem repetições da mesma música entre países e semanas. A API consulta IDs únicos.

**Por que Premium não resolveu?** O acesso Premium não elimina os limites separados de requisições da API. A autenticação funcionou, mas o servidor recusou novas consultas com HTTP 429.

**Como são obtidos os gêneros?** A consulta de artistas fornece os gêneros associados. A transformação reúne os gêneros sem repetição. Uma lista vazia não significa necessariamente falha.

**O que você consegue comprovar agora?** Estrutura e volume dos CSVs, execução das transformações e carga dos rankings, ausência de duplicação ao repetir a carga, testes e registros de consultas reais anteriores ao limite.

**O que ainda falta?** Persistir a coleta autenticada completa e validar a cobertura e as divergências dos metadados. Não devo apresentar a coleta parcial como concluída.

## O que mostrar na tela

1. O relatório `docs/validacao_spotify_andreza.md` no seu fork.
2. A correção em `src/etl1_spotify.py`.
3. Os testes `test_etl1_sem_metadados.py` e `test_validacao_spotify_checkpoint.py`.
4. O inventário `auditoria_etl1.json` e o registro `spotify_coleta_parcial.json`.
