import tkinter as tk
import tkinter.font as tkFont
from tkinter import messagebox, ttk, filedialog
import itertools
import time
import logging
import threading
import sys
import os

from multiprocessing import Process, Queue, Event
from queue import Empty

# Configurar paths do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
utils_path = os.path.join(BASE_DIR, 'utils')
config_path = os.path.join(BASE_DIR, 'config')

if utils_path not in sys.path:
    sys.path.append(utils_path)
if config_path not in sys.path:
    sys.path.append(config_path)

try:
    from utils.paths import setup_project_paths
    setup_project_paths()
    from config.config import APP_VERSION, APP_NAME
    from utils.logger import Logger
except ImportError as e:
    # Fallback para definições básicas
    from config.config import APP_VERSION, APP_NAME
    from utils.logger import Logger

# URL de login do sistema Canaimé (não mais usada diretamente aqui)
# URL_LOGIN_CANAIME = 'https://canaime.com.br/sgp2rr/login/login_principal.php'

logger = Logger.get_logger()

class LogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.tag_config('info', foreground='#add8e6') # Light blue
        self.text_widget.tag_config('warning', foreground='#ffa500') # Orange
        self.text_widget.tag_config('error', foreground='#ff4500') # Red-orange
        self.text_widget.tag_config('critical', foreground='#dc143c') # Crimson
        self.text_widget.tag_config('debug', foreground='#90ee90') # Light green

    def emit(self, record):
        try:
            msg = self.format(record)
            # Verificar se o widget ainda existe antes de tentar escrever
            if hasattr(self.text_widget, 'winfo_exists') and self.text_widget.winfo_exists():
                # Adiciona a mensagem com uma tag baseada no nível do log
                self.text_widget.insert(tk.END, msg + '\n', record.levelname.lower())
                self.text_widget.yview(tk.END) # Auto-scroll
        except Exception:
            # Se houver erro ao escrever no widget, apenas ignorar
            pass

class LoginApp:
    def __init__(self, root, headless, process_task_func):
        self.root = root
        self.login_successful = False
        self.frames = itertools.cycle(["◐", "◓", "◑", "◒"])
        self.animation_running = False
        self.headless = headless
        self.process_task_func = process_task_func # Function from main.py to run in separate process
        self.process_queue = Queue() # Queue for communication from child process (child -> UI)
        self.command_queue = Queue() # Queue for commands from UI to child process (UI -> child)
        self.process_stop_event = Event() # Event to signal child process to stop
        self.process_finalized = False  # Flag para evitar finalização duplicada
        self._login_error_window = None  # Referência para janela de erro de login
        self._validation_error_window = None  # Referência para janela de erro de validação

        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("400x600")
        self.root.resizable(False, False)
        self.root.configure(bg="#1E2C44")  # Cor de fundo azul escuro

        self.center_window()
        self.create_widgets()
        self.bind_events()

        # Add the custom handler to the logger
        # self.log_handler = LogHandler(self.log_text)
        # logger.addHandler(self.log_handler)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        # Main Frame
        main_frame = tk.Frame(self.root, bg="#1E2C44")
        main_frame.pack(pady=50, padx=40, fill="both", expand=True)

        # Logo Placeholder (you would replace this with an actual image)
        logo_label = tk.Label(
            main_frame,
            text="👮",  # Placeholder icon
            font=('Segoe UI', 60),
            fg="#FFD700", # Gold color
            bg="#1E2C44"
        )
        logo_label.pack(pady=(0, 20))

        # Title
        title_label = tk.Label(
            main_frame,
            text="LOGIN CANAIMÉ",
            font=('Segoe UI', 24, 'bold'),
            fg="#FFFFFF",  # White color
            bg="#1E2C44"
        )
        title_label.pack(pady=(0, 5))
        
        # Subtitle
        subtitle_label = tk.Label(
            main_frame,
            text=f"{APP_NAME} {APP_VERSION}",
            font=('Segoe UI', 9),
            fg="#FFFFFF",
            bg="#1E2C44",
            anchor="e"  # Align to right
        )
        subtitle_label.pack(fill="x", padx=5, pady=(0, 30))

        # Username Entry
        self.username_entry = tk.Entry(
            main_frame,
            font=('Segoe UI', 12),
            bg="#2B3C57",  # Darker blue for entry
            fg="#FFFFFF",
            insertbackground="#FFFFFF",  # White cursor
            relief="flat",
            highlightbackground="#2B3C57",
            highlightthickness=1,
            bd=0 # Remove border
        )
        self.username_entry.pack(pady=(0, 20), fill="x", padx=15)
        self.set_placeholder(self.username_entry, " Usuário")
        self.username_entry.bind("<FocusIn>", lambda e: self.on_entry_focus_in(self.username_entry, " Usuário"))
        self.username_entry.bind("<FocusOut>", lambda e: self.on_entry_focus_out(self.username_entry, " Usuário"))

        # Password Entry
        self.password_entry = tk.Entry(
            main_frame,
            font=('Segoe UI', 12),
            bg="#2B3C57",
            fg="#FFFFFF",
            show="*",
            insertbackground="#FFFFFF",
            relief="flat",
            highlightbackground="#2B3C57",
            highlightthickness=1,
            bd=0 # Remove border
        )
        self.password_entry.pack(pady=(0, 40), fill="x", padx=15)
        self.set_placeholder(self.password_entry, " Senha")
        self.password_entry.bind("<FocusIn>", lambda e: self.on_entry_focus_in(self.password_entry, " Senha", is_password=True))
        self.password_entry.bind("<FocusOut>", lambda e: self.on_entry_focus_out(self.password_entry, " Senha", is_password=True))

        # Login Button
        self.login_button = tk.Button(
            main_frame,
            text="Login",
            font=('Segoe UI', 14, 'bold'),
            bg="#1A73E8",  # Blue color as in image
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.iniciar_login,
            activebackground="#155CBF",
            pady=10
        )
        self.login_button.pack(pady=(0, 20), fill="x")
        
        # Status Frame para mostrar logs e status
        status_frame = tk.Frame(main_frame, bg="#2B3C57", bd=1, relief="solid")
        status_frame.pack(pady=10, fill="both", expand=True)
        
        # Status Text para mostrar logs
        self.status_text = tk.Text(
            status_frame,
            wrap='word',
            font=('Consolas', 9),
            bg='#2B3C57',
            fg='#FFFFFF',
            relief='flat',
            bd=0,
            insertbackground='#FFFFFF',
            height=6
        )
        self.status_text.pack(side='left', fill='both', expand=True)
        
        # Scrollbar para o Status Text
        status_scrollbar = tk.Scrollbar(status_frame, command=self.status_text.yview)
        status_scrollbar.pack(side='right', fill='y')
        self.status_text.config(yscrollcommand=status_scrollbar.set)
        
        # Configurar o handler de log para o status_text
        self.log_handler = LogHandler(self.status_text)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # Remover handlers existentes do mesmo tipo para evitar duplicação
        for handler in logger.handlers[:]:
            if isinstance(handler, LogHandler):
                logger.removeHandler(handler)
        
        logger.addHandler(self.log_handler)

    def bind_events(self):
        self.root.bind('<Return>', lambda event: self.iniciar_login()) # Bind Enter key to login

    def set_placeholder(self, entry, placeholder_text):
        entry.insert(0, placeholder_text)
        entry.config(fg='gray')

    def on_entry_focus_in(self, entry, placeholder_text, is_password=False):
        if entry.get() == placeholder_text:
            entry.delete(0, tk.END)
            entry.config(fg='white')
            if is_password:
                entry.config(show='*')
        entry.config(highlightbackground="#1A73E8") # Highlight on focus

    def on_entry_focus_out(self, entry, placeholder_text, is_password=False):
        if not entry.get():
            entry.insert(0, placeholder_text)
            entry.config(fg='gray')
            if is_password:
                entry.config(show='')
        entry.config(highlightbackground="#2B3C57") # Default color when not focused

    def iniciar_login(self):
        # Resetar flags para novo processo
        self.process_finalized = False
        if hasattr(self, '_finalization_countdown'):
            delattr(self, '_finalization_countdown')
        # Resetar referências de janelas de erro
        self._login_error_window = None
        self._validation_error_window = None
        # CRÍTICO: Resetar o process_stop_event para novo processo
        self.process_stop_event.clear()
            
        username = self.username_entry.get()
        password = self.password_entry.get()

        # Handle placeholder text
        if username == " Usuário":
            username = ""
        if password == " Senha":
            password = ""

        if not username or not password:
            self.add_status_message("ERRO: Por favor, insira o usuário e a senha.")
            return

        # Limpar o status text e mostrar mensagem de início
        self.status_text.config(state='normal')
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state='disabled')
        self.add_status_message("Iniciando processo de login...")

        self.login_button.config(state=tk.DISABLED)
        self.animation_running = True

        logger.info("Iniciando processo de login...")

        try:
            # Iniciar o processo em segundo plano
            p = Process(
                target=self.process_task_func,
                args=(
                    self.headless,
                    self.process_queue,
                    self.command_queue,
                    self.process_stop_event,
                    username,
                    password,
                ),
            )
            p.start()
            
            self.root.after(100, self.verificar_fila)
        except Exception as e:
            error_msg = f"Erro ao iniciar processo: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.add_status_message(f"ERRO: {error_msg}")
            self.login_button.config(state=tk.NORMAL)
            self.animation_running = False

    def animar_bolinha(self):
        # Função de animação removida do novo layout
        pass

    def verificar_fila(self):
        if not self.process_stop_event.is_set():
            try:
                message_type, *message_content = self.process_queue.get_nowait()
                
                # Log de debug para verificar mensagens recebidas
                logger.info(f"Recebida mensagem: {message_type} - {message_content}")
                
                if message_type == "log":
                    log_message = message_content[0]
                    logger.info(log_message) # Logs from child process
                    self.add_status_message(log_message)
                elif message_type == "success":
                    self.login_successful = True
                    # Resetar countdown pois processamos uma mensagem importante
                    if hasattr(self, '_finalization_countdown'):
                        delattr(self, '_finalization_countdown')
                    self.finalizar_processo("Sucesso", message_content[0])
                elif message_type == "exit_app":
                    # Encerrar completamente a aplicação
                    self.add_status_message(message_content[0])
                    self.root.after(500, self.encerrar_aplicativo)
                elif message_type == "error":
                    logger.info(f"Processando erro: {message_content[0]}")
                    logger.info(f"Traceback: {message_content[1] if len(message_content) > 1 else 'N/A'}")
                    # Resetar countdown pois processamos uma mensagem importante
                    if hasattr(self, '_finalization_countdown'):
                        delattr(self, '_finalization_countdown')
                    self.finalizar_processo("Erro", message_content[0], message_content[1] if len(message_content) > 1 else None)
                elif message_type == "validation_error":
                    logger.info(f"Processando erro de validação: {message_content[0]}")
                    logger.info(f"Presos não mapeados: {len(message_content[1]) if len(message_content) > 1 else 0}")
                    # Resetar countdown pois processamos uma mensagem importante
                    if hasattr(self, '_finalization_countdown'):
                        delattr(self, '_finalization_countdown')
                    # Exibir janela de erro de validação ANTES de marcar como finalizado
                    self.show_validation_error(message_content[0], message_content[1])
                    # Marcar como finalizado APÓS exibir a janela
                    self.process_finalized = True
                    # Definir stop_event APÓS processar a mensagem (similar ao erro de login)
                    self.process_stop_event.set()
                elif message_type == "status":
                    # Mensagem de status sem ser log
                    self.add_status_message(message_content[0])
                elif message_type == "choose_alas":
                    # Exibir janela para seleção de alas
                    alas = message_content[0] if message_content else []
                    self.show_ala_selection(alas)
                elif message_type == "ask_save_path":
                    # Perguntar onde salvar o PDF
                    suggested_name = message_content[0] if message_content else "cara_cracha.pdf"
                    path = self.ask_save_path(suggested_name)
                    self.command_queue.put(("save_path", path))
            except Empty:
                # Sem mensagens ainda, continuar verificando
                pass
            except Exception as e:
                error_msg = f"Erro ao processar mensagem da fila: {e}"
                logger.error(error_msg, exc_info=True)
                self.add_status_message(f"ERRO: {error_msg}")
            finally:
                self.root.after(100, self.verificar_fila)
        else:
            # Processo terminou, mas pode ter mensagens pendentes na fila
            # Aguardar um pouco mais para processar mensagens pendentes
            if not hasattr(self, '_finalization_countdown'):
                self._finalization_countdown = 5  # Tentar por 5 ciclos (500ms)
            
            if self._finalization_countdown > 0:
                self._finalization_countdown -= 1
                self.root.after(100, self.verificar_fila)
            else:
                # Após aguardar, finalizar se não houve mensagens importantes
                if not self.process_finalized:
                    logger.info("Processo terminou, finalizando UI")
                    self.finalizar_processo("", "") # Call to clean up UI
                else:
                    logger.info("Processo já foi finalizado por mensagem importante")

    def finalizar_processo(self, title, message, traceback_text=None):
        # Evitar finalização duplicada
        if self.process_finalized:
            logger.info("Processo já finalizado, ignorando chamada duplicada")
            return
            
        logger.info(f"Finalizando processo: {title} - {message}")
        self.login_button.config(state=tk.NORMAL)
        self.animation_running = False
        self.process_finalized = True

        if title == "Sucesso":
            self.add_status_message(f"SUCESSO: {message}")
            # O encerramento será tratado pelo sinal exit_app
        elif title == "Erro":
            self.add_status_message(f"❌ ERRO: {message}")
            logger.info(f"Detectado erro: {message}")
            
            # Verificar se é erro de login para exibir janela especial
            if "login" in message.lower() or "credenciais" in message.lower():
                logger.info("Exibindo janela de erro de login")
                self.add_status_message("🔐 Abrindo janela de erro de login...")
                self.show_login_error(message, traceback_text)
            else:
                # Para outros erros, mostrar no status
                if traceback_text:
                    self.add_status_message("📋 Detalhes do erro:")
                    self.add_status_message(traceback_text[:500] + "..." if len(traceback_text) > 500 else traceback_text)
        
        # Remove o handler de log ao finalizar
        if hasattr(self, 'log_handler') and self.log_handler in logger.handlers:
            logger.removeHandler(self.log_handler)

    def show_login_error(self, error_message, traceback_text=None):
        """Exibe erro de login de forma amigável"""
        # Verificar se já existe uma janela de erro aberta
        if hasattr(self, '_login_error_window') and self._login_error_window is not None and self._login_error_window.winfo_exists():
            logger.info("Janela de erro de login já existe, não criando nova")
            return
            
        logger.info(f"Exibindo janela de erro de login: {error_message}")
        
        # Criar janela de erro de login
        login_error_window = tk.Toplevel(self.root)
        self._login_error_window = login_error_window  # Guardar referência
        login_error_window.title("Erro de Login")
        login_error_window.geometry("700x600")
        login_error_window.attributes('-topmost', True)
        login_error_window.configure(bg='#1b2838')
        
        # Centralizar a janela na tela
        login_error_window.update_idletasks()
        width = login_error_window.winfo_width()
        height = login_error_window.winfo_height()
        x = (login_error_window.winfo_screenwidth() // 2) - (width // 2)
        y = (login_error_window.winfo_screenheight() // 2) - (height // 2)
        login_error_window.geometry(f'{width}x{height}+{x}+{y}')

        # Título
        title_label = tk.Label(
            login_error_window,
            text="❌ ERRO DE LOGIN",
            font=('Segoe UI', 16, 'bold'),
            bg='#1b2838',
            fg='#e74c3c'
        )
        title_label.pack(pady=15)

        # Ícone de erro
        error_icon = tk.Label(
            login_error_window,
            text="🔐",
            font=('Segoe UI', 48),
            bg='#1b2838',
            fg='#e74c3c'
        )
        error_icon.pack(pady=10)

        # Mensagem de erro
        msg_label = tk.Label(
            login_error_window,
            text="Falha na autenticação no sistema Canaimé",
            font=('Segoe UI', 12, 'bold'),
            bg='#1b2838',
            fg='#ffffff',
            wraplength=650
        )
        msg_label.pack(pady=10)

        # Detalhes do erro
        details_label = tk.Label(
            login_error_window,
            text=error_message,
            font=('Segoe UI', 10),
            bg='#1b2838',
            fg='#ff6b6b',
            wraplength=650
        )
        details_label.pack(pady=10)

        # Instruções
        instructions_label = tk.Label(
            login_error_window,
            text="Verifique:\n• Usuário e senha estão corretos\n• Conexão com a internet\n• Sistema Canaimé está acessível\n• Credenciais não expiraram",
            font=('Segoe UI', 10),
            bg='#1b2838',
            fg='#ffffff',
            justify='left',
            wraplength=650
        )
        instructions_label.pack(pady=15)

        # Botão para tentar novamente
        retry_button = tk.Button(
            login_error_window,
            text="🔄 Tentar Novamente",
            font=('Segoe UI', 12, 'bold'),
            bg='#3498db',
            fg='white',
            relief='flat',
            cursor='hand2',
            command=login_error_window.destroy,
            activebackground='#287bb8',
            pady=8,
            padx=20
        )
        retry_button.pack(pady=15)

        # Botão para fechar
        close_button = tk.Button(
            login_error_window,
            text="❌ Fechar",
            font=('Segoe UI', 12, 'bold'),
            bg='#e74c3c',
            fg='white',
            relief='flat',
            cursor='hand2',
            command=login_error_window.destroy,
            activebackground='#c0392b',
            pady=8,
            padx=20
        )
        close_button.pack(pady=10)

        login_error_window.grab_set()
        login_error_window.wait_window()

    def encerrar_aplicativo(self):
        """Encerra o aplicativo completamente após o sucesso"""
        # Remover o handler de log para evitar erros de Tkinter
        if hasattr(self, 'log_handler'):
            logger.removeHandler(self.log_handler)
        
        # Ensure the child process is terminated if still running
        if not self.process_stop_event.is_set():
            self.process_stop_event.set()
            logger.info("Encerrando processos em segundo plano...")
        
        # Encerrar a aplicação completamente
        logger.info("Encerrando aplicação...")
        self.root.destroy()
        import sys
        sys.exit(0)  # Força o encerramento completo do programa

    def on_closing(self):
        if messagebox.askokcancel("Sair", "Você deseja sair da aplicação?"):
            self.encerrar_aplicativo()

    def add_status_message(self, message):
        """Adiciona uma mensagem ao status_text e faz scroll para o final"""
        self.status_text.config(state='normal')
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state='disabled')

    def show_validation_error(self, title, unmapped_prisoners):
        """Exibe erro de validação com lista de presos não mapeados"""
        # Verificar se já existe uma janela de erro aberta
        if hasattr(self, '_validation_error_window') and self._validation_error_window is not None and self._validation_error_window.winfo_exists():
            logger.info("Janela de erro de validação já existe, não criando nova")
            return
            
        logger.info(f"Iniciando show_validation_error: {title}")
        logger.info(f"Presos não mapeados recebidos: {len(unmapped_prisoners) if unmapped_prisoners else 0}")
        
        self.login_button.config(state=tk.NORMAL)
        self.animation_running = False
        
        # Log adicional para debug
        logger.info("Criando janela de erro de validação...")
        
        # Forçar foco na janela principal antes de criar o popup
        self.root.lift()
        self.root.focus_force()

        # Criar janela de erro de validação
        validation_window = tk.Toplevel(self.root)
        self._validation_error_window = validation_window  # Guardar referência
        validation_window.title("Erro de Validação - Presos Não Mapeados")
        validation_window.geometry("900x800")
        validation_window.attributes('-topmost', True)
        validation_window.configure(bg='#1E2C44')
        
        logger.info("Janela de erro de validação criada com sucesso")
        logger.info(f"Título da janela: {validation_window.title()}")
        logger.info(f"Geometria da janela: {validation_window.geometry()}")
        
        # Centralizar a janela na tela
        validation_window.update_idletasks()
        width = validation_window.winfo_width()
        height = validation_window.winfo_height()
        x = (validation_window.winfo_screenwidth() // 2) - (width // 2)
        y = (validation_window.winfo_screenheight() // 2) - (height // 2)
        validation_window.geometry(f'{width}x{height}+{x}+{y}')

        # Título
        title_label = tk.Label(
            validation_window,
            text="❌ ERRO DE VALIDAÇÃO",
            font=('Segoe UI', 14, 'bold'),
            bg='#1b2838',
            fg='#e74c3c'
        )
        title_label.pack(pady=10)

        # Mensagem explicativa
        msg_label = tk.Label(
            validation_window,
            text="Os seguintes presos não puderam ser mapeados para alas/celas válidas:",
            font=('Segoe UI', 10),
            bg='#1b2838',
            fg='#ffffff',
            wraplength=750
        )
        msg_label.pack(pady=5)

        # Frame para a lista de presos
        list_frame = tk.Frame(validation_window, bg='#2b3a4a', bd=1, relief="solid")
        list_frame.pack(padx=20, pady=10, fill='both', expand=True)

        # Text widget para a lista
        list_text = tk.Text(
            list_frame,
            wrap='word',
            font=('Consolas', 9),
            bg='#2b3a4a',
            fg='#ffffff',
            relief='flat',
            bd=0,
            insertbackground='#ffffff'
        )
        list_text.pack(side='left', fill='both', expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(list_frame, command=list_text.yview)
        scrollbar.pack(side='right', fill='y')
        list_text.config(yscrollcommand=scrollbar.set)

        # Formatar e inserir a lista de presos
        formatted_list = []
        formatted_list.append("PRESOS NÃO MAPEADOS ENCONTRADOS:")
        formatted_list.append("=" * 70)
        formatted_list.append("")
        
        for i, prisoner in enumerate(unmapped_prisoners, 1):
            formatted_list.append(f"{i:2d}. Código: {prisoner['Código']:<8} | Nome: {prisoner['Nome']:<30} | Ala: {prisoner['Ala']:<10} | Cela: {prisoner['Cela']}")
        
        formatted_list.append("")
        formatted_list.append("=" * 70)
        formatted_list.append(f"TOTAL: {len(unmapped_prisoners)} presos não mapeados")
        formatted_list.append("")
        formatted_list.append("INSTRUÇÕES:")
        formatted_list.append("1. Copie esta lista usando o botão 'Copiar Lista'")
        formatted_list.append("2. Verifique as alas e celas no sistema Canaimé")
        formatted_list.append("3. Atualize a configuração das unidades se necessário")
        formatted_list.append("4. Execute o programa novamente")

        list_text.insert(tk.END, "\n".join(formatted_list))
        list_text.config(state='disabled')

        # Botão para copiar lista
        def copy_list():
            validation_window.clipboard_clear()
            validation_window.clipboard_append("\n".join(formatted_list))
            messagebox.showinfo("Copiado", "Lista de presos copiada para a área de transferência!", parent=validation_window)

        copy_button = tk.Button(
            validation_window,
            text="📋 Copiar Lista",
            font=('Segoe UI', 10, 'bold'),
            bg='#3498db',
            fg='white',
            relief='flat',
            cursor='hand2',
            command=copy_list,
            activebackground='#287bb8'
        )
        copy_button.pack(pady=10)

        # Botão para fechar
        close_button = tk.Button(
            validation_window,
            text="❌ Fechar",
            font=('Segoe UI', 10, 'bold'),
            bg='#e74c3c',
            fg='white',
            relief='flat',
            cursor='hand2',
            command=validation_window.destroy,
            activebackground='#c0392b'
        )
        close_button.pack(pady=5)

        # Adicionar mensagem no status
        self.add_status_message(f"ERRO: {len(unmapped_prisoners)} presos não mapeados encontrados. Verifique a janela de erro.")

        logger.info("Exibindo janela de erro de validação (grab_set + wait_window)")
        validation_window.grab_set()
        validation_window.wait_window()
        logger.info("Janela de erro de validação foi fechada")

    def show_ala_selection(self, alas):
        """Exibe janela para seleção de uma ou mais alas e envia a seleção para o processo filho."""
        if not alas:
            self.add_status_message("ERRO: Nenhuma ala encontrada.")
            return

        sel_win = tk.Toplevel(self.root)
        sel_win.title("Selecione as Alas")
        sel_win.geometry("520x520")
        sel_win.configure(bg="#1E2C44")
        sel_win.attributes('-topmost', True)

        tk.Label(
            sel_win,
            text="Selecione as alas desejadas:",
            font=('Segoe UI', 13, 'bold'),
            bg="#1E2C44",
            fg="#FFFFFF"
        ).pack(pady=10)

        frame = tk.Frame(sel_win, bg="#1E2C44")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Duas colunas de listas
        left_frame = tk.Frame(frame, bg="#1E2C44")
        right_frame = tk.Frame(frame, bg="#1E2C44")
        left_frame.pack(side='left', fill='both', expand=True, padx=(0,5))
        right_frame.pack(side='left', fill='both', expand=True, padx=(5,0))

        lb_left = tk.Listbox(
            left_frame,
            selectmode=tk.MULTIPLE,
            bg="#2B3C57",
            fg="#FFFFFF",
            font=('Segoe UI', 14),
            activestyle='none'
        )
        lb_left.pack(fill="both", expand=True)

        lb_right = tk.Listbox(
            right_frame,
            selectmode=tk.MULTIPLE,
            bg="#2B3C57",
            fg="#FFFFFF",
            font=('Segoe UI', 14),
            activestyle='none'
        )
        lb_right.pack(fill="both", expand=True)

        alas_sorted = sorted(set(alas))
        mid = (len(alas_sorted) + 1) // 2
        for a in alas_sorted[:mid]:
            lb_left.insert(tk.END, a)
        for a in alas_sorted[mid:]:
            lb_right.insert(tk.END, a)

        def confirm():
            selections = [lb_left.get(i) for i in lb_left.curselection()] + [lb_right.get(i) for i in lb_right.curselection()]
            if not selections:
                messagebox.showwarning("Atenção", "Selecione ao menos uma ala.", parent=sel_win)
                return
            # Enviar seleção para o processo filho
            self.command_queue.put(("selected_alas", selections))
            self.add_status_message(f"Alas selecionadas: {', '.join(selections)}")
            sel_win.destroy()

        tk.Button(
            sel_win,
            text="Confirmar",
            font=('Segoe UI', 12, 'bold'),
            bg="#3498db",
            fg='white',
            relief='flat',
            cursor='hand2',
            command=confirm
        ).pack(pady=10)

        # Centralizar janela
        sel_win.update_idletasks()
        width = sel_win.winfo_width()
        height = sel_win.winfo_height()
        x = (sel_win.winfo_screenwidth() // 2) - (width // 2)
        y = (sel_win.winfo_screenheight() // 2) - (height // 2)
        sel_win.geometry(f"{width}x{height}+{x}+{y}")

        sel_win.grab_set()
        sel_win.wait_window()

    def ask_save_path(self, suggested_name: str) -> str:
        # Caixa de diálogo para salvar PDF (centralizada e topmost)
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.attributes('-topmost', True)
        dialog.update_idletasks()
        filetypes = [("PDF", "*.pdf")]
        path = filedialog.asksaveasfilename(
            parent=dialog,
            defaultextension=".pdf",
            filetypes=filetypes,
            initialfile=suggested_name,
            title="Salvar PDF"
        )
        try:
            dialog.destroy()
        except Exception:
            pass
        return path or ""
