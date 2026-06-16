# modelos.py - Estructuras en memoria para el file system
import datetime


class Nodo:
    """Base para archivos y directorios"""
    def __init__(self, nombre, padre=None):
        self.nombre = nombre
        self.padre = padre
        self.fecha_creacion = datetime.datetime.now()
        self.fecha_modificacion = datetime.datetime.now()

    def es_directorio(self):
        raise NotImplementedError

    def _nombre_en_ruta(self):
        """Nombre que se muestra al construir una ruta (Archivo lo sobrescribe)"""
        return self.nombre

    def ruta_completa(self):
        """Construye la ruta absoluta del nodo"""
        partes = []
        actual = self
        while actual is not None:
            partes.append(actual._nombre_en_ruta())
            actual = actual.padre
        partes.reverse()
        # el primer elemento es "root", lo convertimos a "/"
        if len(partes) == 1:
            return "/"
        return "/" + "/".join(partes[1:])


class Archivo(Nodo):
    """Representa un archivo en el file system"""
    def __init__(self, nombre, extension, contenido=b"", padre=None):
        super().__init__(nombre, padre)
        self.extension = extension.lstrip(".")
        self.contenido = contenido      # bytes en memoria
        self.sector_inicio = -1         # sector inicial en disco (-1 = no guardado)
        self.tamanio = len(contenido)

    def es_directorio(self):
        return False

    def nombre_completo(self):
        """Retorna nombre.extension o solo nombre si no hay extension"""
        if self.extension:
            return f"{self.nombre}.{self.extension}"
        return self.nombre

    def _nombre_en_ruta(self):
        return self.nombre_completo()

    def actualizar_contenido(self, nuevo_contenido):
        if isinstance(nuevo_contenido, str):
            nuevo_contenido = nuevo_contenido.encode("utf-8")
        self.contenido = nuevo_contenido
        self.tamanio = len(nuevo_contenido)
        self.fecha_modificacion = datetime.datetime.now()


class Directorio(Nodo):
    """Representa un directorio en el file system"""
    def __init__(self, nombre, padre=None):
        super().__init__(nombre, padre)
        self.hijos = {}     # clave: nombre_completo -> Nodo

    def es_directorio(self):
        return True

    def agregar(self, nodo):
        """Agrega un hijo al directorio"""
        clave = nodo.nombre if nodo.es_directorio() else nodo.nombre_completo()
        self.hijos[clave] = nodo
        nodo.padre = self
        self.fecha_modificacion = datetime.datetime.now()

    def eliminar(self, clave):
        """Elimina un hijo por nombre"""
        if clave in self.hijos:
            del self.hijos[clave]
            self.fecha_modificacion = datetime.datetime.now()
            return True
        return False

    def buscar(self, clave):
        """Busca un hijo por nombre exacto"""
        return self.hijos.get(clave)

    def existe(self, clave):
        return clave in self.hijos

    def listar(self):
        """Retorna lista de hijos ordenada: directorios primero"""
        dirs = sorted(
            [n for n in self.hijos.values() if n.es_directorio()],
            key=lambda x: x.nombre
        )
        archivos = sorted(
            [n for n in self.hijos.values() if not n.es_directorio()],
            key=lambda x: x.nombre
        )
        return dirs + archivos
