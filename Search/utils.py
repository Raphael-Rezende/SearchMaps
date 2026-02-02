import sqlite3
import pandas as pd
from tabulate import tabulate

import os
from pathlib import Path



def formatar_dados(dados, colunas):
    """
    Formata os dados removendo espaços vazios e símbolos indesejados.
    :param dados: Lista de dados extraídos do banco.
    :param colunas: Lista das colunas escolhidas para exibição.
    :return: Dados formatados.
    """
    dados_formatados = []
    for linha in dados:
        nova_linha = []
        for dado in linha:
            if isinstance(dado, str):
                # Remove símbolos e espaços desnecessários
                dado = dado.replace("\n", " ").strip()
            nova_linha.append(dado)
        dados_formatados.append(nova_linha)
    return dados_formatados


def selecionar_colunas(df, max_colunas=5):
    """Permite ao usuário selecionar colunas para exibição."""
    print("\n=== Escolha as colunas para exibição ===")
    colunas_disponiveis = list(df.columns)

    # Exibe as opções numeradas
    for i, coluna in enumerate(colunas_disponiveis, start=1):
        print(f"{i}. {coluna}")

    # Solicita ao usuário que selecione as colunas
    selecionadas = []
    while len(selecionadas) < max_colunas:
        try:
            escolha = int(input(f"\nEscolha o número da coluna (ou 0 para finalizar): "))
            if escolha == 0:
                break
            if escolha < 1 or escolha > len(colunas_disponiveis):
                print("Opção inválida. Tente novamente.")
                continue

            coluna_escolhida = colunas_disponiveis[escolha - 1]
            if coluna_escolhida in selecionadas:
                print("Coluna já selecionada. Tente outra.")
            else:
                selecionadas.append(coluna_escolhida)
                print(f"Coluna '{coluna_escolhida}' adicionada.")
        except ValueError:
            print("Entrada inválida. Digite um número.")

    if not selecionadas:
        print("\nNenhuma coluna selecionada. Exibindo todas as colunas.")
        selecionadas = colunas_disponiveis[:max_colunas]

    return selecionadas


def exportar_para_excel():
    """
    Exporta os dados do banco SQLite para um arquivo Excel com formatação.
    """
    # Conexão com o banco
    conexao = sqlite3.connect("estabelecimentos.db")
    cursor = conexao.cursor()

    # Consulta os dados do banco
    cursor.execute("SELECT * FROM estabelecimentos")
    dados = cursor.fetchall()
    colunas = ["ID","Cidade", "Tipo_Estabelecimento", "Nome", "Endereco", "Entrega", "Telefone", "Cardapio", "Website"]

    if not dados:
        print("\nNenhum dado encontrado no banco de dados.")
        return

    # Cria DataFrame com os dados
    df = pd.DataFrame(dados, columns=colunas)

    
    # Define o caminho para salvar o arquivo
    pasta_destino = obter_pasta_documentos()
    nome_arquivo = os.path.join(pasta_destino, "estabelecimentos_formatados.xlsx")
    with pd.ExcelWriter(nome_arquivo, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Estabelecimentos")
        worksheet = writer.sheets["Estabelecimentos"]

        # Formatações de célula
        for idx, col in enumerate(df.columns):
            largura = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(idx, idx, largura)
        worksheet.set_column("C:C", 50)  # Aumenta a largura da coluna "Endereco"

    print(f"\nArquivo Excel exportado com sucesso: {nome_arquivo}")
    conexao.close()

def exportar_para_csv():
    """
    Exporta os dados do banco SQLite para um arquivo CSV.
    """
    # Conexão com o banco
    conexao = sqlite3.connect("estabelecimentos.db")
    cursor = conexao.cursor()

    # Consulta os dados do banco
    cursor.execute("SELECT * FROM estabelecimentos")
    dados = cursor.fetchall()
    colunas = ["ID","Cidade", "Tipo_Estabelecimento","Nome", "Endereco", "Entrega", "Telefone", "Cardapio", "Website"]

    if not dados:
        print("\nNenhum dado encontrado no banco de dados.")
        return

    # Cria DataFrame com os dados
    df = pd.DataFrame(dados, columns=colunas)


    # Define o caminho para salvar o arquivo
    pasta_destino = obter_pasta_documentos()
    nome_arquivo = os.path.join(pasta_destino, "estabelecimentos.csv")
    
    # Exporta para CSV
    df.to_csv(nome_arquivo, index=False, sep=";", encoding="utf-8")
    print(f"\nArquivo CSV exportado com sucesso: {nome_arquivo}")

    conexao.close()


def obter_pasta_documentos():
    """
    Obtém o caminho para a pasta Documentos do usuário e cria a subpasta 'Data Maps' se necessário.
    Retorna o caminho completo para a pasta 'Data Maps'.
    """
    # Identifica a pasta Documentos
    documentos = Path.home() / "Documents"

    # Caminho para a subpasta 'Data Maps'
    data_maps_pasta = documentos / "Data Maps"

    # Cria a pasta, se não existir
    data_maps_pasta.mkdir(parents=True, exist_ok=True)

    return data_maps_pasta


def exportar_lista_para_excel(dados, destino, colunas=None):
    """
    Exporta uma lista de dicionÃ¡rios para um arquivo Excel em um caminho especÃ­fico.
    :param dados: Lista de dicionÃ¡rios.
    :param destino: Caminho do arquivo .xlsx.
    :param colunas: Lista opcional de colunas em ordem preferida.
    """
    if not dados:
        raise ValueError("Nenhum dado para exportar.")

    df = pd.DataFrame(dados)
    if colunas:
        colunas_existentes = [col for col in colunas if col in df.columns]
        if colunas_existentes:
            df = df[colunas_existentes]

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(destino, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Estabelecimentos")
        worksheet = writer.sheets["Estabelecimentos"]

        for idx, col in enumerate(df.columns):
            largura = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(idx, idx, largura)


def exportar_lista_para_csv(dados, destino, colunas=None):
    """
    Exporta uma lista de dicionÃ¡rios para um arquivo CSV em um caminho especÃ­fico.
    :param dados: Lista de dicionÃ¡rios.
    :param destino: Caminho do arquivo .csv.
    :param colunas: Lista opcional de colunas em ordem preferida.
    """
    if not dados:
        raise ValueError("Nenhum dado para exportar.")

    df = pd.DataFrame(dados)
    if colunas:
        colunas_existentes = [col for col in colunas if col in df.columns]
        if colunas_existentes:
            df = df[colunas_existentes]

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False, sep=";", encoding="utf-8")
