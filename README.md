# File System Simulado — SO-P3

**Curso:** Sistemas Operativos — I Semestre 2026  
**Institución:** Instituto Tecnológico de Costa Rica  
**Profesora:** Ing. Erika Marín Schumann  
**Lenguaje:** Python 3

---

## Requisitos

- Python 3.8 o superior
- Librería `tkinter` (interfaz gráfica)

### Instalar tkinter (si no está disponible)

```bash
# Ubuntu / Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# macOS (si usas Homebrew)
brew install python-tk
```

---

## Cómo ejecutar

```bash
cd SO-P3
python3 main.py
```

Se abrirá la ventana gráfica del simulador.

---

## Estructura del proyecto

```
SO-P3/
├── main.py          # Punto de entrada
├── interfaz.py      # GUI (tkinter)
├── comandos.py      # Parsing y ejecución de comandos
├── filesystem.py    # Lógica del file system (árbol en memoria + disco)
├── disco.py         # Disco virtual: archivo binario, FAT, FIRST FIT
└── modelos.py       # Estructuras de datos: Archivo, Directorio
```

---

## Interfaz gráfica

| Zona | Descripción |
|------|-------------|
| **Barra superior** | Ruta actual del directorio y espacio libre del disco |
| **Panel izquierdo** | Árbol del file system — siempre visible, se actualiza en tiempo real |
| **Panel derecho** | Terminal: salida con colores por tipo de mensaje |
| **Barra inferior** | Campo de entrada del comando + botón **Ejecutar** |

**Atajos de teclado:**
- `Enter` — ejecutar el comando
- `↑` / `↓` — navegar el historial de comandos
- `Tab` — autocompletar nombres de archivos/directorios

---

## Comandos disponibles

### CREATE — Crear disco virtual

```
CREATE <nombre_disco> <num_sectores> <tam_sector_bytes>
```

Crea el archivo binario que representa el disco. Debe ejecutarse antes que cualquier otro comando.

```
CREATE mi_disco.fs 100 512
CREATE disco_pequeño.fs 20 64
```

> El tamaño total del disco será `num_sectores × tam_sector_bytes` bytes.

---

### FILE — Crear archivo

```
FILE <nombre> <extension> [contenido]
```

Crea un archivo en el directorio actual. Si ya existe un archivo con ese nombre, se pregunta si desea **reemplazarlo**.

```
FILE notas txt Hola mundo
FILE reporte doc Este es el contenido del reporte
FILE config ini debug=true port=8080
```

---

### MKDIR — Crear directorio

```
MKDIR <nombre>
```

Crea un directorio en el directorio actual. Si ya existe uno con ese nombre, se pregunta si desea **reemplazarlo** (se vacía el existente).

```
MKDIR documentos
MKDIR fotos
```

---

### CAMBIARDIR / CD — Cambiar directorio

```
CAMBIARDIR <ruta>
CD <ruta>
```

Acepta rutas absolutas, relativas, `..` y `.`.

```
CD documentos           # relativa
CD /documentos/fotos    # absoluta
CD ..                   # subir un nivel
CD /                    # ir a la raíz
```

---

### LISTARDIR / LS — Listar directorio

```
LISTARDIR
LS
```

Lista el contenido del directorio actual diferenciando `[DIR]` de `[ARCHIVO]`, mostrando nombre, tamaño y fecha de modificación.

---

### MODFILE — Modificar archivo

```
MODFILE <nombre.ext> <nuevo contenido>
```

Reemplaza el contenido de un archivo existente.

```
MODFILE notas.txt Este es el nuevo contenido de las notas
```

---

### VERPROPIEDADES — Ver propiedades

```
VERPROPIEDADES <nombre>
```

Muestra: nombre, extensión, tipo, tamaño, fecha de creación y fecha de modificación.

```
VERPROPIEDADES notas.txt
VERPROPIEDADES documentos
```

---

### VERFILE — Ver contenido

```
VERFILE <nombre.ext>
```

Muestra el contenido textual de un archivo.

```
VERFILE notas.txt
VERFILE reporte.doc
```

---

### COPY — Copiar (3 tipos, aplica a archivos y directorios)

```
COPY <origen> <destino>
```

El prefijo `real://` indica una ruta del sistema operativo real. Sin prefijo = ruta virtual del file system.

**Tipo 1 — Real → Virtual**
```
COPY real:///home/usuario/documento.pdf /docs/documento.pdf
COPY real:///home/usuario/carpeta /backup
```

**Tipo 2 — Virtual → Real**
```
COPY /docs/reporte.txt real:///home/usuario/Desktop/reporte.txt
COPY /fotos real:///home/usuario/Desktop/mis_fotos
```

**Tipo 3 — Virtual → Virtual**
```
COPY /docs/notas.txt /backup/notas_copia.txt
COPY /docs /backup_docs
```

> Si el nombre destino ya existe se preguntará si desea reemplazarlo.

---

### MOVER / MV — Mover o renombrar

```
MOVER <origen> <destino>
MV <origen> <destino>
```

Si el destino es un directorio existente, mueve ahí el nodo conservando su nombre.  
Si el destino no existe como directorio, renombra el nodo.  
Acepta rutas con directorios en el origen y destino.

```
MOVER notas.txt notas_v2.txt          # renombrar en mismo directorio
MOVER notas.txt /docs/notas.txt       # mover a otro directorio
MOVER /docs/foto.png /fotos           # mover a directorio existente
MOVER /docs/a.txt /fotos/nuevo.txt    # mover y renombrar a la vez
```

---

### REMOVE / RM — Eliminar

```
REMOVE <nombre> [nombre2 ...] [-r]
RM <nombre> [-r]
```

- Sin `-r`: elimina archivos o directorios vacíos.
- Con `-r`: elimina directorios con todo su contenido (recursivo).

```
REMOVE notas.txt
REMOVE notas.txt reporte.doc
REMOVE documentos -r
```

---

### FIND — Buscar

```
FIND <patron>
```

Busca archivos y directorios en todo el file system cuyo nombre coincida con el patrón. Soporta el comodín `*`.

```
FIND *.txt
FIND reporte*
FIND imagen.png
```

---

### TREE — Ver árbol

```
TREE
```

Muestra el árbol completo del file system. También está **siempre visible** en el panel izquierdo de la interfaz, actualizándose tras cada comando.

---

### ESTADO — Estado del disco

```
ESTADO
```

Muestra estadísticas del disco: sectores totales/usados/libres, tamaño de sector, espacio total/libre y porcentaje de uso con barra visual.

---

### HELP — Ayuda

```
HELP
```

Lista todos los comandos disponibles con su sintaxis.

---

## Disco virtual

El disco se guarda como un **archivo binario** con la siguiente estructura interna:

```
[Encabezado 16 bytes]
  magic(4) + sector_count(4) + sector_size(4) + indice_inicio(4)

[FAT: sector_count × 4 bytes]
  Cada entrada es un int32:
    -2 = sector libre
    -1 = fin de cadena (EOF)
     n = número del siguiente sector en la cadena

[Datos: sector_count × sector_size bytes]
  Contenido crudo de cada sector
```

**Asignación:** FIRST FIT + enlazada (los sectores de un archivo no necesitan ser contiguos).  
**Fragmentación:** interna (último sector puede no llenarse).  
**Persistencia:** el archivo de disco se mantiene al cerrar la aplicación y puede reabrirse para recuperar los datos.

---

## Ejemplo de sesión completa

```
CREATE mi_disco.fs 100 512
MKDIR documentos
MKDIR fotos
CD documentos
FILE informe txt Este es el informe del proyecto
FILE datos csv 1,2,3,4,5
LISTARDIR
VERPROPIEDADES informe.txt
VERFILE informe.txt
MODFILE informe.txt Informe actualizado con nueva información
VERFILE informe.txt
CD ..
COPY /documentos /backup_documentos
MOVER /backup_documentos/datos.csv /fotos/datos_fotos.csv
FIND *.txt
FIND *.csv
TREE
ESTADO
REMOVE /documentos/datos.csv
REMOVE backup_documentos -r
TREE
```
