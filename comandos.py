# comandos.py - Traduce cada comando del usuario a operaciones del FileSystem
import os
import shlex


class ManejadorComandos:
    """
    Parsea y ejecuta los comandos del file system.
    Cada metodo retorna una lista de strings con la salida para la GUI.
    """

    def __init__(self, fs):
        self.fs = fs          # instancia de FileSystem
        # Funcion que recibe (titulo, pregunta) y retorna True/False.
        # La GUI la reemplaza por messagebox.askyesno; en tests es None (no pregunta).
        self.callback_confirmar = None
        # tabla de despacho: nombre_comando -> metodo
        self._tabla = {
            "create":         self._cmd_create,
            "file":           self._cmd_file,
            "mkdir":          self._cmd_mkdir,
            "cambiardir":     self._cmd_cambiardir,
            "cd":             self._cmd_cambiardir,
            "listardir":      self._cmd_listardir,
            "ls":             self._cmd_listardir,
            "modfile":        self._cmd_modfile,
            "verpropiedades": self._cmd_verpropiedades,
            "verfile":        self._cmd_verfile,
            "copy":           self._cmd_copy,
            "mover":          self._cmd_mover,
            "mv":             self._cmd_mover,
            "remove":         self._cmd_remove,
            "rm":             self._cmd_remove,
            "find":           self._cmd_find,
            "tree":           self._cmd_tree,
            "help":           self._cmd_help,
            "estado":         self._cmd_estado,
        }

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def ejecutar(self, linea):
        """
        Recibe la linea de texto del usuario, la parsea y ejecuta.
        Retorna lista de strings con la respuesta.
        """
        linea = linea.strip()
        if not linea:
            return []

        try:
            tokens = shlex.split(linea)
        except ValueError as e:
            return [f"[Error] Comillas mal formadas: {e}"]

        cmd = tokens[0].lower()
        args = tokens[1:]

        if cmd not in self._tabla:
            return [f"[Error] Comando desconocido: '{cmd}'. Escribe 'help' para ver los comandos."]

        try:
            return self._tabla[cmd](args)
        except Exception as e:
            return [f"[Error inesperado] {e}"]

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def _cmd_create(self, args):
        """CREATE <ruta_disco> <num_sectores> <tam_sector>"""
        if len(args) < 3:
            return ["Uso: CREATE <ruta_disco> <num_sectores> <tam_sector_bytes>"]

        ruta = args[0]
        try:
            nsec = int(args[1])
            tsec = int(args[2])
        except ValueError:
            return ["[Error] num_sectores y tam_sector deben ser numeros enteros."]

        if nsec <= 0 or tsec <= 0:
            return ["[Error] Los valores deben ser positivos."]

        # el sector 0 se reserva para el indice, necesitamos al menos 2
        if nsec < 2:
            return ["[Error] Se necesitan al menos 2 sectores."]

        try:
            self.fs.crear(ruta, nsec, tsec)
        except Exception as e:
            return [f"[Error] No se pudo crear el disco: {e}"]

        total_kb = (nsec * tsec) / 1024
        return [
            f"Disco creado: {ruta}",
            f"  Sectores: {nsec}  |  Tamano sector: {tsec} bytes  |  Total: {total_kb:.1f} KB",
        ]

    # ------------------------------------------------------------------
    # FILE
    # ------------------------------------------------------------------

    def _cmd_file(self, args):
        """FILE <nombre> <extension> <contenido...>"""
        if len(args) < 2:
            return ["Uso: FILE <nombre> <extension> [contenido]"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado. Usa CREATE primero."]

        nombre = args[0]
        extension = args[1].lstrip(".")
        contenido = " ".join(args[2:]) if len(args) > 2 else ""

        ok, msg = self.fs.crear_archivo(nombre, extension, contenido)

        if not ok and msg == "EXISTE":
            nombre_completo = f"{nombre}.{extension}" if extension else nombre
            if not self._preguntar_caer_encima(nombre_completo):
                return [f"Operacion cancelada. '{nombre_completo}' no fue reemplazado."]
            ok, msg = self.fs.crear_archivo(nombre, extension, contenido, force=True)

        if not ok:
            return [f"[Error] {msg}"]
        return [f"Archivo creado: {nombre}.{extension}"]

    # ------------------------------------------------------------------
    # MKDIR
    # ------------------------------------------------------------------

    def _cmd_mkdir(self, args):
        """MKDIR <nombre_directorio>"""
        if not args:
            return ["Uso: MKDIR <nombre>"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado. Usa CREATE primero."]

        nombre = args[0]
        ok, msg = self.fs.crear_directorio(nombre)

        if not ok and msg == "EXISTE":
            if not self._preguntar_caer_encima(nombre):
                return [f"Operacion cancelada. '{nombre}' no fue reemplazado."]
            ok, msg = self.fs.crear_directorio(nombre, force=True)

        if not ok:
            return [f"[Error] {msg}"]
        return [f"Directorio creado: {nombre}"]

    # ------------------------------------------------------------------
    # CAMBIARDIR / CD
    # ------------------------------------------------------------------

    def _cmd_cambiardir(self, args):
        """CAMBIARDIR <ruta>  |  CD <ruta>"""
        if not args:
            return ["Uso: CAMBIARDIR <ruta>"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        ruta = args[0]
        ok, msg = self.fs.cambiar_directorio(ruta)
        if not ok:
            return [f"[Error] {msg}"]
        return [f"Directorio actual: {self.fs.ruta_actual()}"]

    # ------------------------------------------------------------------
    # LISTARDIR / LS
    # ------------------------------------------------------------------

    def _cmd_listardir(self, args):
        """LISTARDIR  |  LS"""
        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        hijos = self.fs.directorio_actual.listar()
        if not hijos:
            return ["(directorio vacio)"]

        lineas = [f"Contenido de {self.fs.ruta_actual()}:"]
        lineas.append(f"  {'TIPO':<12} {'NOMBRE':<30} {'TAMANO':>10}  MODIFICACION")
        lineas.append("  " + "-" * 68)

        for nodo in hijos:
            if nodo.es_directorio():
                tipo = "[DIR]"
                nombre = nodo.nombre
                tamano = "-"
            else:
                tipo = "[ARCHIVO]"
                nombre = nodo.nombre_completo()
                tamano = f"{nodo.tamanio} B"
            fecha = nodo.fecha_modificacion.strftime("%Y-%m-%d %H:%M")
            lineas.append(f"  {tipo:<12} {nombre:<30} {tamano:>10}  {fecha}")

        return lineas

    # ------------------------------------------------------------------
    # MODFILE
    # ------------------------------------------------------------------

    def _cmd_modfile(self, args):
        """MODFILE <nombre_completo> <nuevo_contenido...>"""
        if len(args) < 2:
            return ["Uso: MODFILE <nombre.ext> <nuevo contenido>"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        nombre = args[0]
        nuevo = " ".join(args[1:])
        ok, msg = self.fs.modificar_archivo(nombre, nuevo)
        if not ok:
            return [f"[Error] {msg}"]
        return [f"Archivo '{nombre}' modificado."]

    # ------------------------------------------------------------------
    # VERPROPIEDADES
    # ------------------------------------------------------------------

    def _cmd_verpropiedades(self, args):
        """VERPROPIEDADES <nombre_completo>"""
        if not args:
            return ["Uso: VERPROPIEDADES <nombre>"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        props, msg = self.fs.propiedades(args[0])
        if props is None:
            return [f"[Error] {msg}"]

        lineas = [f"Propiedades de '{args[0]}':"]
        for k, v in props.items():
            lineas.append(f"  {k:<14}: {v}")
        return lineas

    # ------------------------------------------------------------------
    # VERFILE
    # ------------------------------------------------------------------

    def _cmd_verfile(self, args):
        """VERFILE <nombre_completo>"""
        if not args:
            return ["Uso: VERFILE <nombre.ext>"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        contenido, msg = self.fs.leer_archivo(args[0])
        if contenido is None:
            return [f"[Error] {msg}"]

        lineas = [f"--- Contenido de '{args[0]}' ---"]
        lineas += contenido.splitlines() or ["(archivo vacio)"]
        lineas.append("--- fin ---")
        return lineas

    # ------------------------------------------------------------------
    # COPY
    # ------------------------------------------------------------------

    def _cmd_copy(self, args):
        """
        COPY <origen> <destino>
        Detecta automaticamente el tipo de copia segun el prefijo:
          real:// -> ruta real del sistema operativo
          Sin prefijo -> ruta virtual del file system
        """
        if len(args) < 2:
            return [
                "Uso: COPY <origen> <destino>",
                "  Prefijo 'real://' para rutas del SO. Ejemplos:",
                "  COPY real://home/user/doc.txt /docs/doc.txt   (real -> virtual)",
                "  COPY /docs/doc.txt real://home/user/doc.txt   (virtual -> real)",
                "  COPY /docs/a.txt /docs/b.txt                  (virtual -> virtual)",
            ]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        origen, destino = args[0], args[1]
        PREFIJO = "real://"

        origen_real = origen.startswith(PREFIJO)
        destino_real = destino.startswith(PREFIJO)

        if origen_real and not destino_real:
            # real -> virtual
            ruta_real = origen[len(PREFIJO):]
            return self._copiar_real_a_virtual(ruta_real, destino)

        elif not origen_real and destino_real:
            # virtual -> real
            ruta_real = destino[len(PREFIJO):]
            return self._copiar_virtual_a_real(origen, ruta_real)

        elif not origen_real and not destino_real:
            # virtual -> virtual
            ok, msg = self.fs.copiar_virtual_a_virtual(origen, destino)
            if not ok:
                return [f"[Error] {msg}"]
            return [f"Copiado: {origen} -> {destino}"]

        else:
            return ["[Error] No se puede copiar de real a real con este comando."]

    def _copiar_real_a_virtual(self, ruta_real, ruta_virtual):
        """Copia un archivo o directorio real al file system virtual"""
        if os.path.isdir(ruta_real):
            return self._copiar_dir_real_a_virtual(ruta_real, ruta_virtual)

        if not os.path.isfile(ruta_real):
            return [f"[Error] No existe '{ruta_real}' en el sistema real"]

        with open(ruta_real, "rb") as f:
            contenido = f.read()

        nombre_base = os.path.basename(ruta_real)
        # resolver directorio destino dentro del FS virtual
        dir_dest, nombre_dest = self.fs._resolver_padre_y_nombre(ruta_virtual)
        if dir_dest is None:
            # si la ruta virtual es un directorio existente, copiar ahi
            dir_dest = self.fs._resolver_nodo(ruta_virtual)
            if dir_dest and dir_dest.es_directorio():
                nombre_dest = nombre_base
            else:
                return [f"[Error] Ruta virtual destino no valida: {ruta_virtual}"]

        partes = nombre_dest.rsplit(".", 1)
        nom = partes[0]
        ext = partes[1] if len(partes) > 1 else ""

        # guardar directorio actual, cambiar al destino y crear archivo
        dir_original = self.fs.directorio_actual
        self.fs.directorio_actual = dir_dest
        ok, msg = self.fs.crear_archivo(nom, ext, contenido)
        self.fs.directorio_actual = dir_original

        if not ok and msg == "EXISTE":
            nombre_completo = f"{nom}.{ext}" if ext else nom
            if not self._preguntar_caer_encima(nombre_completo):
                return [f"Operacion cancelada."]
            self.fs.directorio_actual = dir_dest
            ok, msg = self.fs.crear_archivo(nom, ext, contenido, force=True)
            self.fs.directorio_actual = dir_original

        if not ok:
            return [f"[Error] {msg}"]
        return [f"Copiado (real -> virtual): {ruta_real} -> {ruta_virtual}"]

    def _copiar_dir_real_a_virtual(self, ruta_dir_real, ruta_virtual):
        """Copia un directorio real (con todo su contenido) al FS virtual"""
        nombre = os.path.basename(ruta_dir_real.rstrip("/"))
        dir_dest = self.fs._resolver_nodo(ruta_virtual)
        if dir_dest is None or not dir_dest.es_directorio():
            return [f"[Error] El destino virtual '{ruta_virtual}' no es un directorio valido"]

        if dir_dest.existe(nombre):
            if not self._preguntar_caer_encima(nombre):
                return [f"Operacion cancelada."]
            self.fs.eliminar(nombre, recursivo=True)

        conteo = [0]  # contador de archivos copiados (lista para mutabilidad en closure)
        errores = []

        def copiar_recursivo(real_path, dir_virtual):
            for entry in os.scandir(real_path):
                if entry.is_dir():
                    nuevo = __import__('modelos').Directorio(entry.name, dir_virtual)
                    dir_virtual.agregar(nuevo)
                    copiar_recursivo(entry.path, nuevo)
                elif entry.is_file():
                    try:
                        with open(entry.path, "rb") as f:
                            cont = f.read()
                        partes = entry.name.rsplit(".", 1)
                        nom = partes[0]; ext = partes[1] if len(partes) > 1 else ""
                        sector = self.fs.disco.asignar(cont)
                        if sector is None:
                            errores.append(f"Sin espacio para '{entry.name}'")
                            return
                        from modelos import Archivo
                        a = Archivo(nom, ext, cont, dir_virtual)
                        a.sector_inicio = sector
                        dir_virtual.agregar(a)
                        conteo[0] += 1
                    except Exception as e:
                        errores.append(f"Error copiando '{entry.name}': {e}")

        from modelos import Directorio
        nuevo_dir = Directorio(nombre, dir_dest)
        dir_dest.agregar(nuevo_dir)
        copiar_recursivo(ruta_dir_real, nuevo_dir)
        self.fs._guardar_indice()

        salida = [f"Directorio copiado (real -> virtual): {ruta_dir_real} -> {ruta_virtual}",
                  f"  {conteo[0]} archivo(s) copiado(s)."]
        if errores:
            salida += [f"  [Advertencia] {e}" for e in errores]
        return salida

    def _copiar_virtual_a_real(self, ruta_virtual, ruta_real):
        """Copia un archivo o directorio virtual al sistema de archivos real"""
        nodo = self.fs._resolver_nodo(ruta_virtual)
        if nodo is None:
            return [f"[Error] No existe '{ruta_virtual}' en el file system virtual"]

        if nodo.es_directorio():
            return self._copiar_dir_virtual_a_real(nodo, ruta_real)

        # archivo simple
        contenido, msg = self.fs.leer_archivo(nodo.nombre_completo())
        if contenido is None:
            # intentar desde el directorio padre
            contenido = self.fs.disco.leer_datos(nodo.sector_inicio).rstrip(b'\x00').decode("utf-8", errors="replace")

        try:
            os.makedirs(os.path.dirname(ruta_real) or ".", exist_ok=True)
            with open(ruta_real, "w", encoding="utf-8") as f:
                f.write(contenido)
        except Exception as e:
            return [f"[Error] No se pudo escribir en el sistema real: {e}"]

        return [f"Copiado (virtual -> real): {ruta_virtual} -> {ruta_real}"]

    def _copiar_dir_virtual_a_real(self, nodo_dir, ruta_real_base):
        """Exporta recursivamente un directorio virtual al sistema real"""
        conteo = [0]
        errores = []

        def exportar(nodo, ruta_base):
            destino = os.path.join(ruta_base, nodo.nombre)
            os.makedirs(destino, exist_ok=True)
            for hijo in nodo.hijos.values():
                if hijo.es_directorio():
                    exportar(hijo, destino)
                else:
                    try:
                        datos = self.fs.disco.leer_datos(hijo.sector_inicio).rstrip(b'\x00')
                        ruta_arch = os.path.join(destino, hijo.nombre_completo())
                        with open(ruta_arch, "wb") as f:
                            f.write(datos)
                        conteo[0] += 1
                    except Exception as e:
                        errores.append(f"Error exportando '{hijo.nombre_completo()}': {e}")

        try:
            exportar(nodo_dir, ruta_real_base)
        except Exception as e:
            return [f"[Error] {e}"]

        salida = [f"Directorio copiado (virtual -> real): /{nodo_dir.nombre} -> {ruta_real_base}",
                  f"  {conteo[0]} archivo(s) exportado(s)."]
        if errores:
            salida += [f"  [Advertencia] {e}" for e in errores]
        return salida

    # ------------------------------------------------------------------
    # MOVER / MV
    # ------------------------------------------------------------------

    def _cmd_mover(self, args):
        """
        MOVER <origen> <destino>
        Si destino es un directorio existente: mueve ahi.
        Si no existe como directorio: renombra.
        """
        if len(args) < 2:
            return ["Uso: MOVER <origen> <destino>"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        origen, destino = args[0], args[1]

        # caso 1: el destino es un directorio existente -> mover conservando nombre
        nodo_dest = self.fs._resolver_nodo(destino)

        if nodo_dest is not None and nodo_dest.es_directorio():
            ok, msg = self.fs.mover(origen, destino_dir=destino)

        elif "/" in destino.rstrip("/"):
            # caso 2: el destino trae ruta + nombre nuevo (ej. documentos/notas2.txt)
            dir_parte, nombre_final = destino.rstrip("/").rsplit("/", 1)
            dir_parte = dir_parte if dir_parte else "/"
            nodo_dir = self.fs._resolver_nodo(dir_parte)
            if nodo_dir is None or not nodo_dir.es_directorio():
                return [f"[Error] Directorio destino no valido: {dir_parte}"]
            ok, msg = self.fs.mover(origen, destino_dir=dir_parte, nuevo_nombre=nombre_final)

        else:
            # caso 3: solo un nombre nuevo -> renombrar donde esta
            ok, msg = self.fs.mover(origen, nuevo_nombre=destino)

        if not ok:
            return [f"[Error] {msg}"]
        return [f"Movido/renombrado: {origen} -> {destino}"]

    # ------------------------------------------------------------------
    # REMOVE / RM
    # ------------------------------------------------------------------

    def _cmd_remove(self, args):
        """
        REMOVE <nombre> [-r]
        -r activa eliminacion recursiva para directorios con contenido.
        """
        if not args:
            return ["Uso: REMOVE <nombre> [-r]"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        recursivo = "-r" in args
        nombres = [a for a in args if a != "-r"]

        salida = []
        for nombre in nombres:
            ok, msg = self.fs.eliminar(nombre, recursivo)
            if ok:
                salida.append(f"Eliminado: {nombre}")
            else:
                salida.append(f"[Error] {msg}")
        return salida

    # ------------------------------------------------------------------
    # FIND
    # ------------------------------------------------------------------

    def _cmd_find(self, args):
        """FIND <patron>  (soporta wildcards: *.txt, reporte*)"""
        if not args:
            return ["Uso: FIND <patron>  (ej: FIND *.txt)"]

        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        patron = args[0]
        resultados = self.fs.buscar(patron)

        if not resultados:
            return [f"No se encontraron coincidencias para '{patron}'."]

        lineas = [f"Resultados para '{patron}':"]
        for r in resultados:
            lineas.append(f"  {r}")
        return lineas

    # ------------------------------------------------------------------
    # TREE
    # ------------------------------------------------------------------

    def _cmd_tree(self, args):
        """TREE  — muestra el arbol completo del file system"""
        if not self.fs.esta_montado():
            return ["[Error] No hay disco montado."]

        return self.fs.arbol_texto()

    # ------------------------------------------------------------------
    # ESTADO (extra util)
    # ------------------------------------------------------------------

    def _cmd_estado(self, args):
        """ESTADO  — muestra informacion del disco"""
        if not self.fs.esta_montado():
            return ["No hay disco montado."]

        d = self.fs.disco
        libres = d.sectores_libres()
        usados = d.sectores_usados()
        total = d.sector_count
        pct = (usados / total * 100) if total else 0

        barra = self._barra_uso(pct)
        return [
            "Estado del disco:",
            f"  Sectores totales : {total}",
            f"  Usados           : {usados}",
            f"  Libres           : {libres}",
            f"  Tamano sector    : {d.sector_size} bytes",
            f"  Espacio total    : {d.bytes_totales()} bytes",
            f"  Espacio libre    : {d.bytes_libres()} bytes",
            f"  Uso              : {barra} {pct:.1f}%",
        ]

    def _barra_uso(self, pct, ancho=20):
        llenos = int(pct / 100 * ancho)
        return "[" + "█" * llenos + "░" * (ancho - llenos) + "]"

    # ------------------------------------------------------------------
    # Utilidad interna: preguntar "caer encima"
    # ------------------------------------------------------------------

    def _preguntar_caer_encima(self, nombre):
        """
        Llama al callback de confirmacion si esta registrado (GUI),
        o devuelve False por defecto (entorno de pruebas sin UI).
        """
        if self.callback_confirmar:
            return self.callback_confirmar(
                "Nombre duplicado",
                f"'{nombre}' ya existe en este directorio.\n¿Desea reemplazarlo?"
            )
        return False

    # ------------------------------------------------------------------
    # HELP
    # ------------------------------------------------------------------

    def _cmd_help(self, args):
        return [
            "Comandos disponibles:",
            "  CREATE <disco> <sectores> <tam_sector>  - Crea un disco virtual",
            "  FILE <nombre> <ext> [contenido]         - Crea un archivo",
            "  MKDIR <nombre>                          - Crea un directorio",
            "  CAMBIARDIR <ruta>  |  CD <ruta>         - Cambia de directorio",
            "  LISTARDIR  |  LS                        - Lista el directorio actual",
            "  MODFILE <nombre.ext> <contenido>        - Modifica un archivo",
            "  VERPROPIEDADES <nombre>                 - Propiedades de un archivo/dir",
            "  VERFILE <nombre.ext>                    - Ver contenido de un archivo",
            "  COPY <origen> <destino>                 - Copia archivo (usar 'real://' para SO)",
            "  MOVER <origen> <destino>  |  MV         - Mueve o renombra",
            "  REMOVE <nombre> [-r]  |  RM             - Elimina (con -r recursivo)",
            "  FIND <patron>                           - Busca (ej: FIND *.txt)",
            "  TREE                                    - Muestra el arbol del FS",
            "  ESTADO                                  - Muestra el uso del disco",
            "  HELP                                    - Muestra esta ayuda",
            "  CLEAR                                   - Limpia la pantalla",
        ]
