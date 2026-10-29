# xml2kml.py
# -*- coding: utf-8 -*-
"""
Generación del archivo etapa.kml (planimetría de la etapa) a partir de etapaEsquema.xml

- Lee el archivo XML (con espacio de nombres http://www.uniovi.es) y construye el árbol DOM en memoria.
- Obtiene los datos mediante expresiones XPath.
- Escribe el KML con generación de código basada en plantillas:
      prólogo  ->  chinchetas y línea de la etapa  ->  epílogo

Código de colores de las chinchetas:
    rojo     : salida y meta
    verde    : puertos de montaña
    azul     : sprints intermedios
    amarillo : puntos anónimos (se limitan a un máximo de 30)

NO se utilizan las altitudes: las coordenadas se escriben como longitud,latitud
y el modo de altitud es clampToGround (el punto se pega al terreno).

Uso:  python xml2kml.py [archivoXML] [archivoKML]
      python xml2kml.py etapaEsquema.xml etapa.kml
"""

import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


class Kml(object):
    """Clase que genera las etiquetas de un archivo KML (prólogo, elementos y epílogo)."""

    ESTILOS = {
        # id del estilo : (icono de chincheta de Google Earth, color de la etiqueta)
        'estiloRojo':     'http://maps.google.com/mapfiles/kml/pushpin/red-pushpin.png',
        'estiloVerde':    'http://maps.google.com/mapfiles/kml/pushpin/grn-pushpin.png',
        'estiloAzul':     'http://maps.google.com/mapfiles/kml/pushpin/blue-pushpin.png',
        'estiloAmarillo': 'http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png',
    }

    def __init__(self, archivo, nombre):
        """Constructor: recibe el archivo de salida ya abierto y el nombre del documento KML"""
        self.archivo = archivo
        self.nombre = nombre

    def prologo(self):
        """Escribe el prólogo del archivo KML con la cabecera y los estilos"""
        self.archivo.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.archivo.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
        self.archivo.write('<Document>\n')
        self.archivo.write('<name>' + escape(self.nombre) + '</name>\n')
        for idEstilo, icono in self.ESTILOS.items():
            self.archivo.write('<Style id="' + idEstilo + '">\n')
            self.archivo.write('<IconStyle>\n')
            self.archivo.write('<scale>1.2</scale>\n')
            self.archivo.write('<Icon><href>' + icono + '</href></Icon>\n')
            self.archivo.write('<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>\n')
            self.archivo.write('</IconStyle>\n')
            self.archivo.write('</Style>\n')
        # Estilo de la línea de la etapa (formato KML de color: aabbggrr)
        self.archivo.write('<Style id="lineaEtapa">\n')
        self.archivo.write('<LineStyle>\n')
        self.archivo.write('<color>ff0000ff</color>\n')
        self.archivo.write('<width>4</width>\n')
        self.archivo.write('</LineStyle>\n')
        self.archivo.write('</Style>\n')

    def puntoChincheta(self, nombre, descripcion, longitud, latitud, estilo):
        """Escribe un Placemark de tipo Point (chincheta) con el estilo indicado"""
        self.archivo.write('<Placemark>\n')
        self.archivo.write('<name>' + escape(nombre) + '</name>\n')
        self.archivo.write('<description>' + escape(descripcion) + '</description>\n')
        self.archivo.write('<styleUrl>#' + estilo + '</styleUrl>\n')
        self.archivo.write('<Point>\n')
        self.archivo.write('<coordinates>' + longitud + ',' + latitud + ',0</coordinates>\n')
        self.archivo.write('<altitudeMode>clampToGround</altitudeMode>\n')
        self.archivo.write('</Point>\n')
        self.archivo.write('</Placemark>\n')

    def linea(self, nombre, coordenadas):
        """Escribe un Placemark de tipo LineString con la lista de coordenadas (longitud, latitud)"""
        self.archivo.write('<Placemark>\n')
        self.archivo.write('<name>' + escape(nombre) + '</name>\n')
        self.archivo.write('<styleUrl>#lineaEtapa</styleUrl>\n')
        self.archivo.write('<LineString>\n')
        self.archivo.write('<tessellate>1</tessellate>\n')
        self.archivo.write('<altitudeMode>clampToGround</altitudeMode>\n')
        self.archivo.write('<coordinates>\n')
        for longitud, latitud in coordenadas:
            self.archivo.write(longitud + ',' + latitud + ',0\n')
        self.archivo.write('</coordinates>\n')
        self.archivo.write('</LineString>\n')
        self.archivo.write('</Placemark>\n')

    def epilogo(self):
        """Escribe el epílogo del archivo KML"""
        self.archivo.write('</Document>\n')
        self.archivo.write('</kml>\n')


class Xml2Kml(object):
    """Lee el XML de la etapa, extrae los datos con XPath y genera el archivo KML"""

    ESPACIOS = {'u': 'http://www.uniovi.es'}
    MAX_ANONIMOS = 30

    def __init__(self, archivoXML):
        """Constructor: construye en memoria el árbol DOM del archivo XML"""
        try:
            self.arbol = ET.parse(archivoXML)
        except IOError:
            print('No se encuentra el archivo ', archivoXML)
            sys.exit(1)
        except ET.ParseError:
            print('Error procesando en el archivo XML = ', archivoXML)
            sys.exit(1)
        self.raiz = self.arbol.getroot()

    # ---------- Métodos auxiliares de acceso mediante XPath ----------

    def texto(self, expresionXPath, nodo=None):
        """Devuelve el texto (sin espacios sobrantes) del primer elemento que cumple la expresión XPath"""
        if nodo is None:
            nodo = self.raiz
        elemento = nodo.find(expresionXPath, self.ESPACIOS)
        if elemento is None or elemento.text is None:
            return ''
        return elemento.text.strip()

    def textos(self, expresionXPath, nodo=None):
        """Devuelve la lista de textos (sin espacios sobrantes) de los elementos que cumplen la expresión XPath"""
        if nodo is None:
            nodo = self.raiz
        return [e.text.strip() if e.text else '' for e in nodo.findall(expresionXPath, self.ESPACIOS)]

    # ---------- Extracción de datos ----------

    def obtenerSalidaMeta(self):
        """Devuelve (salida, meta); cada una es una tupla (longitud, latitud)"""
        salida = (self.texto('u:lugares/u:salidaLong'), self.texto('u:lugares/u:salidaLat'))
        meta = (self.texto('u:lugares/u:llegadaLong'), self.texto('u:lugares/u:llegadaLat'))
        return salida, meta

    def obtenerPuertos(self):
        """Devuelve la lista de puertos de montaña como tuplas (nombre, categoría, longitud, latitud, distancia)"""
        puertos = []
        for categoria in self.raiz.findall('u:hitos/u:puertosMontaña/*', self.ESPACIOS):
            nombreCategoria = categoria.tag.split('}')[1]          # p. ej. categoria1
            nombres = self.textos('u:montaña', categoria)
            longitudes = self.textos('u:montañaLong', categoria)
            latitudes = self.textos('u:montañaLat', categoria)
            distancias = self.textos('u:montañadist', categoria)
            for i in range(len(nombres)):
                puertos.append((nombres[i], nombreCategoria, longitudes[i], latitudes[i], distancias[i]))
        return puertos

    def obtenerSprints(self):
        """Devuelve la lista de sprints como tuplas (nombre, longitud, latitud, distancia)"""
        sprints = []
        for sprint in self.raiz.findall('u:hitos/u:Sprints/u:intermedios', self.ESPACIOS):
            sprints.append((self.texto('u:sprint', sprint), self.texto('u:sprintLong', sprint),
                            self.texto('u:sprintLat', sprint), self.texto('u:sprintdist', sprint)))
        return sprints

    def obtenerAnonimos(self):
        """Devuelve los puntos anónimos como tuplas (id, longitud, latitud, distancia), ordenados por distancia
        y limitados a MAX_ANONIMOS puntos (se seleccionan de forma uniforme si hay más)"""
        puntos = []
        for punto in self.raiz.findall('u:puntosAnonimos/u:punto', self.ESPACIOS):
            puntos.append((punto.get('id'), self.texto('u:longitud', punto), self.texto('u:latitud', punto),
                           self.texto('u:distanciaPunto', punto)))
        puntos.sort(key=lambda p: float(p[3]))
        if len(puntos) > self.MAX_ANONIMOS:
            paso = (len(puntos) - 1) / (self.MAX_ANONIMOS - 1)
            puntos = [puntos[round(i * paso)] for i in range(self.MAX_ANONIMOS)]
        return puntos

    # ---------- Generación del KML ----------

    def generarKml(self, archivoKML):
        """Escribe el archivo KML: prólogo, chinchetas, línea de la etapa y epílogo"""
        nombreEtapa = self.texto('u:nombre')
        numero = self.texto('u:numero')
        salida, meta = self.obtenerSalidaMeta()
        puertos = self.obtenerPuertos()
        sprints = self.obtenerSprints()
        anonimos = self.obtenerAnonimos()

        try:
            archivo = open(archivoKML, 'w', encoding='utf-8')
        except IOError:
            print('No se puede crear el archivo ', archivoKML)
            sys.exit(1)

        kml = Kml(archivo, 'Etapa ' + numero + ': ' + nombreEtapa)
        kml.prologo()

        # Salida y meta (rojo)
        kml.puntoChincheta('Salida', self.texto('u:datosCircuito/u:Empieza'), salida[0], salida[1], 'estiloRojo')
        kml.puntoChincheta('Meta', self.texto('u:datosCircuito/u:Acaba'), meta[0], meta[1], 'estiloRojo')

        # Puertos de montaña (verde)
        for nombre, categoria, longitud, latitud, distancia in puertos:
            kml.puntoChincheta(nombre, 'Puerto de montaña (' + categoria + ')', longitud, latitud, 'estiloVerde')

        # Sprints intermedios (azul)
        for nombre, longitud, latitud, distancia in sprints:
            kml.puntoChincheta(nombre, 'Sprint intermedio', longitud, latitud, 'estiloAzul')

        # Puntos anónimos (amarillo)
        for ident, longitud, latitud, distancia in anonimos:
            kml.puntoChincheta('Punto ' + ident, 'Punto anónimo a ' + distancia + ' km de la salida',
                               longitud, latitud, 'estiloAmarillo')

        # Línea de la etapa: salida -> puntos anónimos (por distancia) -> meta
        coordenadas = [salida] + [(p[1], p[2]) for p in anonimos] + [meta]
        kml.linea('Recorrido de la etapa', coordenadas)

        kml.epilogo()
        archivo.close()
        print('Archivo generado: ', archivoKML)


def main():
    """Genera etapa.kml a partir de etapaEsquema.xml (o de los archivos indicados por línea de comandos)"""
    archivoXML = sys.argv[1] if len(sys.argv) > 1 else 'etapaEsquema.xml'
    archivoKML = sys.argv[2] if len(sys.argv) > 2 else 'etapa.kml'
    Xml2Kml(archivoXML).generarKml(archivoKML)


if __name__ == '__main__':
    main()
