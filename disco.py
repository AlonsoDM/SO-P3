# disco.py - Disco virtual como archivo binario con FAT enlazada
import struct
import os

# Constantes del encabezado del disco
MAGIC = b'FS01'
HEADER_SIZE = 16        # magic(4) + sector_count(4) + sector_size(4) + indice_inicio(4)
# OJO: estos valores NO pueden coincidir con un numero de sector valido (>= 0),
# de lo contrario un sector real (ej. el sector 0) se confundiria con "libre".
FAT_LIBRE = -2          # sector libre
FAT_EOF = -1            # fin de cadena de sectores


class Disco:
    """
    Maneja el archivo binario que simula el disco.

    Estructura del archivo en disco:
      [Encabezado 16 bytes]
      [FAT: sector_count * 4 bytes]
      [Sectores de datos: sector_count * sector_size bytes]
    """

    def __init__(self):
        self.ruta = None
        self.sector_count = 0
        self.sector_size = 0
        self.fat = []           # tabla de asignacion en memoria
        self.indice_inicio = FAT_EOF   # sector donde inicia el indice del arbol (-1 = no existe)
        self._fat_offset = HEADER_SIZE
        self._datos_offset = 0

    # ------------------------------------------------------------------
    # Creacion y apertura
    # ------------------------------------------------------------------

    def crear(self, ruta, sector_count, sector_size):
        """Crea un disco nuevo e inicializa todo en ceros"""
        self.ruta = ruta
        self.sector_count = sector_count
        self.sector_size = sector_size
        self.fat = [FAT_LIBRE] * sector_count
        self.indice_inicio = FAT_EOF
        self._fat_offset = HEADER_SIZE
        self._datos_offset = HEADER_SIZE + sector_count * 4

        with open(ruta, 'wb') as f:
            f.write(MAGIC)
            f.write(struct.pack('>II', sector_count, sector_size))
            f.write(struct.pack('>i', self.indice_inicio))   # puntero al indice (-1 = no existe)
            for _ in range(sector_count):               # FAT vacia
                f.write(struct.pack('>i', FAT_LIBRE))
            f.write(b'\x00' * (sector_count * sector_size))  # datos vacios

    def abrir(self, ruta):
        """Abre un disco existente y carga la FAT en memoria"""
        if not os.path.exists(ruta):
            raise FileNotFoundError(f"No se encontró el disco: {ruta}")

        with open(ruta, 'rb') as f:
            magic = f.read(4)
            if magic != MAGIC:
                raise ValueError("El archivo no es un disco valido (magic incorrecto)")

            self.sector_count, self.sector_size = struct.unpack('>II', f.read(8))
            self.indice_inicio = struct.unpack('>i', f.read(4))[0]

            self.fat = [struct.unpack('>i', f.read(4))[0] for _ in range(self.sector_count)]

        self.ruta = ruta
        self._fat_offset = HEADER_SIZE
        self._datos_offset = HEADER_SIZE + self.sector_count * 4

    # ------------------------------------------------------------------
    # Lectura y escritura de sectores
    # ------------------------------------------------------------------

    def _offset_sector(self, num):
        return self._datos_offset + num * self.sector_size

    def leer_sector(self, num):
        """Devuelve los bytes crudos de un sector"""
        with open(self.ruta, 'rb') as f:
            f.seek(self._offset_sector(num))
            return f.read(self.sector_size)

    def escribir_sector(self, num, datos):
        """Escribe datos en un sector (rellena o trunca segun sector_size)"""
        if isinstance(datos, str):
            datos = datos.encode('utf-8')
        datos = (datos + b'\x00' * self.sector_size)[:self.sector_size]
        with open(self.ruta, 'r+b') as f:
            f.seek(self._offset_sector(num))
            f.write(datos)

    def limpiar_sector(self, num):
        self.escribir_sector(num, b'\x00' * self.sector_size)

    # ------------------------------------------------------------------
    # FAT
    # ------------------------------------------------------------------

    def _guardar_fat(self):
        """Persiste la FAT en memoria al archivo de disco"""
        with open(self.ruta, 'r+b') as f:
            f.seek(self._fat_offset)
            for val in self.fat:
                f.write(struct.pack('>i', val))

    def _guardar_puntero_indice(self):
        """Persiste en el encabezado el sector donde inicia el indice del arbol"""
        with open(self.ruta, 'r+b') as f:
            f.seek(12)      # offset del campo indice_inicio en el encabezado
            f.write(struct.pack('>i', self.indice_inicio))

    # ------------------------------------------------------------------
    # Indice del arbol (metadata persistida en una cadena de sectores)
    # ------------------------------------------------------------------
    # En vez de fijar un sector "magico", el encabezado guarda un puntero
    # al primer sector de la cadena del indice. Asi se asigna y libera con
    # las mismas reglas (first fit + enlazado) que cualquier archivo.

    def guardar_indice(self, datos):
        """Reemplaza el indice guardado por nuevos datos. True si se pudo."""
        nuevo_inicio = self.reasignar(self.indice_inicio, datos)
        if nuevo_inicio is None:
            return False
        self.indice_inicio = nuevo_inicio
        self._guardar_puntero_indice()
        return True

    def leer_indice(self):
        """Retorna los bytes del indice, o vacio si todavia no existe"""
        if self.indice_inicio < 0:
            return b''
        return self.leer_datos(self.indice_inicio)

    # ------------------------------------------------------------------
    # Asignacion FIRST FIT + enlazada
    # ------------------------------------------------------------------

    def _buscar_libres(self, n):
        """First fit: busca los primeros n sectores libres"""
        libres = [i for i, v in enumerate(self.fat) if v == FAT_LIBRE]
        if len(libres) < n:
            return None
        return libres[:n]

    def asignar(self, datos):
        """
        Asigna sectores para los datos usando first fit enlazado.
        Retorna el numero del primer sector, o None si no hay espacio.
        """
        if isinstance(datos, str):
            datos = datos.encode('utf-8')

        if not datos:
            datos = b'\x00'

        # cuantos sectores necesitamos (ceil division)
        n = max(1, -(-len(datos) // self.sector_size))

        sectores = self._buscar_libres(n)
        if sectores is None:
            return None     # disco lleno

        # encadenar en la FAT
        for i in range(len(sectores) - 1):
            self.fat[sectores[i]] = sectores[i + 1]
        self.fat[sectores[-1]] = FAT_EOF

        # escribir datos en los sectores
        for i, s in enumerate(sectores):
            chunk = datos[i * self.sector_size:(i + 1) * self.sector_size]
            self.escribir_sector(s, chunk)

        self._guardar_fat()
        return sectores[0]

    def liberar(self, sector_inicio):
        """Libera toda la cadena de sectores de un archivo"""
        actual = sector_inicio
        while actual not in (FAT_EOF, FAT_LIBRE) and actual >= 0:
            siguiente = self.fat[actual]
            self.fat[actual] = FAT_LIBRE
            self.limpiar_sector(actual)
            actual = siguiente
        self._guardar_fat()

    def leer_datos(self, sector_inicio):
        """Lee y concatena los datos de toda la cadena de sectores"""
        datos = b''
        actual = sector_inicio
        visitados = set()   # evitar ciclos corruptos
        while actual not in (FAT_EOF, FAT_LIBRE) and actual >= 0:
            if actual in visitados:
                break
            visitados.add(actual)
            datos += self.leer_sector(actual)
            actual = self.fat[actual]
        return datos

    def reasignar(self, sector_inicio, nuevos_datos):
        """Libera los sectores anteriores y asigna nuevos para los datos"""
        if sector_inicio >= 0:
            self.liberar(sector_inicio)
        return self.asignar(nuevos_datos)

    # ------------------------------------------------------------------
    # Estado del disco
    # ------------------------------------------------------------------

    def sectores_libres(self):
        return sum(1 for v in self.fat if v == FAT_LIBRE)

    def sectores_usados(self):
        return self.sector_count - self.sectores_libres()

    def esta_lleno(self):
        return self.sectores_libres() == 0

    def bytes_libres(self):
        return self.sectores_libres() * self.sector_size

    def bytes_totales(self):
        return self.sector_count * self.sector_size

    def esta_montado(self):
        return self.ruta is not None
