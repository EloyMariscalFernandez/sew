# xml2altimetria.py
# -*- coding: utf-8 -*-
"""
Generación del archivo altimetria.svg (perfil altimétrico de la etapa) a partir de etapaEsquema.xml

- Lee el archivo XML (con espacio de nombres http://www.uniovi.es) y construye el árbol DOM en memoria.
- Obtiene las distancias y altitudes mediante expresiones XPath.
- Escribe el SVG con generación de código basada en plantillas:
      prólogo  ->  ejes, perfil (polilínea) y marcas de los hitos  ->  epílogo

El perfil es una polilínea cuyos vértices son los puntos de la etapa (salida, puntos anónimos,
puertos de montaña, sprints y meta) ordenados por distancia. La polilínea se cierra por abajo
para rellenar el perfil ("efecto suelo").

Colores de las marcas (igual que en el KML):
    rojo  : salida y meta
    verde : puertos de montaña
    azul  : sprints intermedios

Uso:  python xml2altimetria.py [archivoXML] [archivoSVG]
      python xml2altimetria.py etapaEsquema.xml altimetria.svg
"""

import math
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


class Svg(object):
    """Clase que genera las etiquetas de un archivo SVG (prólogo, elementos gráficos y epílogo)."""

    def __init__(self, archivo, ancho, alto):
        """Constructor: recibe el archivo de salida ya abierto y las dimensiones del dibujo"""
        self.archivo = archivo
        self.ancho = ancho
        self.alto = alto

    def prologo(self):
        """Escribe el prólogo del archivo SVG"""
        self.archivo.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.archivo.write('<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
                           'width="' + str(self.ancho) + '" height="' + str(self.alto) + '" '
                           'viewBox="0 0 ' + str(self.ancho) + ' ' + str(self.alto) + '" '
                           'font-family="Arial, Helvetica, sans-serif">\n')
        self.archivo.write('<rect x="0" y="0" width="' + str(self.ancho) + '" height="' + str(self.alto) +
                           '" fill="#ffffff"/>\n')

    def linea(self, x1, y1, x2, y2, color='#000000', grosor=1, discontinua=False):
        """Escribe una línea recta"""
        estilo = ' stroke-dasharray="4,4"' if discontinua else ''
        self.archivo.write('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s"%s/>\n'
                           % (x1, y1, x2, y2, color, grosor, estilo))

    def polilinea(self, puntos, relleno='none', trazo='none', grosor=1):
        """Escribe una polilínea a partir de una lista de vértices (x, y)"""
        lista = ' '.join('%.1f,%.1f' % (x, y) for x, y in puntos)
        self.archivo.write('<polyline points="%s" fill="%s" stroke="%s" stroke-width="%s" '
                           'stroke-linejoin="round"/>\n' % (lista, relleno, trazo, grosor))

    def circulo(self, cx, cy, radio, relleno, trazo='#ffffff'):
        """Escribe un círculo"""
        self.archivo.write('<circle cx="%.1f" cy="%.1f" r="%s" fill="%s" stroke="%s" stroke-width="1.5"/>\n'
                           % (cx, cy, radio, relleno, trazo))

    def rectangulo(self, x, y, ancho, alto, relleno):
        """Escribe un rectángulo"""
        self.archivo.write('<rect x="%.1f" y="%.1f" width="%s" height="%s" fill="%s"/>\n'
                           % (x, y, ancho, alto, relleno))

    def texto(self, x, y, contenido, tam=12, color='#333333', ancla='start', rotacion=0, negrita=False):
        """Escribe un texto; si rotacion != 0 el texto se gira (grados) alrededor de su punto (x, y)"""
        giro = ' transform="rotate(%s %.1f %.1f)"' % (rotacion, x, y) if rotacion else ''
        peso = ' font-weight="bold"' if negrita else ''
        self.archivo.write('<text x="%.1f" y="%.1f" font-size="%s" fill="%s" text-anchor="%s"%s%s>%s</text>\n'
                           % (x, y, tam, color, ancla, peso, giro, escape(contenido)))

    def epilogo(self):
        """Escribe el epílogo del archivo SVG"""
        self.archivo.write('</svg>\n')


class Xml2Altimetria(object):
    """Lee el XML de la etapa, extrae distancias y altitudes con XPath y genera el perfil en SVG"""

    ESPACIOS = {'u': 'http://www.uniovi.es'}

    # Colores
    COLOR_PERFIL = '#1f4e79'
    COLOR_RELLENO = '#c9d9ec'
    COLOR_SALIDA_META = '#d62728'
    COLOR_PUERTO = '#2ca02c'
    COLOR_SPRINT = '#1f77ff'

    # Dimensiones del dibujo y márgenes
    ANCHO, ALTO = 1200, 640
    MARGEN_IZQ, MARGEN_DER, MARGEN_SUP, MARGEN_INF = 85, 35, 95, 75

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

    @staticmethod
    def convertirAltitud(cadena):
        """Convierte una altitud a metros. En el XML las altitudes de salida, meta y hitos se han escrito
        con el punto como separador de miles (1.014 = 1014 m, 2.409 = 2409 m); los puntos anónimos
        ya vienen en metros (1260.000). Ninguna altitud de la etapa es menor de 10 m."""
        valor = float(cadena)
        return valor * 1000 if valor < 10 else valor

    # ---------- Extracción de datos ----------

    def obtenerDistanciaTotal(self):
        """Devuelve la distancia total de la etapa en km"""
        return float(self.texto('u:datosCircuito/u:distancia'))

    def obtenerVertices(self):
        """Devuelve la lista de vértices del perfil como tuplas (distancia km, altitud m, tipo, nombre),
        ordenada por distancia. Los hitos con una distancia fuera de la etapa se descartan con un aviso."""
        total = self.obtenerDistanciaTotal()
        vertices = []

        # Salida y meta
        vertices.append((0.0, self.convertirAltitud(self.texto('u:lugares/u:salidaAlt')), 'salida', 'Salida'))
        vertices.append((total, self.convertirAltitud(self.texto('u:lugares/u:llegadaAlt')), 'meta', 'Meta'))

        # Puntos anónimos
        for punto in self.raiz.findall('u:puntosAnonimos/u:punto', self.ESPACIOS):
            vertices.append((float(self.texto('u:distanciaPunto', punto)),
                             self.convertirAltitud(self.texto('u:altitud', punto)),
                             'anonimo', 'Punto ' + punto.get('id')))

        # Puertos de montaña (las distancias están en km aunque el atributo diga "m")
        hitos = []
        for categoria in self.raiz.findall('u:hitos/u:puertosMontaña/*', self.ESPACIOS):
            nombres = self.textos('u:montaña', categoria)
            altitudes = self.textos('u:montañaAlt', categoria)
            distancias = self.textos('u:montañadist', categoria)
            for i in range(len(nombres)):
                hitos.append((float(distancias[i]), self.convertirAltitud(altitudes[i]), 'puerto', nombres[i]))

        # Sprints intermedios
        for sprint in self.raiz.findall('u:hitos/u:Sprints/u:intermedios', self.ESPACIOS):
            hitos.append((float(self.texto('u:sprintdist', sprint)),
                          self.convertirAltitud(self.texto('u:sprintAlt', sprint)),
                          'sprint', self.texto('u:sprint', sprint)))

        for hito in hitos:
            if 0 <= hito[0] <= total:
                vertices.append(hito)
            else:
                print('AVISO: "%s" tiene una distancia (%s) fuera de la etapa (0-%s km); no se dibuja en el perfil.'
                      % (hito[3], hito[0], total))

        vertices.sort(key=lambda v: v[0])
        return vertices

    # ---------- Cálculo de escalas ----------

    @staticmethod
    def redondear(valor, paso, hacia):
        """Redondea 'valor' al múltiplo de 'paso' inferior (hacia='abajo') o superior (hacia='arriba')"""
        if hacia == 'abajo':
            return math.floor(valor / paso) * paso
        return math.ceil(valor / paso) * paso

    # ---------- Generación del SVG ----------

    def generarSvg(self, archivoSVG):
        """Escribe el archivo SVG: prólogo, ejes, perfil, marcas de hitos y epílogo"""
        total = self.obtenerDistanciaTotal()
        vertices = self.obtenerVertices()

        altitudes = [v[1] for v in vertices]
        altMin = self.redondear(min(altitudes) - 50, 500, 'abajo')
        altMax = self.redondear(max(altitudes) + 450, 500, 'arriba')   # hueco arriba para las etiquetas

        izq, der = self.MARGEN_IZQ, self.ANCHO - self.MARGEN_DER
        sup, inf = self.MARGEN_SUP, self.ALTO - self.MARGEN_INF

        def px(distancia):
            return izq + (distancia / total) * (der - izq)

        def py(altitud):
            return inf - ((altitud - altMin) / (altMax - altMin)) * (inf - sup)

        try:
            archivo = open(archivoSVG, 'w', encoding='utf-8')
        except IOError:
            print('No se puede crear el archivo ', archivoSVG)
            sys.exit(1)

        svg = Svg(archivo, self.ANCHO, self.ALTO)
        svg.prologo()

        # Título
        titulo = 'Etapa ' + self.texto('u:numero') + ': ' + self.texto('u:nombre')
        subtitulo = ('Perfil altimétrico · ' + self.texto('u:datosCircuito/u:distancia') + ' km · desnivel '
                     + self.texto('u:datosCircuito/u:desnivel') + ' m')
        svg.texto(self.ANCHO / 2, 34, titulo, tam=22, color='#111111', ancla='middle', negrita=True)
        svg.texto(self.ANCHO / 2, 58, subtitulo, tam=14, color='#555555', ancla='middle')

        # Rejilla y escala vertical (cada 500 m)
        altitud = altMin
        while altitud <= altMax:
            y = py(altitud)
            svg.linea(izq, y, der, y, color='#dddddd', grosor=1)
            svg.texto(izq - 10, y + 4, '%d' % altitud, tam=12, ancla='end')
            altitud += 500

        # Rejilla y escala horizontal (cada 10 km)
        distancia = 0
        while distancia <= total:
            x = px(distancia)
            svg.linea(x, sup, x, inf, color='#eeeeee', grosor=1)
            svg.texto(x, inf + 20, '%d' % distancia, tam=12, ancla='middle')
            distancia += 10

        # Perfil: polilínea cerrada por abajo (relleno) y polilínea abierta (línea del perfil)
        perfil = [(px(v[0]), py(v[1])) for v in vertices]
        suelo = perfil + [(perfil[-1][0], inf), (perfil[0][0], inf), perfil[0]]
        svg.polilinea(suelo, relleno=self.COLOR_RELLENO, trazo='none')
        svg.polilinea(perfil, relleno='none', trazo=self.COLOR_PERFIL, grosor=2.5)

        # Ejes
        svg.linea(izq, sup, izq, inf, color='#000000', grosor=1.5)
        svg.linea(izq, inf, der, inf, color='#000000', grosor=1.5)
        svg.texto((izq + der) / 2, inf + 50, 'Distancia (km)', tam=14, ancla='middle')
        svg.texto(24, (sup + inf) / 2, 'Altitud (m)', tam=14, ancla='middle', rotacion=-90)

        # Marcas de salida/meta, puertos y sprints
        colores = {'salida': self.COLOR_SALIDA_META, 'meta': self.COLOR_SALIDA_META,
                   'puerto': self.COLOR_PUERTO, 'sprint': self.COLOR_SPRINT}
        for distancia, altitud, tipo, nombre in vertices:
            if tipo in colores:
                x, y = px(distancia), py(altitud)
                if tipo in ('puerto', 'sprint'):
                    svg.linea(x, y, x, sup, color=colores[tipo], grosor=1, discontinua=True)
                    svg.texto(x + 4, y - 12, '%s (%d m)' % (nombre, altitud), tam=12,
                              color=colores[tipo], rotacion=-90, negrita=True)
                svg.circulo(x, y, 5.5, colores[tipo])

        # Leyenda
        x = izq
        for color, etiqueta in ((self.COLOR_SALIDA_META, 'Salida / Meta'),
                                (self.COLOR_PUERTO, 'Puerto de montaña'),
                                (self.COLOR_SPRINT, 'Sprint intermedio')):
            svg.circulo(x + 6, 78, 5.5, color)
            svg.texto(x + 16, 82, etiqueta, tam=12)
            x += 170

        svg.epilogo()
        archivo.close()
        print('Archivo generado: ', archivoSVG)


def main():
    """Genera altimetria.svg a partir de etapaEsquema.xml (o de los archivos indicados por línea de comandos)"""
    archivoXML = sys.argv[1] if len(sys.argv) > 1 else 'etapaEsquema.xml'
    archivoSVG = sys.argv[2] if len(sys.argv) > 2 else 'altimetria.svg'
    Xml2Altimetria(archivoXML).generarSvg(archivoSVG)


if __name__ == '__main__':
    main()
