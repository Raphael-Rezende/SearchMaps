from searcher import search
from db import listar_dados, visualizar_dados, filtrar_dados
from utils import exportar_para_excel, exportar_para_csv

#Para fazer requisições
import requests
import os

# Função para verificar a conexão com a internet
def verificar_conexao():
    print("Verificando conexão com a internet...")
    try:
        requests.get("https://www.google.com", timeout=5)
        print("Conexão com a internet verificada com sucesso!\n")
    except requests.ConnectionError:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("Erro: Sem conexão com a internet. Verifique sua conexão e tente novamente. Ou Digite 0 para voltar ao menu anterior")
        back = input("")
        if back == "1":
            show_menu()

def show_menu():
    while True:
        print("\n=== Menu Principal ===")
        print("1. Buscar Estabelecimentos")
        print("2. Mostrar Dados Recolhidos")
        print("3. Filtrar dado específico ou por coluna")
        print("4. Exportar para Excel")
        print("5. Exportar arquivo CSV")
        print("0. Sair")
        
        choice = input("Escolha uma opção (0-3): ")
        
        if choice == '1':
            # Verifica a conexão antes de solicitar as entradas do usuário
            verificar_conexao()
            search()
        elif choice == '2':
            visualizar_dados()
        elif choice == '3':
            filtrar_dados()
        elif choice == "4":
            exportar_para_excel()
        elif choice == "5":
            exportar_para_csv()
        
        elif choice == '0':
            print("\nSaindo do programa... Obrigado por usar!")
            exit()

        else:
            print("Opção inválida! Tente novamente.")

if __name__ == "__main__":
    show_menu()
