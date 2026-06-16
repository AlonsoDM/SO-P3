#!/usr/bin/env python3
# main.py - Punto de entrada del simulador de File System
import tkinter as tk
from interfaz import Interfaz


def main():
    root = tk.Tk()
    app = Interfaz(root)

    # al cerrar la ventana, guardamos el indice del file system en disco
    root.protocol("WM_DELETE_WINDOW", app.cerrar)

    root.mainloop()


if __name__ == "__main__":
    main()
