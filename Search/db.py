import sqlite3

from utils import formatar_dados

from tabulate import tabulate

def criar_banco():
    """Cria o banco de dados e a tabela se não existir."""
    conexao = sqlite3.connect("estabelecimentos.db")
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estabelecimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cidade TEXT NOT NULL,
            tipo_estabelecimento TEXT NOT NULL,
            nome TEXT NOT NULL,
            endereco TEXT,
            entrega TEXT,
            telefone TEXT,
            cardapio TEXT,
            website TEXT,
            UNIQUE(cidade, nome, endereco)  -- Evita duplicatas
        );
    """)

    conexao.commit()
    conexao.close()
    print("Banco de dados criado ou já existente.")


def salvar_dados_no_banco(dados):
    """
    Salva os dados no banco SQLite, verificando duplicatas.
    :param dados: Lista de listas com os dados (cidade, nome, endereco, entrega, telefone, cardapio, website)
    """
    criar_banco()  # Garante que o banco e a tabela existam
    conexao = sqlite3.connect("estabelecimentos.db")
    cursor = conexao.cursor()

    registros_salvos = 0
    for registro in dados:
        try:
            cursor.execute("""
                INSERT INTO estabelecimentos (cidade, tipo_estabelecimento, nome, endereco, entrega, telefone, cardapio, website)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, registro)
            registros_salvos += 1
        except sqlite3.IntegrityError:
            # Ignorar duplicatas
            print(f"Registro duplicado ignorado: {registro[1]} em {registro[0]}")

    conexao.commit()
    conexao.close()

    print(f"{registros_salvos} novos registros salvos com sucesso.")


def listar_dados():
    """Exibe os dados do banco de dados no terminal."""
    conexao = sqlite3.connect("estabelecimentos.db")
    cursor = conexao.cursor()

    cursor.execute("SELECT cidade, nome, endereco, entrega, telefone, cardapio, website FROM estabelecimentos")
    dados = cursor.fetchall()

    if dados:
        print("\n=== Dados no Banco de Dados ===")
        for registro in dados:
            print(f"Cidade: {registro[0]}, Nome: {registro[1]}, Endereço: {registro[2]}, "
                  f"Entrega: {registro[3]}, Telefone: {registro[4]}, Cardápio: {registro[5]}, Website: {registro[6]}")
    else:
        print("\nO banco de dados está vazio.")

    conexao.close()
    
    
def visualizar_dados():
    """
    Exibe os dados do banco SQLite com a possibilidade de escolher até 4 colunas.
    """
    # Conexão com o banco de dados
    conexao = sqlite3.connect("estabelecimentos.db")
    cursor = conexao.cursor()

    # Todas as colunas disponíveis
    todas_colunas = ["cidade", "nome", "endereco", "entrega", "telefone", "cardapio", "website"]

    # Exibe as opções de colunas e solicita ao usuário quais ele quer visualizar
    print("\n=== Colunas Disponíveis ===")
    for i, coluna in enumerate(todas_colunas, start=1):
        print(f"{i}. {coluna.capitalize()}")

    try:
        escolhas = input("\nEscolha até 4 colunas separadas por vírgula (ex.: 1,3,5): ").split(",")
        escolhas = [int(e.strip()) for e in escolhas if e.strip().isdigit()]

        if not (1 <= len(escolhas) <= 4):
            print("Você deve escolher entre 1 e 4 colunas. Tente novamente.")
            return

        colunas_escolhidas = [todas_colunas[i - 1] for i in escolhas]

    except (ValueError, IndexError):
        print("Entrada inválida. Tente novamente.")
        return

    # Monta a consulta SQL com as colunas escolhidas
    colunas_sql = ", ".join(colunas_escolhidas)
    cursor.execute(f"SELECT {colunas_sql} FROM estabelecimentos")
    dados = cursor.fetchall()

    if dados:
        # Formata os dados e exibe no terminal
        dados_formatados = formatar_dados(dados, colunas_escolhidas)
        print("\n=== Dados Selecionados ===")
        print(tabulate(dados_formatados, headers=[col.capitalize() for col in colunas_escolhidas], tablefmt="grid"))
    else:
        print("\nO banco de dados está vazio.")

    conexao.close()
    
def filtrar_dados():
    """
    Permite que o usuário filtre dados no banco de dados com base em um termo fornecido.
    O filtro é aplicado a todas as colunas.
    """
    conexao = sqlite3.connect("estabelecimentos.db")
    cursor = conexao.cursor()

    # Solicita ao usuário o termo de busca
    termo = input("Digite o termo para filtrar os dados: ").strip()

    if not termo:
        print("Nenhum termo fornecido. Voltando ao menu...")
        return

    # Consulta para buscar o termo em todas as colunas
    cursor.execute("""
        SELECT * FROM estabelecimentos 
        WHERE Cidade LIKE ? 
           OR Nome LIKE ? 
           OR Endereco LIKE ? 
           OR Entrega LIKE ? 
           OR Telefone LIKE ? 
           OR Cardapio LIKE ? 
           OR Website LIKE ?
    """, [f"%{termo}%"] * 7)
    resultados = cursor.fetchall()

    if resultados:
        # Exibe os resultados formatados
        colunas = ["Cidade", "Nome", "Endereco", "Entrega", "Telefone", "Cardapio", "Website"]
        print("\nResultados encontrados:")
        print(tabulate(resultados, headers=colunas, tablefmt="grid"))
    else:
        print("\nNenhum dado encontrado para o termo fornecido.")

    conexao.close()
