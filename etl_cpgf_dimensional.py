#!/usr/bin/env python3
"""
ETL dimensional para dados do Portal da Transparencia - CPGF.

Entrada:
    Um diretorio contendo arquivos CSV mensais do CPGF, por exemplo:
        202101_CPGF.csv
        202102_CPGF.csv
        ...
        202512_CPGF.csv

Saida:
    Arquivos CSV dimensionais:
        dm_orgao.csv
        dm_portador.csv
        dm_favorecido.csv
        dm_tp_transacao.csv
        dm_tempo.csv
        ft_transacao_cpgf.csv

Uso:
    python etl_cpgf_dimensional.py
    python etl_cpgf_dimensional.py --input-dir ./dados_cpgf --output-dir ./saida_dw

Observacao:
    A dimensao dm_tempo e derivada de DATA TRANSACAO.
    Registros sem DATA TRANSACAO, como transacoes sigilosas, recebem sk_tempo = -1.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BASE_DIR / "data"
DEFAULT_OUTPUT_DIR = BASE_DIR / "saida_dw"


COLUNAS_OBRIGATORIAS = [
    "CÓDIGO ÓRGÃO SUPERIOR",
    "NOME ÓRGÃO SUPERIOR",
    "CÓDIGO ÓRGÃO",
    "NOME ÓRGÃO",
    "CÓDIGO UNIDADE GESTORA",
    "NOME UNIDADE GESTORA",
    "CPF PORTADOR",
    "NOME PORTADOR",
    "CNPJ OU CPF FAVORECIDO",
    "NOME FAVORECIDO",
    "TRANSAÇÃO",
    "DATA TRANSAÇÃO",
    "VALOR TRANSAÇÃO",
]


MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def limpar_texto(valor: object) -> str | None:
    """Remove espacos extras e converte vazio/NaN para None."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto == "" or texto.lower() in {"nan", "none", "null"}:
        return None
    return texto


def normalizar_colunas_texto(df: pd.DataFrame, colunas: Iterable[str]) -> pd.DataFrame:
    """Aplica limpeza simples de texto nas colunas informadas."""
    for coluna in colunas:
        df[coluna] = df[coluna].map(limpar_texto)
    return df


def converter_valor_brasileiro(serie: pd.Series) -> pd.Series:
    """Converte valores no formato brasileiro para numero decimal.

    Exemplos:
        '19,43'     -> 19.43
        '1.234,56'  -> 1234.56
    """
    return pd.to_numeric(
        serie.astype(str)
        .str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )


def gerar_sk_incremental(df_dim: pd.DataFrame, nome_sk: str) -> pd.DataFrame:
    """Insere uma chave substituta incremental iniciando em 1."""
    df_dim = df_dim.reset_index(drop=True).copy()
    df_dim.insert(0, nome_sk, range(1, len(df_dim) + 1))
    return df_dim


def classificar_tp_doc_favorecido(documento: object) -> str:
    """Classifica CPF/CNPJ ou codigos especiais do favorecido.

    Codigos especiais encontrados no CPGF:
        -1  -> N/I  : nao informado
        -2  -> N/A  : nao se aplica
        -11 -> SIG  : sigiloso
    """
    doc = limpar_texto(documento)
    if doc is None:
        return "N/I"
    if doc == "-11":
        return "SIG"
    if doc == "-1":
        return "N/I"
    if doc == "-2":
        return "N/A"

    apenas_digitos = re.sub(r"\D", "", doc)
    if len(apenas_digitos) == 14:
        return "CNPJ"
    if len(apenas_digitos) == 11:
        return "CPF"
    return "N/I"


def classificar_gp_transacao(descricao: object) -> str:
    """Agrupa a descricao original da transacao em Compra, Saque ou Sigiloso."""
    texto = limpar_texto(descricao)
    if texto is None:
        return "Nao informado"

    texto_upper = texto.upper()
    if "SIGILO" in texto_upper:
        return "Sigiloso"
    if "COMPRA" in texto_upper:
        return "Compra"
    if "SAQUE" in texto_upper:
        return "Saque"
    return "Outros"


def truncar_texto(serie: pd.Series, tamanho: int) -> pd.Series:
    """Trunca texto para respeitar tamanhos definidos no modelo fisico."""
    return serie.map(lambda x: x[:tamanho] if isinstance(x, str) else x)


def ler_arquivos_cpgf(input_dir: Path, pattern: str, encoding: str) -> pd.DataFrame:
    arquivos = sorted(input_dir.glob(pattern))
    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum arquivo encontrado em {input_dir} com o padrao {pattern!r}."
        )

    frames = []
    for arquivo in arquivos:
        df = pd.read_csv(
            arquivo,
            sep=";",
            encoding=encoding,
            dtype=str,
            quotechar='"',
        )
        faltantes = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns]
        if faltantes:
            raise ValueError(
                f"Arquivo {arquivo.name} nao possui as colunas obrigatorias: {faltantes}"
            )
        frames.append(df[COLUNAS_OBRIGATORIAS].copy())

    return pd.concat(frames, ignore_index=True)


def preparar_staging(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas, limpa textos e cria campos derivados para as dimensoes."""
    df = df.rename(
        columns={
            "CÓDIGO ÓRGÃO SUPERIOR": "cd_orgao_superior",
            "NOME ÓRGÃO SUPERIOR": "nm_orgao_superior",
            "CÓDIGO ÓRGÃO": "cd_orgao",
            "NOME ÓRGÃO": "nm_orgao",
            "CÓDIGO UNIDADE GESTORA": "cd_unidade_gestora",
            "NOME UNIDADE GESTORA": "nm_unidade_gestora",
            "CPF PORTADOR": "cpf_portador",
            "NOME PORTADOR": "nm_portador",
            "CNPJ OU CPF FAVORECIDO": "doc_favorecido",
            "NOME FAVORECIDO": "nm_favorecido",
            "TRANSAÇÃO": "descr_transacao",
            "DATA TRANSAÇÃO": "data_transacao",
            "VALOR TRANSAÇÃO": "valor_transacao",
        }
    )

    colunas_texto = [
        "cd_orgao_superior",
        "nm_orgao_superior",
        "cd_orgao",
        "nm_orgao",
        "cd_unidade_gestora",
        "nm_unidade_gestora",
        "cpf_portador",
        "nm_portador",
        "doc_favorecido",
        "nm_favorecido",
        "descr_transacao",
        "data_transacao",
    ]
    df = normalizar_colunas_texto(df, colunas_texto)

    # Ajustes para nomes curtos definidos no modelo fisico da atividade.
    df["nm_portador"] = truncar_texto(df["nm_portador"], 45)
    df["nm_favorecido"] = truncar_texto(df["nm_favorecido"], 45)

    df["valor_transacao"] = converter_valor_brasileiro(df["valor_transacao"])

    df["dt_transacao"] = pd.to_datetime(
        df["data_transacao"],
        format="%d/%m/%Y",
        errors="coerce",
    )
    df["fl_data_invalida"] = df["data_transacao"].notna() & df["dt_transacao"].isna()

    data_valida = df["dt_transacao"].notna()
    df["dia"] = pd.NA
    df["mes"] = pd.NA
    df["ano"] = pd.NA
    df.loc[data_valida, "dia"] = df.loc[data_valida, "dt_transacao"].dt.day.astype(int)
    df.loc[data_valida, "mes"] = df.loc[data_valida, "dt_transacao"].dt.month.astype(int)
    df.loc[data_valida, "ano"] = df.loc[data_valida, "dt_transacao"].dt.year.astype(int)

    df["sk_tempo"] = -1
    df.loc[data_valida, "sk_tempo"] = df.loc[data_valida, "dt_transacao"].dt.strftime("%Y%m%d").astype(int)

    df["tp_doc_favorecido"] = df["doc_favorecido"].map(classificar_tp_doc_favorecido)
    df["fl_sigiloso_favorecido"] = (
        df["doc_favorecido"].eq("-11")
        | df["nm_favorecido"].fillna("").str.upper().eq("SIGILOSO")
    )

    df["fl_sigiloso_portador"] = (
        df["cpf_portador"].isna()
        & df["nm_portador"].fillna("").str.upper().eq("SIGILOSO")
    )

    df["gp_transacao"] = df["descr_transacao"].map(classificar_gp_transacao)
    df.loc[~data_valida, "gp_transacao"] = "Sigiloso"

    return df


def construir_dimensoes_e_fato(stg: pd.DataFrame) -> dict[str, pd.DataFrame]:
    # dm_orgao
    cols_orgao = [
        "cd_orgao_superior",
        "nm_orgao_superior",
        "cd_orgao",
        "nm_orgao",
        "cd_unidade_gestora",
        "nm_unidade_gestora",
    ]
    dm_orgao = stg[cols_orgao].drop_duplicates().sort_values(cols_orgao, na_position="last")
    dm_orgao = gerar_sk_incremental(dm_orgao, "sk_orgao")

    # dm_portador
    cols_portador = ["cpf_portador", "nm_portador", "fl_sigiloso_portador"]
    dm_portador = (
        stg[cols_portador]
        .drop_duplicates()
        .rename(columns={"fl_sigiloso_portador": "fl_sigiloso"})
        .sort_values(["fl_sigiloso", "nm_portador", "cpf_portador"], na_position="last")
    )
    dm_portador = gerar_sk_incremental(dm_portador, "sk_portador")

    # dm_favorecido
    cols_favorecido_stg = [
        "doc_favorecido",
        "tp_doc_favorecido",
        "nm_favorecido",
        "fl_sigiloso_favorecido",
    ]
    dm_favorecido = (
        stg[cols_favorecido_stg]
        .drop_duplicates()
        .rename(columns={"fl_sigiloso_favorecido": "fl_sigiloso"})
        .sort_values(["fl_sigiloso", "tp_doc_favorecido", "nm_favorecido", "doc_favorecido"], na_position="last")
    )
    dm_favorecido = gerar_sk_incremental(dm_favorecido, "sk_favorecido")

    # dm_tp_transacao
    cols_tp_transacao = ["descr_transacao", "gp_transacao"]
    dm_tp_transacao = (
        stg[cols_tp_transacao]
        .drop_duplicates()
        .sort_values(["gp_transacao", "descr_transacao"], na_position="last")
    )
    dm_tp_transacao = gerar_sk_incremental(dm_tp_transacao, "sk_tp_transacao")

    # dm_tempo
    dm_tempo = (
        stg.loc[stg["sk_tempo"].ne(-1), ["sk_tempo", "dia", "mes", "ano"]]
        .drop_duplicates()
        .sort_values("sk_tempo")
    )
    dm_tempo["dia"] = dm_tempo["dia"].astype(int)
    dm_tempo["mes"] = dm_tempo["mes"].astype(int)
    dm_tempo["ano"] = dm_tempo["ano"].astype(int)

    # Membro especial para datas ausentes/sigilosas.
    dm_tempo = pd.concat(
        [
            pd.DataFrame([{"sk_tempo": -1, "dia": pd.NA, "mes": pd.NA, "ano": pd.NA}]),
            dm_tempo,
        ],
        ignore_index=True,
    )

    # Montagem da fato atraves das chaves das dimensoes.
    fato = stg.copy()
    fato = fato.merge(dm_orgao, on=cols_orgao, how="left")

    fato = fato.merge(
        dm_portador.rename(columns={"fl_sigiloso": "fl_sigiloso_portador"}),
        on=["cpf_portador", "nm_portador", "fl_sigiloso_portador"],
        how="left",
    )

    fato = fato.merge(
        dm_favorecido.rename(columns={"fl_sigiloso": "fl_sigiloso_favorecido"}),
        on=["doc_favorecido", "tp_doc_favorecido", "nm_favorecido", "fl_sigiloso_favorecido"],
        how="left",
    )

    fato = fato.merge(dm_tp_transacao, on=cols_tp_transacao, how="left")

    ft_transacao_cpgf = pd.DataFrame(
        {
            "sk_transacao_cpgf": range(1, len(fato) + 1),
            "sk_orgao": fato["sk_orgao"].astype(int),
            "sk_portador": fato["sk_portador"].astype(int),
            "sk_favorecido": fato["sk_favorecido"].astype(int),
            "sk_tp_transacao": fato["sk_tp_transacao"].astype(int),
            "sk_tempo": fato["sk_tempo"].astype(int),
            "valor_transacao": fato["valor_transacao"].round(2),
            "quantidade_transacao": 1,
        }
    )

    return {
        "stg_cpgf": stg,
        "dm_orgao": dm_orgao,
        "dm_portador": dm_portador,
        "dm_favorecido": dm_favorecido,
        "dm_tp_transacao": dm_tp_transacao,
        "dm_tempo": dm_tempo,
        "ft_transacao_cpgf": ft_transacao_cpgf,
    }


def salvar_tabelas(tabelas: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for nome, df in tabelas.items():
        if nome == "stg_cpgf":
            continue
        caminho = output_dir / f"{nome}.csv"
        df.to_csv(caminho, sep=";", index=False, encoding="utf-8")


def imprimir_resumo(tabelas: dict[str, pd.DataFrame]) -> None:
    fato = tabelas["ft_transacao_cpgf"]
    staging = tabelas["stg_cpgf"]
    print("ETL concluido com sucesso.")
    print("Resumo das tabelas geradas:")
    for nome, df in tabelas.items():
        if nome == "stg_cpgf":
            continue
        print(f"- {nome}: {len(df):,} linhas".replace(",", "."))
    print(
        "Valor total da fato: "
        + f"{fato['valor_transacao'].sum(min_count=1):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    print(f"Transacoes sem data/sk_tempo = -1: {(fato['sk_tempo'] == -1).sum():,}".replace(",", "."))
    print("Resumo de qualidade da carga:")
    print(f"- Linhas lidas: {len(staging):,}".replace(",", "."))
    print(f"- Datas invalidas: {staging['fl_data_invalida'].sum():,}".replace(",", "."))
    print(f"- Favorecidos sigilosos: {staging['fl_sigiloso_favorecido'].sum():,}".replace(",", "."))
    print(f"- Valores nulos/invalidos: {staging['valor_transacao'].isna().sum():,}".replace(",", "."))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETL dimensional para arquivos CSV do CPGF."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Diretorio com os arquivos CSV do CPGF. Padrao: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Diretorio onde os arquivos dimensionais serao salvos. Padrao: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--pattern",
        default="*_CPGF.csv",
        help="Padrao dos arquivos de entrada. Padrao: *_CPGF.csv",
    )
    parser.add_argument(
        "--encoding",
        default="latin1",
        help="Encoding dos CSVs de entrada. Padrao: latin1",
    )
    args = parser.parse_args()

    bruto = ler_arquivos_cpgf(args.input_dir, args.pattern, args.encoding)
    staging = preparar_staging(bruto)
    tabelas = construir_dimensoes_e_fato(staging)
    salvar_tabelas(tabelas, args.output_dir)
    imprimir_resumo(tabelas)


if __name__ == "__main__":
    main()
