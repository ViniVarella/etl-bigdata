# ETL CPGF Dimensional

Projeto em Python para transformar arquivos CSV mensais do CPGF (Cartao de Pagamento do Governo Federal), publicados no Portal da Transparencia, em um modelo dimensional simples para analise e BI.

## Visao geral

O ETL consolida todos os arquivos mensais da pasta `data`, padroniza os campos relevantes, aplica regras de limpeza e classificacao e gera um conjunto de tabelas em modelo estrela:

- `dm_orgao`
- `dm_portador`
- `dm_favorecido`
- `dm_tp_transacao`
- `dm_tempo`
- `ft_transacao`

Esse modelo foi pensado para responder perguntas como:

- quanto cada orgao gastou
- como os gastos evoluem no tempo
- quais sao os principais favorecidos
- qual o peso de compras, saques e transacoes sigilosas

## Objetivo da atividade

O objetivo deste projeto e:

1. extrair dados brutos do CPGF em CSV
2. transformar os dados em um modelo dimensional consistente
3. gerar uma base pronta para visualizacao em ferramenta de BI

## Fonte de dados

Os arquivos de entrada sao CSVs mensais com nomes no padrao:

```text
202101_CPGF.csv
202102_CPGF.csv
202103_CPGF.csv
...
```

Formato esperado dos CSVs:

- separador: `;`
- textos entre aspas duplas: `"`
- encoding padrao: `latin1`

Colunas utilizadas pelo ETL:

- `CÓDIGO ÓRGÃO SUPERIOR`
- `NOME ÓRGÃO SUPERIOR`
- `CÓDIGO ÓRGÃO`
- `NOME ÓRGÃO`
- `CÓDIGO UNIDADE GESTORA`
- `NOME UNIDADE GESTORA`
- `CPF PORTADOR`
- `NOME PORTADOR`
- `CNPJ OU CPF FAVORECIDO`
- `NOME FAVORECIDO`
- `TRANSAÇÃO`
- `DATA TRANSAÇÃO`
- `VALOR TRANSAÇÃO`

Observacao:

- o ETL usa a data real da transacao (`DATA TRANSAÇÃO`) para a dimensao tempo
- o nome do arquivo nao define a data da fato

## Requisitos

- Python 3.10+
- dependencias descritas em [requirements.txt](C:/Users/vinic/PycharmProjects/etl-bigdata/requirements.txt)

Instalacao:

```bash
pip install -r requirements.txt
```

## Como executar

Execucao direta com os diretorios padrao definidos no codigo:

```bash
python etl_cpgf_dimensional.py
```

Diretorios padrao:

- entrada: `./data`
- saida: `./saida_dw`

Tambem e possivel sobrescrever os caminhos:

```bash
python etl_cpgf_dimensional.py --input-dir ./data --output-dir ./saida_dw
```

Argumentos disponiveis:

- `--input-dir`: diretorio com os CSVs de entrada
- `--output-dir`: diretorio onde os CSVs dimensionais serao gravados
- `--pattern`: padrao de busca dos arquivos, padrao `*_CPGF.csv`
- `--encoding`: encoding dos arquivos de entrada, padrao `latin1`

Exemplo com argumentos explicitos:

```bash
python etl_cpgf_dimensional.py --input-dir ./data --output-dir ./saida_dw --pattern "*_CPGF.csv" --encoding latin1
```

## Fluxo do ETL

O script executa as etapas abaixo:

1. localiza todos os arquivos `*_CPGF.csv` no diretorio de entrada
2. le cada arquivo com `pandas.read_csv`
3. valida se as colunas obrigatorias existem
4. concatena todos os arquivos em um unico conjunto bruto
5. renomeia as colunas para nomes tecnicos menores
6. limpa espacos extras e padroniza valores vazios
7. converte `VALOR TRANSAÇÃO` do formato brasileiro para decimal
8. converte `DATA TRANSAÇÃO` para data
9. deriva atributos da dimensao tempo (`dia`, `mes`, `ano`, `sk_tempo`)
10. classifica documento do favorecido e grupo da transacao
11. constroi as dimensoes removendo duplicidades
12. monta a fato com as chaves substitutas das dimensoes
13. grava os CSVs finais na pasta de saida
14. imprime um resumo da carga e indicadores de qualidade

## Regras de transformacao

### Limpeza de texto

- remove espacos em branco no inicio e no fim
- converte valores vazios, `nan`, `none` e `null` para nulo
- preserva caracteres que fazem parte do valor original, como apostrofos no nome do favorecido

### Valores monetarios

- `VALOR TRANSAÇÃO` e convertido do formato brasileiro para decimal
- exemplos:
  - `19,43` -> `19.43`
  - `1.234,56` -> `1234.56`
- valores invalidos nao sao convertidos para `0`; permanecem nulos

### Datas

- `DATA TRANSAÇÃO` e interpretada no formato `dd/mm/aaaa`
- quando a data e valida, o ETL gera:
  - `dia`
  - `mes`
  - `ano`
  - `sk_tempo` no formato `AAAAMMDD`
- quando a data esta ausente ou invalida:
  - `sk_tempo = -1`
  - a transacao e classificada como `Sigiloso`

### Favorecido

O ETL classifica o documento do favorecido em:

- `CPF`
- `CNPJ`
- `SIG` -> sigiloso
- `N/I` -> nao informado
- `N/A` -> nao se aplica

Codigos especiais tratados:

- `-11` -> `SIG`
- `-1` -> `N/I`
- `-2` -> `N/A`

### Portador

Um portador e marcado como sigiloso apenas quando:

- `CPF PORTADOR` estiver vazio
- e `NOME PORTADOR` for `SIGILOSO`

### Grupo da transacao

A descricao original da transacao e agrupada em:

- `Compra`
- `Saque`
- `Sigiloso`
- `Outros`

## Modelo dimensional

### dm_orgao

Representa a estrutura administrativa associada a transacao.

Colunas:

- `sk_orgao`
- `cd_orgao_superior`
- `nm_orgao_superior`
- `cd_orgao`
- `nm_orgao`
- `cd_unidade_gestora`
- `nm_unidade_gestora`

### dm_portador

Representa o portador do cartao.

Colunas:

- `sk_portador`
- `cpf_portador`
- `nm_portador`
- `fl_sigiloso`

### dm_favorecido

Representa quem recebeu o pagamento ou aparece associado ao gasto.

Colunas:

- `sk_favorecido`
- `doc_favorecido`
- `tp_doc_favorecido`
- `nm_favorecido`
- `fl_sigiloso`

### dm_tp_transacao

Representa a descricao original e o grupo analitico da transacao.

Colunas:

- `sk_tp_transacao`
- `descr_transacao`
- `gp_transacao`

### dm_tempo

Representa a data da transacao.

Colunas:

- `sk_tempo`
- `dia`
- `mes`
- `ano`

Regra especial:

- existe uma linha tecnica com `sk_tempo = -1` para transacoes sem data valida

### ft_transacao

Tabela fato do modelo.

Colunas:

- `sk_transacao`
- `sk_orgao`
- `sk_portador`
- `sk_favorecido`
- `sk_tp_transacao`
- `sk_tempo`
- `vl_transacao`

Medida principal:

- `vl_transacao`

## Limites fisicos das colunas textuais

Os limites abaixo seguem o diagrama atual do modelo:

- `dm_orgao.cd_orgao_superior`: `VARCHAR(20)`
- `dm_orgao.nm_orgao_superior`: `VARCHAR(100)`
- `dm_orgao.cd_orgao`: `VARCHAR(20)`
- `dm_orgao.nm_orgao`: `VARCHAR(100)`
- `dm_orgao.cd_unidade_gestora`: `VARCHAR(20)`
- `dm_orgao.nm_unidade_gestora`: `VARCHAR(100)`
- `dm_portador.cpf_portador`: `VARCHAR(20)`
- `dm_portador.nm_portador`: `VARCHAR(60)`
- `dm_favorecido.doc_favorecido`: `VARCHAR(20)`
- `dm_favorecido.tp_doc_favorecido`: `VARCHAR(4)`
- `dm_favorecido.nm_favorecido`: `VARCHAR(150)`
- `dm_tp_transacao.descr_transacao`: `VARCHAR(45)`
- `dm_tp_transacao.gp_transacao`: `VARCHAR(45)`

O ETL aplica truncamento somente quando necessario para respeitar esses limites.

## Arquivos gerados

Ao final da execucao, sao gerados:

- `dm_orgao.csv`
- `dm_portador.csv`
- `dm_favorecido.csv`
- `dm_tp_transacao.csv`
- `dm_tempo.csv`
- `ft_transacao.csv`

## Resumo de qualidade da carga

Ao final da execucao, o script informa:

- quantidade de linhas lidas
- quantidade de datas invalidas
- quantidade de favorecidos sigilosos
- quantidade de valores nulos ou invalidos
- total de linhas geradas em cada dimensao e na fato
- soma total de `vl_transacao`

Exemplo de pontos que esse resumo ajuda a validar:

- se houve erro de leitura dos arquivos
- se existem registros sem data valida
- se ha valores monetarios com problema de conversao
- se o volume final bate com a expectativa da atividade

## Uso no BI

Com esse modelo, e possivel montar analises como:

- gasto total por orgao
- gasto por mes e ano
- gasto por tipo de transacao
- top favorecidos por valor
- participacao de transacoes sigilosas
- distribuicao de gastos por portador

Sugestoes de indicadores:

- soma de `vl_transacao`
- quantidade de transacoes por contagem de linhas da fato
- ticket medio por orgao ou por tipo de transacao
- percentual de transacoes sigilosas

## Observacoes importantes

- os arquivos brutos podem conter colunas adicionais, mas o ETL usa apenas as colunas necessarias para o modelo dimensional
- nomes com apostrofos ou pontuacao estranha podem existir na base original e sao preservados quando fazem parte do valor publicado
- a dimensao tempo e derivada de `DATA TRANSAÇÃO`, nao do nome do arquivo
- `sk_tempo = -1` representa data desconhecida, ausente ou sigilosa
- a qualidade visual do BI depende da ferramenta, mas os CSVs gerados saem sem chaves nulas na fato
