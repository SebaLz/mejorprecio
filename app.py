from flask import Flask, render_template, request, jsonify, Response
from scraper import OfertasScraper
import re
import os
from urllib.parse import urljoin
from datetime import date
from price_history import create_history_service, product_fingerprint

app = Flask(__name__)
scraper = OfertasScraper()
history_service = create_history_service()


def get_base_url():
    configured = os.getenv('SITE_URL', '').strip()
    if configured:
        return configured.rstrip('/')
    return request.host_url.rstrip('/')

def normalizar_texto(texto):
    """Normaliza un texto para comparación: lowercase, sin espacios extra, sin caracteres especiales"""
    if not texto:
        return ""
    # Convertir a lowercase
    texto = texto.lower()
    # Remover espacios múltiples
    texto = re.sub(r'\s+', ' ', texto)
    # Remover caracteres especiales pero mantener números y letras
    texto = re.sub(r'[^\w\s]', '', texto)
    return texto.strip()

def normalizar_tienda(tienda):
    """Normaliza el nombre de la tienda para comparación"""
    if not tienda:
        return ""
    tienda = tienda.lower().strip()
    # Normalizar variaciones comunes
    tienda = tienda.replace('full h4rd', 'fullh4rd')
    tienda = tienda.replace('full h4rd', 'fullh4rd')
    tienda = tienda.replace(' ', '')
    return tienda

def son_duplicados(producto1, producto2):
    """Determina si dos productos son duplicados"""
    # Normalizar nombres
    nombre1 = normalizar_texto(producto1.get('nombre', ''))
    nombre2 = normalizar_texto(producto2.get('nombre', ''))
    
    # Normalizar tiendas
    tienda1 = normalizar_tienda(producto1.get('tienda', ''))
    tienda2 = normalizar_tienda(producto2.get('tienda', ''))
    
    # Comparar precios (permitir pequeña diferencia por redondeo)
    precio1 = producto1.get('precio', 0)
    precio2 = producto2.get('precio', 0)
    diferencia_precio = abs(precio1 - precio2)
    porcentaje_diferencia = (diferencia_precio / max(precio1, precio2) * 100) if max(precio1, precio2) > 0 else 0
    
    # Son duplicados si:
    # 1. Los nombres normalizados son muy similares (al menos 80% de similitud)
    # 2. Las tiendas coinciden (o están vacías ambas)
    # 3. Los precios son iguales o muy similares (menos del 1% de diferencia)
    
    # Calcular similitud de nombres (método simple: palabras en común)
    palabras1 = set(nombre1.split())
    palabras2 = set(nombre2.split())
    if palabras1 and palabras2:
        palabras_comunes = len(palabras1.intersection(palabras2))
        palabras_totales = len(palabras1.union(palabras2))
        similitud = (palabras_comunes / palabras_totales * 100) if palabras_totales > 0 else 0
    else:
        similitud = 0
    
    # Verificar si son duplicados
    tiendas_coinciden = (tienda1 == tienda2) or (not tienda1 and not tienda2)
    precios_similares = porcentaje_diferencia < 1.0
    nombres_similares = similitud >= 70  # Al menos 70% de similitud
    
    return nombres_similares and tiendas_coinciden and precios_similares

def eliminar_duplicados(resultados):
    """Elimina productos duplicados de la lista, manteniendo el de mejor formato"""
    if not resultados:
        return resultados
    
    # Ordenar por calidad del nombre (preferir nombres más cortos y sin repeticiones)
    def calidad_nombre(producto):
        nombre = producto.get('nombre', '')
        # Penalizar nombres con repeticiones como "placa de placa"
        if 'placa de placa' in nombre.lower():
            return 1
        # Preferir nombres más cortos
        return len(nombre)
    
    resultados_ordenados = sorted(resultados, key=calidad_nombre)
    resultados_sin_duplicados = []
    productos_vistos = []
    
    for producto in resultados_ordenados:
        es_duplicado = False
        for visto in productos_vistos:
            if son_duplicados(producto, visto):
                es_duplicado = True
                # Si el nuevo producto tiene mejor nombre, reemplazar
                if calidad_nombre(producto) < calidad_nombre(visto):
                    resultados_sin_duplicados.remove(visto)
                    productos_vistos.remove(visto)
                    resultados_sin_duplicados.append(producto)
                    productos_vistos.append(producto)
                break
        
        if not es_duplicado:
            resultados_sin_duplicados.append(producto)
            productos_vistos.append(producto)
    
    return resultados_sin_duplicados


def aplicar_cambios_de_historial(resultados, cambios):
    if not resultados:
        return
    for producto in resultados:
        key = product_fingerprint(producto)
        cambio = cambios.get(key)
        if not cambio:
            continue
        producto["price_change"] = cambio

@app.route('/')
def index():
    base_url = get_base_url()
    page_title = "MejorPrecio | Compara precios de hardware"
    page_description = (
        "Compara precios de componentes de PC en PreciosGamer y HardGamers, "
        "con historial de precios y alertas de bajadas."
    )
    canonical_url = f"{base_url}/"
    og_image = urljoin(f"{base_url}/", "static/og-image.svg")
    structured_data = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "MejorPrecio",
            "url": canonical_url,
            "description": page_description,
            "inLanguage": "es-AR",
            "potentialAction": {
                "@type": "SearchAction",
                "target": f"{canonical_url}?q={{search_term_string}}",
                "query-input": "required name=search_term_string",
            },
        },
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "MejorPrecio",
            "applicationCategory": "ShoppingApplication",
            "operatingSystem": "Web",
            "url": canonical_url,
            "description": page_description,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        },
    ]
    return render_template(
        'index.html',
        page_title=page_title,
        page_description=page_description,
        canonical_url=canonical_url,
        site_name='MejorPrecio',
        og_image=og_image,
        structured_data=structured_data,
    )

@app.route('/buscar', methods=['POST'])
def buscar():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'La búsqueda no puede estar vacía'}), 400
        
        resultados = scraper.buscar_todo(query)
        
        # Eliminar duplicados de cada fuente
        resultados['preciosgamer'] = eliminar_duplicados(resultados['preciosgamer'])
        resultados['hardgamers'] = eliminar_duplicados(resultados['hardgamers'])
        
        # Combinar y eliminar duplicados entre fuentes
        todos_resultados = resultados['preciosgamer'] + resultados['hardgamers']
        todos_resultados = eliminar_duplicados(todos_resultados)
        
        # Ordenar todos los resultados por precio
        todos_resultados.sort(key=lambda x: x['precio'] if x['precio'] > 0 else float('inf'))

        snapshot = history_service.record_snapshot(query, todos_resultados)
        cambios = snapshot.get("changes", {})
        aplicar_cambios_de_historial(todos_resultados, cambios)
        aplicar_cambios_de_historial(resultados['preciosgamer'], cambios)
        aplicar_cambios_de_historial(resultados['hardgamers'], cambios)

        resultados['todos'] = todos_resultados
        resultados['total'] = len(todos_resultados)
        resultados['historial'] = {
            'guardado': snapshot.get('saved', False),
            'backend': snapshot.get('backend'),
            'capturado_en': snapshot.get('captured_at')
        }
        
        return jsonify(resultados)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/buscar/preciosgamer', methods=['POST'])
def buscar_preciosgamer_retry():
    try:
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'La busqueda no puede estar vacia'}), 400

        resultados_pg = scraper.buscar_preciosgamer(query)
        resultados_pg = eliminar_duplicados(resultados_pg)
        resultados_pg.sort(key=lambda x: x['precio'] if x['precio'] > 0 else float('inf'))

        return jsonify({
            'query': query,
            'preciosgamer': resultados_pg,
            'total': len(resultados_pg)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/historial', methods=['GET'])
def historial():
    try:
        query = request.args.get('query', '').strip()
        limit = request.args.get('limit', 20, type=int)
        data = history_service.get_history(query=query if query else None, limit=limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/robots.txt', methods=['GET'])
def robots():
    base_url = get_base_url()
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /buscar\n"
        "Disallow: /historial\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )
    return Response(body, mimetype='text/plain')


@app.route('/sitemap.xml', methods=['GET'])
def sitemap():
    base_url = get_base_url()
    today = date.today().isoformat()
    urls = [
        f"{base_url}/",
    ]
    xml_items = []
    for url in urls:
        xml_items.append(
            "<url>"
            f"<loc>{url}</loc>"
            f"<lastmod>{today}</lastmod>"
            "<changefreq>daily</changefreq>"
            "<priority>1.0</priority>"
            "</url>"
        )
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        f"{''.join(xml_items)}"
        "</urlset>"
    )
    return Response(xml, mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
