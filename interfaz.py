# interfaz.py - Interfaz terminal con arbol siempre visible (requisito TREE)
import tkinter as tk
from tkinter import scrolledtext, messagebox
from filesystem import FileSystem
from comandos import ManejadorComandos

BG        = "#0d0d0d"
FG        = "#e0e0e0"
FG_PROMPT = "#5af78e"
FG_ERROR  = "#ff5c57"
FG_DIR    = "#57c7ff"
FG_ARCHIVO = "#f3f99d"
FG_TITULO  = "#ff6ac1"
FG_ACTUAL  = "#5af78e"   # directorio actual resaltado en el arbol


class Interfaz:
    def __init__(self, root):
        self.root = root
        self.root.title("SO-P3 File System")
        self.root.configure(bg=BG)
        self.root.geometry("1000x600")
        self.root.minsize(700, 400)

        self.fs = FileSystem()
        self.manejador = ManejadorComandos(self.fs)
        self.historial = []
        self.hist_idx = -1

        self.manejador.callback_confirmar = messagebox.askyesno

        self._construir_ui()
        self._mostrar_bienvenida()
        self._actualizar_arbol()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _construir_ui(self):
        # cuerpo: arbol izq | terminal der
        frame_cuerpo = tk.Frame(self.root, bg=BG)
        frame_cuerpo.pack(fill=tk.BOTH, expand=True)

        # --- panel arbol (izquierda, siempre visible) ---
        frame_arbol = tk.Frame(frame_cuerpo, bg=BG, width=220)
        frame_arbol.pack(fill=tk.Y, side=tk.LEFT)
        frame_arbol.pack_propagate(False)

        tk.Label(frame_arbol, text="TREE", bg=BG, fg=FG_TITULO,
                 font=("Courier", 10)).pack(anchor="w", padx=4, pady=(4, 0))

        # separador simple: solo una linea de fondo distinto
        tk.Frame(frame_arbol, bg="#333333", height=1).pack(fill=tk.X)

        self.txt_arbol = tk.Text(
            frame_arbol,
            bg=BG, fg=FG_DIR,
            font=("Courier", 10),
            wrap=tk.NONE,
            state=tk.DISABLED,
            relief=tk.FLAT,
            cursor="arrow",
            selectbackground="#1a1a1a",
            bd=0,
        )
        sb_arbol = tk.Scrollbar(frame_arbol, orient=tk.VERTICAL,
                                command=self.txt_arbol.yview, bg=BG)
        self.txt_arbol.configure(yscrollcommand=sb_arbol.set)
        sb_arbol.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_arbol.pack(fill=tk.BOTH, expand=True, padx=2)

        self.txt_arbol.tag_config("dir",    foreground=FG_DIR)
        self.txt_arbol.tag_config("archivo", foreground=FG_ARCHIVO)
        self.txt_arbol.tag_config("actual",  foreground=FG_ACTUAL)
        self.txt_arbol.tag_config("normal",  foreground=FG)

        # separador vertical entre paneles
        tk.Frame(frame_cuerpo, bg="#333333", width=1).pack(fill=tk.Y, side=tk.LEFT)

        # --- panel terminal (derecha) ---
        frame_terminal = tk.Frame(frame_cuerpo, bg=BG)
        frame_terminal.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        self.txt_salida = scrolledtext.ScrolledText(
            frame_terminal,
            bg=BG, fg=FG,
            font=("Courier", 12),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            insertbackground=FG,
            selectbackground="#333333",
            bd=0,
        )
        self.txt_salida.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))

        self.txt_salida.tag_config("prompt",   foreground=FG_PROMPT)
        self.txt_salida.tag_config("error",    foreground=FG_ERROR)
        self.txt_salida.tag_config("dir",      foreground=FG_DIR)
        self.txt_salida.tag_config("archivo",  foreground=FG_ARCHIVO)
        self.txt_salida.tag_config("titulo",   foreground=FG_TITULO)
        self.txt_salida.tag_config("normal",   foreground=FG)

        # linea de entrada
        frame_entrada = tk.Frame(frame_terminal, bg=BG)
        frame_entrada.pack(fill=tk.X, padx=4, pady=4)

        self.lbl_prompt = tk.Label(
            frame_entrada, text="/ $ ",
            bg=BG, fg=FG_PROMPT,
            font=("Courier", 12),
        )
        self.lbl_prompt.pack(side=tk.LEFT)

        self.entrada = tk.Entry(
            frame_entrada,
            bg=BG, fg=FG,
            font=("Courier", 12),
            insertbackground=FG,
            relief=tk.FLAT,
            bd=0,
        )
        self.entrada.pack(fill=tk.X, expand=True, side=tk.LEFT)
        self.entrada.bind("<Return>", self._on_enter)
        self.entrada.bind("<Up>",     self._hist_arriba)
        self.entrada.bind("<Down>",   self._hist_abajo)
        self.entrada.bind("<Tab>",    self._autocompletar)
        self.entrada.focus_set()

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def _on_enter(self, event=None):
        cmd = self.entrada.get().strip()
        if not cmd:
            return

        self.historial.append(cmd)
        self.hist_idx = len(self.historial)

        self._escribir_prompt(cmd)
        self.entrada.delete(0, tk.END)

        if cmd.lower() == "clear":
            self._limpiar_terminal()
        else:
            salida = self.manejador.ejecutar(cmd)
            for linea in salida:
                self._escribir_linea(linea)

        # actualizar arbol y prompt DESPUES de ejecutar el comando
        self._actualizar_arbol()
        self._actualizar_prompt_label()

    def _hist_arriba(self, event=None):
        if self.historial and self.hist_idx > 0:
            self.hist_idx -= 1
            self._set_entrada(self.historial[self.hist_idx])

    def _hist_abajo(self, event=None):
        if self.hist_idx < len(self.historial) - 1:
            self.hist_idx += 1
            self._set_entrada(self.historial[self.hist_idx])
        else:
            self.hist_idx = len(self.historial)
            self._set_entrada("")

    def _set_entrada(self, texto):
        self.entrada.delete(0, tk.END)
        self.entrada.insert(0, texto)

    def _autocompletar(self, event=None):
        if not self.fs.esta_montado():
            return "break"

        texto = self.entrada.get()
        tokens = texto.split()
        if not tokens:
            return "break"

        ultimo = tokens[-1]
        hijos = self.fs.directorio_actual.listar()
        nombres = [
            n.nombre if n.es_directorio() else n.nombre_completo()
            for n in hijos
        ]
        coincidencias = [n for n in nombres if n.startswith(ultimo)]

        if len(coincidencias) == 1:
            tokens[-1] = coincidencias[0]
            self._set_entrada(" ".join(tokens))
        elif len(coincidencias) > 1:
            self._escribir_linea("  " + "  ".join(coincidencias))

        return "break"

    # ------------------------------------------------------------------
    # Escritura en la terminal
    # ------------------------------------------------------------------

    def _escribir_prompt(self, cmd):
        ruta = self.fs.ruta_actual() if self.fs.esta_montado() else "/"
        self._append(f"{ruta} $ {cmd}\n", "prompt")

    def _escribir_linea(self, linea):
        self._append(linea + "\n", self._detectar_tag(linea))

    def _detectar_tag(self, linea):
        if linea.startswith("[Error]") or linea.startswith("[error]"):
            return "error"
        if linea.startswith("  [DIR]"):
            return "dir"
        if linea.startswith("  [ARCHIVO]"):
            return "archivo"
        if linea.startswith("---") or linea.endswith("---"):
            return "titulo"
        if linea.startswith("Comandos") or linea.startswith("Estado") \
                or linea.startswith("Propiedades") or linea.startswith("Contenido"):
            return "titulo"
        return "normal"

    def _append(self, texto, tag="normal"):
        self.txt_salida.configure(state=tk.NORMAL)
        self.txt_salida.insert(tk.END, texto, tag)
        self.txt_salida.see(tk.END)
        self.txt_salida.configure(state=tk.DISABLED)

    def _limpiar_terminal(self):
        self.txt_salida.configure(state=tk.NORMAL)
        self.txt_salida.delete("1.0", tk.END)
        self.txt_salida.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Actualizacion de paneles
    # ------------------------------------------------------------------

    def _actualizar_prompt_label(self):
        ruta = self.fs.ruta_actual() if self.fs.esta_montado() else "/"
        self.lbl_prompt.configure(text=f"{ruta} $ ")

    def _actualizar_arbol(self):
        self.txt_arbol.configure(state=tk.NORMAL)
        self.txt_arbol.delete("1.0", tk.END)

        if not self.fs.esta_montado():
            self.txt_arbol.insert(tk.END, "(sin disco)\n", "normal")
        else:
            ruta_actual = self.fs.ruta_actual()
            for linea in self.fs.arbol_texto():
                # resaltar el nodo del directorio actual
                nombre_actual = ruta_actual.split("/")[-1] or "raiz"
                if nombre_actual != "raiz" and nombre_actual in linea:
                    tag = "actual"
                elif "[DIR]" in linea or "📁" in linea or "raiz" in linea:
                    tag = "dir"
                elif "📄" in linea:
                    tag = "archivo"
                else:
                    tag = "normal"
                self.txt_arbol.insert(tk.END, linea + "\n", tag)

        self.txt_arbol.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Bienvenida
    # ------------------------------------------------------------------

    def _mostrar_bienvenida(self):
        self._append("File System Simulado -- SO-P3 I-2026 -- ITCR\n", "titulo")
        self._append("Escribe 'help' para ver los comandos disponibles.\n", "normal")
        self._append("Escribe 'clear' para limpiar la pantalla.\n\n", "normal")

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------

    def cerrar(self):
        if self.fs.esta_montado():
            try:
                self.fs.desmontar()
            except Exception:
                pass
        self.root.destroy()
