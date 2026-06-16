# filesystem.py - Logica principal del file system (arbrol en memoria + disco)
import json
import datetime
from modelos import Archivo, Directorio
from disco import Disco


class FileSystem:
    """
    Coordina el arbol de directorios en memoria y la persistencia en disco.
    El arbol vive en RAM; el disco guarda el contenido real de los archivos.
    """

    def __init__(self):
        self.disco = Disco()
        self.raiz = None            # nodo raiz del arbol
        self.directorio_actual = None
        self._montado = False

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def crear(self, ruta_disco, sector_count, sector_size):
        """Crea un disco nuevo y un arbol vacio"""
        self.disco.crear(ruta_disco, sector_count, sector_size)
        self.raiz = Directorio("root")
        self.directorio_actual = self.raiz
        self._montado = True
        self._guardar_indice()

    def montar(self, ruta_disco):
        """Abre un disco existente y reconstruye el arbol desde el indice"""
        self.disco.abrir(ruta_disco)
        # intentar recuperar el indice guardado
        ok = self._cargar_indice()
        if not ok:
            self.raiz = Directorio("root")
        self.directorio_actual = self.raiz
        self._montado = True

    def desmontar(self):
        """Guarda el indice en disco antes de cerrar"""
        if self._montado:
            self._guardar_indice()
            self._montado = False

    def esta_montado(self):
        return self._montado

    # ------------------------------------------------------------------
    # Persistencia del indice (metadata del arbol como JSON en disco)
    # ------------------------------------------------------------------
    # El arbol se serializa a JSON y se guarda como una cadena de sectores
    # mas (asignada con las mismas reglas first-fit + enlazada que un
    # archivo). El encabezado del disco guarda el puntero a esa cadena.

    def _arbol_a_dict(self, nodo):
        """Serializa el arbol recursivamente a dict para JSON"""
        base = {
            "nombre": nodo.nombre,
            "es_dir": nodo.es_directorio(),
            "fecha_creacion": nodo.fecha_creacion.isoformat(),
            "fecha_modificacion": nodo.fecha_modificacion.isoformat(),
        }
        if nodo.es_directorio():
            base["hijos"] = [self._arbol_a_dict(h) for h in nodo.hijos.values()]
        else:
            base["extension"] = nodo.extension
            base["sector_inicio"] = nodo.sector_inicio
            base["tamanio"] = nodo.tamanio
        return base

    def _dict_a_arbol(self, d, padre=None):
        """Reconstruye el arbol desde un dict JSON"""
        if d["es_dir"]:
            nodo = Directorio(d["nombre"], padre)
            nodo.fecha_creacion = datetime.datetime.fromisoformat(d["fecha_creacion"])
            nodo.fecha_modificacion = datetime.datetime.fromisoformat(d["fecha_modificacion"])
            for hijo_d in d.get("hijos", []):
                hijo = self._dict_a_arbol(hijo_d, nodo)
                clave = hijo.nombre if hijo.es_directorio() else hijo.nombre_completo()
                nodo.hijos[clave] = hijo
        else:
            nodo = Archivo(d["nombre"], d["extension"], padre=padre)
            nodo.fecha_creacion = datetime.datetime.fromisoformat(d["fecha_creacion"])
            nodo.fecha_modificacion = datetime.datetime.fromisoformat(d["fecha_modificacion"])
            nodo.sector_inicio = d["sector_inicio"]
            nodo.tamanio = d["tamanio"]
        return nodo

    def _guardar_indice(self):
        """Serializa el arbol a JSON y lo persiste como cadena de sectores"""
        datos = json.dumps(self._arbol_a_dict(self.raiz)).encode("utf-8")
        self.disco.guardar_indice(datos)

    def _cargar_indice(self):
        """Lee y reconstruye el arbol guardado en el disco (si existe)"""
        try:
            datos = self.disco.leer_indice().rstrip(b'\x00')
            if not datos:
                return False
            d = json.loads(datos.decode("utf-8"))
            self.raiz = self._dict_a_arbol(d)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Navegacion
    # ------------------------------------------------------------------

    def ruta_actual(self):
        return self.directorio_actual.ruta_completa()

    def cambiar_directorio(self, ruta):
        """
        Acepta rutas absolutas (/dir1/dir2) o relativas (dir2, .., .).
        Retorna (True, "") o (False, mensaje_error).
        """
        if ruta == "/":
            self.directorio_actual = self.raiz
            return True, ""

        if ruta == "..":
            if self.directorio_actual.padre is not None:
                self.directorio_actual = self.directorio_actual.padre
            return True, ""

        if ruta == ".":
            return True, ""

        if ruta.startswith("/"):
            # ruta absoluta
            nodo = self._resolver_ruta(ruta)
        else:
            # ruta relativa
            nodo = self._resolver_ruta_relativa(ruta)

        if nodo is None:
            return False, f"No existe el directorio: {ruta}"
        if not nodo.es_directorio():
            return False, f"'{ruta}' no es un directorio"
        self.directorio_actual = nodo
        return True, ""

    def _resolver_ruta(self, ruta_abs):
        """Resuelve una ruta absoluta desde la raiz"""
        partes = [p for p in ruta_abs.split("/") if p]
        nodo = self.raiz
        for parte in partes:
            if not nodo.es_directorio():
                return None
            nodo = nodo.buscar(parte)
            if nodo is None:
                return None
        return nodo

    def _resolver_nodo(self, ruta):
        """Resuelve una ruta (absoluta o relativa) al nodo correspondiente"""
        if ruta.startswith("/"):
            return self._resolver_ruta(ruta)
        return self._resolver_ruta_relativa(ruta)

    def _resolver_padre_y_nombre(self, ruta):
        """
        Divide una ruta en (directorio_contenedor, nombre_final).
        Sirve para ubicar un nodo sin importar si esta en el directorio
        actual o en una subruta (ej. 'documentos/notas.txt').
        Retorna (None, None) si el directorio contenedor no es valido.
        """
        ruta = ruta.rstrip("/")
        if "/" in ruta:
            dir_parte, nombre = ruta.rsplit("/", 1)
            if dir_parte == "":
                directorio = self.raiz
            else:
                directorio = self._resolver_nodo(dir_parte)
        else:
            directorio = self.directorio_actual
            nombre = ruta

        if directorio is None or not directorio.es_directorio():
            return None, None
        return directorio, nombre

    def _resolver_ruta_relativa(self, ruta):
        """Resuelve una ruta relativa desde el directorio actual"""
        partes = [p for p in ruta.split("/") if p]
        nodo = self.directorio_actual
        for parte in partes:
            if parte == "..":
                if nodo.padre:
                    nodo = nodo.padre
            elif parte == ".":
                pass
            else:
                if not nodo.es_directorio():
                    return None
                nodo = nodo.buscar(parte)
                if nodo is None:
                    return None
        return nodo

    # ------------------------------------------------------------------
    # Operaciones de archivos y directorios
    # ------------------------------------------------------------------

    def crear_directorio(self, nombre, force=False):
        """
        Crea un directorio en el directorio actual.
        Si ya existe y force=False devuelve ("EXISTE", nombre) para que
        la capa de UI pueda preguntar al usuario si desea sobreescribir.
        Si force=True elimina el existente y crea uno nuevo vacio.
        """
        if self.directorio_actual.existe(nombre):
            if not force:
                return False, "EXISTE"
            # sobreescribir: eliminar el existente primero
            self._eliminar_recursivo(self.directorio_actual.buscar(nombre))
            self.directorio_actual.eliminar(nombre)

        nuevo = Directorio(nombre, self.directorio_actual)
        self.directorio_actual.agregar(nuevo)
        self._guardar_indice()
        return True, ""

    def crear_archivo(self, nombre, extension, contenido, force=False):
        """
        Crea un archivo y lo persiste en disco.
        Si ya existe y force=False devuelve ("EXISTE", nombre_completo).
        Si force=True libera los sectores del antiguo y crea uno nuevo.
        """
        if not self.disco.esta_montado():
            return False, "No hay disco montado"

        nombre_completo = f"{nombre}.{extension}" if extension else nombre

        if self.directorio_actual.existe(nombre_completo):
            if not force:
                return False, "EXISTE"
            # sobreescribir: liberar sectores del archivo anterior
            viejo = self.directorio_actual.buscar(nombre_completo)
            if viejo.sector_inicio >= 0:
                self.disco.liberar(viejo.sector_inicio)
            self.directorio_actual.eliminar(nombre_completo)

        if isinstance(contenido, str):
            contenido = contenido.encode("utf-8")

        sector = self.disco.asignar(contenido)
        if sector is None:
            return False, "No hay sectores suficientes en el disco"

        nuevo = Archivo(nombre, extension, contenido, self.directorio_actual)
        nuevo.sector_inicio = sector
        self.directorio_actual.agregar(nuevo)
        self._guardar_indice()
        return True, ""

    def modificar_archivo(self, nombre_completo, nuevo_contenido):
        """Reemplaza el contenido de un archivo existente"""
        nodo = self.directorio_actual.buscar(nombre_completo)
        if nodo is None:
            return False, f"No existe '{nombre_completo}'"
        if nodo.es_directorio():
            return False, f"'{nombre_completo}' es un directorio"

        if isinstance(nuevo_contenido, str):
            nuevo_contenido = nuevo_contenido.encode("utf-8")

        nuevo_sector = self.disco.reasignar(nodo.sector_inicio, nuevo_contenido)
        if nuevo_sector is None:
            return False, "No hay espacio en disco para los nuevos datos"

        nodo.sector_inicio = nuevo_sector
        nodo.actualizar_contenido(nuevo_contenido)
        self._guardar_indice()
        return True, ""

    def leer_archivo(self, nombre_completo):
        """Retorna el contenido de un archivo como string"""
        nodo = self.directorio_actual.buscar(nombre_completo)
        if nodo is None:
            return None, f"No existe '{nombre_completo}'"
        if nodo.es_directorio():
            return None, f"'{nombre_completo}' es un directorio"

        datos = self.disco.leer_datos(nodo.sector_inicio)
        return datos.rstrip(b'\x00').decode("utf-8", errors="replace"), ""

    def eliminar(self, nombre, recursivo=False):
        """Elimina un archivo o directorio (recursivo para dirs con contenido)"""
        nodo = self.directorio_actual.buscar(nombre)
        if nodo is None:
            return False, f"No existe '{nombre}'"

        if nodo.es_directorio():
            if nodo.hijos and not recursivo:
                return False, f"El directorio '{nombre}' no esta vacio (usa -r para recursivo)"
            self._eliminar_recursivo(nodo)
        else:
            # liberar sectores del archivo
            if nodo.sector_inicio >= 0:
                self.disco.liberar(nodo.sector_inicio)

        self.directorio_actual.eliminar(nombre)
        self._guardar_indice()
        return True, ""

    def _eliminar_recursivo(self, directorio):
        """Elimina todos los hijos de un directorio recursivamente"""
        for hijo in list(directorio.hijos.values()):
            if hijo.es_directorio():
                self._eliminar_recursivo(hijo)
            else:
                if hijo.sector_inicio >= 0:
                    self.disco.liberar(hijo.sector_inicio)

    def mover(self, origen, destino_dir=None, nuevo_nombre=None):
        """
        Mueve o renombra un nodo. 'origen' puede ser un nombre simple
        ('notas.txt') o una ruta ('documentos/notas.txt').
        - Si destino_dir es None: renombra dejandolo en su directorio actual.
        - Si nuevo_nombre es None: conserva el nombre original al mover.
        """
        dir_origen, nombre_origen = self._resolver_padre_y_nombre(origen)
        if dir_origen is None:
            return False, f"Ruta de origen no valida: {origen}"

        nodo = dir_origen.buscar(nombre_origen)
        if nodo is None:
            return False, f"No existe '{origen}'"

        dir_destino = dir_origen
        if destino_dir is not None:
            resultado = self._resolver_nodo(destino_dir)
            if resultado is None or not resultado.es_directorio():
                return False, f"Directorio destino no valido: {destino_dir}"
            dir_destino = resultado

        nombre_final = nuevo_nombre if nuevo_nombre else nombre_origen

        choca = dir_destino.existe(nombre_final)
        es_mismo_lugar = (dir_destino is dir_origen and nombre_origen == nombre_final)
        if choca and not es_mismo_lugar:
            return False, f"Ya existe '{nombre_final}' en el destino"

        dir_origen.eliminar(nombre_origen)

        if nuevo_nombre:
            if not nodo.es_directorio():
                partes = nuevo_nombre.rsplit(".", 1)
                nodo.nombre = partes[0]
                nodo.extension = partes[1] if len(partes) > 1 else ""
            else:
                nodo.nombre = nuevo_nombre

        dir_destino.agregar(nodo)
        self._guardar_indice()
        return True, ""

    def copiar_virtual_a_virtual(self, origen, destino):
        """
        Copia un archivo o directorio de una ruta virtual a otra.
        Si el origen es un directorio, lo copia de forma recursiva.
        """
        nodo_origen = self._resolver_nodo(origen)
        if nodo_origen is None:
            return False, f"No existe el origen: {origen}"

        if nodo_origen.es_directorio():
            return self._copiar_dir_virtual(nodo_origen, destino)

        # --- copia de archivo ---
        # Si el destino es un directorio existente, copiar dentro con el nombre original
        nodo_dest = self._resolver_nodo(destino)
        if nodo_dest is not None and nodo_dest.es_directorio():
            dir_dest = nodo_dest
            nombre_dest = nodo_origen.nombre_completo()
        else:
            dir_dest, nombre_dest = self._resolver_padre_y_nombre(destino)
            if dir_dest is None:
                return False, f"Directorio destino no valido: {destino}"

        partes_nombre = nombre_dest.rsplit(".", 1)
        nom = partes_nombre[0]
        ext = partes_nombre[1] if len(partes_nombre) > 1 else nodo_origen.extension

        nombre_completo = f"{nom}.{ext}" if ext else nom
        if dir_dest.existe(nombre_completo):
            return False, f"Ya existe '{nombre_completo}' en destino"

        contenido = self.disco.leer_datos(nodo_origen.sector_inicio).rstrip(b'\x00')
        sector = self.disco.asignar(contenido)
        if sector is None:
            return False, "No hay espacio en disco"

        copia = Archivo(nom, ext, contenido, dir_dest)
        copia.sector_inicio = sector
        dir_dest.agregar(copia)
        self._guardar_indice()
        return True, ""

    def _copiar_dir_virtual(self, dir_origen, destino_str):
        """
        Copia recursivamente un directorio a una ruta virtual destino.
        Crea el directorio con el mismo nombre dentro del destino.
        """
        dir_dest_padre, nombre_copia = self._resolver_padre_y_nombre(destino_str)
        if dir_dest_padre is None:
            # si el destino no especifica nombre, usar el nombre original
            dir_dest_padre = self._resolver_nodo(destino_str)
            nombre_copia = dir_origen.nombre
            if dir_dest_padre is None or not dir_dest_padre.es_directorio():
                return False, f"Directorio destino no valido: {destino_str}"

        if dir_dest_padre.existe(nombre_copia):
            return False, f"Ya existe '{nombre_copia}' en el destino"

        nuevo_dir = Directorio(nombre_copia, dir_dest_padre)
        dir_dest_padre.agregar(nuevo_dir)

        ok, msg = self._copiar_hijos_recursivo(dir_origen, nuevo_dir)
        if not ok:
            return False, msg

        self._guardar_indice()
        return True, ""

    def _copiar_hijos_recursivo(self, origen, destino):
        """Copia todos los hijos de 'origen' dentro de 'destino'"""
        for hijo in origen.hijos.values():
            if hijo.es_directorio():
                nuevo_sub = Directorio(hijo.nombre, destino)
                destino.agregar(nuevo_sub)
                ok, msg = self._copiar_hijos_recursivo(hijo, nuevo_sub)
                if not ok:
                    return False, msg
            else:
                contenido = self.disco.leer_datos(hijo.sector_inicio).rstrip(b'\x00')
                sector = self.disco.asignar(contenido)
                if sector is None:
                    return False, "No hay espacio en disco durante la copia"
                copia = Archivo(hijo.nombre, hijo.extension, contenido, destino)
                copia.sector_inicio = sector
                destino.agregar(copia)
        return True, ""

    # ------------------------------------------------------------------
    # Busqueda
    # ------------------------------------------------------------------

    def buscar(self, patron):
        """
        Busca archivos/dirs cuyo nombre coincida con el patron.
        Soporta wildcard '*' (ej: *.txt, reporte*).
        Retorna lista de rutas absolutas.
        """
        import fnmatch
        resultados = []
        self._buscar_recursivo(self.raiz, patron, resultados, fnmatch)
        return resultados

    def _buscar_recursivo(self, nodo, patron, resultados, fnmatch_mod):
        if not nodo.es_directorio():
            return
        for hijo in nodo.hijos.values():
            nombre = hijo.nombre if hijo.es_directorio() else hijo.nombre_completo()
            if fnmatch_mod.fnmatch(nombre, patron):
                resultados.append(hijo.ruta_completa())
            if hijo.es_directorio():
                self._buscar_recursivo(hijo, patron, resultados, fnmatch_mod)

    # ------------------------------------------------------------------
    # Arbol visual (siempre visible en la GUI)
    # ------------------------------------------------------------------

    def arbol_texto(self, nodo=None, prefijo="", es_ultimo=True):
        """Genera el arbol de directorios como texto para la GUI"""
        if nodo is None:
            nodo = self.raiz

        lineas = []
        conector = "└── " if es_ultimo else "├── "
        icono = "📁 " if nodo.es_directorio() else "📄 "
        nombre = nodo.nombre if nodo is self.raiz else (
            nodo.nombre if nodo.es_directorio() else nodo.nombre_completo()
        )

        if nodo is self.raiz:
            lineas.append(f"/ (raiz)")
            prefijo_hijo = ""
        else:
            lineas.append(f"{prefijo}{conector}{icono}{nombre}")
            prefijo_hijo = prefijo + ("    " if es_ultimo else "│   ")

        if nodo.es_directorio():
            hijos = nodo.listar()
            for i, hijo in enumerate(hijos):
                ultimo = (i == len(hijos) - 1)
                lineas += self.arbol_texto(hijo, prefijo_hijo, ultimo)

        return lineas

    def propiedades(self, nombre_completo):
        """Retorna dict con las propiedades de un nodo"""
        nodo = self.directorio_actual.buscar(nombre_completo)
        if nodo is None:
            return None, f"No existe '{nombre_completo}'"

        if nodo.es_directorio():
            return {
                "nombre": nodo.nombre,
                "tipo": "Directorio",
                "creacion": nodo.fecha_creacion.strftime("%Y-%m-%d %H:%M:%S"),
                "modificacion": nodo.fecha_modificacion.strftime("%Y-%m-%d %H:%M:%S"),
            }, ""
        else:
            return {
                "nombre": nodo.nombre,
                "extension": nodo.extension,
                "tipo": "Archivo",
                "tamanio": f"{nodo.tamanio} bytes",
                "creacion": nodo.fecha_creacion.strftime("%Y-%m-%d %H:%M:%S"),
                "modificacion": nodo.fecha_modificacion.strftime("%Y-%m-%d %H:%M:%S"),
                "sector_inicio": nodo.sector_inicio,
            }, ""
