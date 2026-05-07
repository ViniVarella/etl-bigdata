# ETL CPGF Dimensional

Projeto de ETL em Python para transformar arquivos CSV mensais do CPGF (Cartao de Pagamento do Governo Federal) em um modelo dimensional simples para analise e BI.

## Objetivo

Consolidar os arquivos brutos do Portal da Transparencia e gerar:

- dimensoes para orgao, portador, favorecido, tipo de transacao e tempo
- uma tabela fato com valor e quantidade de transacoes

## Estrutura esperada dos arquivos de entrada

Os arquivos CSV devem estar em uma pasta, com nomes no padrao:

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

## Requisitos

- Python 3.10+
- Dependencias em [requirements.txt](C:/Users/vinic/PycharmProjects/etl-bigdata/requirements.txt)

Instalacao:

```bash
pip install -r requirements.txt
```

## Como executar

Execucao direta com os diretorios padrao:

```bash
python etl_cpgf_dimensional.py
```

Diretorios padrao no codigo:

- entrada: `./data`
- saida: `./saida_dw`

Exemplo com caminhos explicitos:

```bash
python etl_cpgf_dimensional.py --input-dir ./data --output-dir ./saida_dw
```

Argumentos disponiveis:

- `--input-dir`: diretorio com os CSVs de entrada
- `--output-dir`: diretorio onde os arquivos de saida serao gravados
- `--pattern`: padrao de busca dos arquivos, padrao `*_CPGF.csv`
- `--encoding`: encoding dos arquivos de entrada, padrao `latin1`

Exemplo com argumentos explicitos:

```bash
python etl_cpgf_dimensional.py --input-dir ./data --output-dir ./saida_dw --pattern "*_CPGF.csv" --encoding latin1
```

## Saidas geradas

O ETL gera os seguintes arquivos CSV:

- `dm_orgao.csv`
- `dm_portador.csv`
- `dm_favorecido.csv`
- `dm_tp_transacao.csv`
- `dm_tempo.csv`
- `ft_transacao.csv`

## Regras principais do ETL

- consolida todos os arquivos CSV encontrados no diretorio de entrada
- limpa campos textuais e padroniza valores vazios
- converte `VALOR TRANSAÇÃO` do formato brasileiro para numero decimal
- converte `DATA TRANSAÇÃO` para data
- gera `sk_tempo` no formato `AAAAMMDD`
- usa `sk_tempo = -1` para registros sem data valida
- classifica documento do favorecido como `CPF`, `CNPJ`, `SIG`, `N/I` ou `N/A`
- classifica a transacao em `Compra`, `Saque`, `Sigiloso` ou `Outros`
- marca portador como sigiloso apenas quando:
  - `CPF PORTADOR` estiver vazio
  - `NOME PORTADOR` for `SIGILOSO`

## Resumo de qualidade da carga

Ao final da execucao, o script informa:

- quantidade de linhas lidas
- quantidade de datas invalidas
- quantidade de favorecidos sigilosos
- quantidade de valores nulos ou invalidos
- total de linhas geradas em cada dimensao e na fato
- soma total de `valor_transacao`

## Modelo dimensional

Dimensoes:

- `dm_orgao`
- `dm_portador`
- `dm_favorecido`
- `dm_tp_transacao`
- `dm_tempo`

Fato:

- `ft_transacao`

Medidas principais:

- `vl_transacao`

## Uso no BI

Com esse modelo, e possivel montar analises como:

- gasto total por orgao
- gasto por mes e ano
- gasto por tipo de transacao
- top favorecidos por valor
- quantidade de transacoes por portador
- transacoes com dados sigilosos

## Observacoes

- a dimensao tempo e derivada de `DATA TRANSAÇÃO`, nao do nome do arquivo
- os arquivos brutos podem conter colunas adicionais, mas o ETL usa apenas as colunas necessarias para o modelo dimensional
- valores invalidos nao sao convertidos para `0`; permanecem nulos para evitar distorcao analitica
