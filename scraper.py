import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

class OfertasScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
        }
        self.driver = None
    
    def _get_driver(self):
        """Obtiene o crea un driver de Selenium"""
        if self.driver is None:
            try:
                chrome_options = Options()
                chrome_options.add_argument('--headless')  # Ejecutar en modo sin ventana
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument(f'user-agent={self.headers["User-Agent"]}')
                
                self.driver = webdriver.Chrome(options=chrome_options)
            except Exception as e:
                print(f"Error al crear driver de Selenium: {e}")
                print("Intentando sin Selenium...")
                return None
        return self.driver
    
    def _close_driver(self):
        """Cierra el driver de Selenium"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def limpiar_precio(self, precio_str: str) -> float:
        """Convierte un string de precio a número"""
        if not precio_str:
            return 0.0
        
        # Remover símbolos de moneda y espacios
        precio_limpio = precio_str.replace('$', '').replace(' ', '').strip()
        
        # Formato argentino: puntos como separadores de miles, coma como decimal
        # Ejemplo: "1.563.890" o "1.563.890,50"
        if '.' in precio_limpio and ',' in precio_limpio:
            # Tiene ambos: punto es miles, coma es decimal
            precio_limpio = precio_limpio.replace('.', '').replace(',', '.')
        elif '.' in precio_limpio:
            # Solo punto: puede ser miles o decimal
            # Si tiene más de un punto, son miles
            if precio_limpio.count('.') > 1:
                precio_limpio = precio_limpio.replace('.', '')
            # Si tiene un punto, asumimos que es decimal
        elif ',' in precio_limpio:
            # Solo coma: es decimal
            precio_limpio = precio_limpio.replace(',', '.')
        
        # Remover cualquier carácter no numérico excepto punto
        precio_limpio = re.sub(r'[^\d.]', '', precio_limpio)
        
        try:
            return float(precio_limpio) if precio_limpio else 0.0
        except:
            return 0.0
    
    def buscar_preciosgamer(self, query: str) -> List[Dict]:
        """Busca productos en preciosgamer.com usando Selenium para contenido dinámico"""
        resultados = []
        driver = None
        
        try:
            # PreciosGamer usa formato de slug en la URL: "rtx 5070 ti" -> "rtx_5070_ti"
            query_slug = query.replace(' ', '_').lower()
            url = f"https://preciosgamer.com/{query_slug}"
            
            # Intentar con Selenium primero (para contenido dinámico)
            driver = self._get_driver()
            if driver:
                try:
                    print(f"PreciosGamer: Accediendo a {url} con Selenium...")
                    driver.get(url)
                    
                    # Esperar a que al menos un producto con precio esté visible (la página carga estructura antes que los datos)
                    def productos_con_precio_visibles(driver):
                        try:
                            cards = driver.find_elements(By.CSS_SELECTOR, "div[class*='product-b']")
                            for card in cards:
                                try:
                                    card.find_element(By.CSS_SELECTOR, "[class*='current-price']")
                                    return True
                                except Exception:
                                    continue
                            return False
                        except Exception:
                            return False
                    
                    try:
                        WebDriverWait(driver, 20).until(productos_con_precio_visibles)
                        time.sleep(3)  # Dar tiempo extra a que se rendericen todos los precios/nombres
                    except TimeoutException:
                        # Si no aparecieron productos con precio, esperar al menos la estructura y un poco más
                        try:
                            WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='product-b']"))
                            )
                            time.sleep(4)
                        except TimeoutException:
                            print("PreciosGamer: Timeout esperando productos, continuando...")
                    
                    # Obtener el HTML después de que JavaScript se ejecute
                    html = driver.page_source
                    soup = BeautifulSoup(html, 'html.parser')
                    base_url = url
                    
                except Exception as e:
                    print(f"PreciosGamer: Error con Selenium: {e}")
                    # Fallback a requests
                    response = requests.get(url, headers=self.headers, timeout=15)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        base_url = url
                    else:
                        return resultados
            else:
                # Fallback a requests si Selenium no está disponible
                print(f"PreciosGamer: Usando requests (sin Selenium) para {url}...")
                response = requests.get(url, headers=self.headers, timeout=15)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    base_url = url
                else:
                    return resultados
            
            if soup:
                # Buscar productos - PreciosGamer usa div con clase "product-b" (puede tener atributos data-v-*)
                # Intentar múltiples formas de encontrar los productos
                productos = []
                
                # Método 1: Buscar por clase que contenga "product-b"
                productos = soup.find_all('div', class_=lambda x: x and 'product-b' in str(x))
                
                # Método 2: Si no encuentra, buscar por atributos data-v-* que suelen tener los componentes Vue
                if not productos:
                    productos = soup.find_all('div', attrs={'data-v-5ed66c8a': True})
                
                # Método 3: Buscar cualquier div que tenga "product" en sus clases
                if not productos:
                    all_divs = soup.find_all('div', class_=True)
                    productos = [div for div in all_divs if any('product' in str(c).lower() for c in div.get('class', []))]
                
                print(f"PreciosGamer: Total de productos encontrados: {len(productos)}")
                
                for producto in productos[:20]:  # Limitar a 20 resultados
                    try:
                        # Buscar el contenedor de descripción - puede tener diferentes variaciones
                        descripcion_container = (producto.find('div', class_=lambda x: x and 'product-description' in str(x)) or
                                                producto.find('div', class_=lambda x: x and 'content-container' in str(x)))
                        
                        # Buscar nombre - está en un <a> con clase "title" o "link-text"
                        nombre_elem = None
                        if descripcion_container:
                            nombre_elem = (descripcion_container.find('a', class_=lambda x: x and 'title' in str(x)) or
                                         descripcion_container.find('a', class_=lambda x: x and 'link-text' in str(x)))
                        
                        # Si no está en el contenedor, buscar directamente en el producto
                        if not nombre_elem:
                            nombre_elem = (producto.find('a', class_=lambda x: x and 'title' in str(x)) or
                                         producto.find('a', class_=lambda x: x and 'link-text' in str(x)))
                        
                        # Buscar precio - está en un div con clase "current-price" o dentro de "prices"
                        precio_elem = (producto.find('div', class_=lambda x: x and 'current-price' in str(x)) or
                                     producto.find('div', class_=lambda x: x and 'price' in str(x).lower()))
                        
                        # Si no encuentra, buscar en el contenedor de precios
                        if not precio_elem:
                            prices_container = producto.find('div', class_=lambda x: x and 'prices' in str(x))
                            if prices_container:
                                precio_elem = prices_container.find('div', class_=lambda x: x and 'current-price' in str(x))
                        
                        # Buscar imagen - está en un <img> dentro de un <a> con clase "img-container"
                        img_elem = None
                        img_container = producto.find('a', class_=lambda x: x and 'img-container' in x)
                        if img_container:
                            img_elem = img_container.find('img')
                        
                        # Buscar link - puede estar en el img-container o en el título
                        link_elem = producto.find('a', class_=lambda x: x and 'img-container' in x)
                        if not link_elem and nombre_elem:
                            link_elem = nombre_elem
                        
                        if nombre_elem and precio_elem:
                            nombre = nombre_elem.get_text(strip=True)
                            precio_texto = precio_elem.get_text(strip=True)
                            precio = self.limpiar_precio(precio_texto)
                            
                            # Buscar nombre de la tienda - está en un <p> con clase "reseller"
                            tienda_elem = None
                            if descripcion_container:
                                tienda_elem = descripcion_container.find('p', class_=lambda x: x and 'reseller' in x)
                            
                            tienda = ''
                            if tienda_elem:
                                tienda = tienda_elem.get_text(strip=True)
                            
                            # Extraer URL de la imagen
                            imagen = ''
                            if img_elem:
                                imagen = img_elem.get('src', '')
                                # Si la imagen es relativa, convertirla a absoluta
                                if imagen and not imagen.startswith('http'):
                                    if imagen.startswith('//'):
                                        imagen = f"https:{imagen}"
                                    elif imagen.startswith('/'):
                                        imagen = f"https://preciosgamer.com{imagen}"
                                    else:
                                        # URL relativa, usar base URL
                                        imagen = f"{base_url}/{imagen}"
                            
                            link = ''
                            if link_elem:
                                link = link_elem.get('href', '')
                            
                            if not link.startswith('http'):
                                if link.startswith('/'):
                                    link = f"https://preciosgamer.com{link}"
                                else:
                                    link = f"https://preciosgamer.com/{link}"
                            
                            if nombre and precio > 0:  # Solo agregar si tiene precio válido
                                resultados.append({
                                    'nombre': nombre,
                                    'precio': precio,
                                    'precio_texto': precio_texto,
                                    'link': link,
                                    'fuente': 'PreciosGamer',
                                    'tienda': tienda,
                                    'imagen': imagen,
                                    'descuento': self._extraer_descuento(producto)
                                })
                    except Exception as e:
                        continue
        except Exception as e:
            print(f"Error en preciosgamer: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"PreciosGamer: Retornando {len(resultados)} resultados")
        return resultados
    
    def buscar_hardgamers(self, query: str) -> List[Dict]:
        """Busca productos en hardgamers.com.ar"""
        resultados = []
        try:
            # URL de búsqueda - HardGamers usa /search?text=
            url = f"https://www.hardgamers.com.ar/search?text={query.replace(' ', '+')}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Buscar productos - HardGamers usa <article> con clase "product"
                productos = soup.find_all('article', class_='product')
                
                for producto in productos[:20]:  # Limitar a 20 resultados
                    try:
                        # Buscar nombre - está en <h3> con clase "product-title" y itemprop="name"
                        nombre_elem = producto.find('h3', class_='product-title', itemprop='name')
                        
                        # Buscar precio - está en <h2> con clase "product-price" y itemprop="price"
                        # El precio numérico está en el atributo "content"
                        precio_elem = producto.find('h2', class_='product-price', itemprop='price')
                        
                        # Buscar imagen - está en <img> con itemprop="image" dentro de product-image
                        img_elem = producto.find('img', itemprop='image')
                        
                        # Buscar link - puede estar en varios lugares
                        link_elem = producto.find('a')
                        
                        if nombre_elem and precio_elem:
                            nombre = nombre_elem.get_text(strip=True)
                            
                            # Buscar nombre de la tienda - está en un <h4> con clase "subtitle"
                            tienda_elem = producto.find('h4', class_='subtitle')
                            tienda = ''
                            if tienda_elem:
                                tienda = tienda_elem.get_text(strip=True)
                            
                            # Extraer URL de la imagen
                            imagen = ''
                            if img_elem:
                                imagen = img_elem.get('src', '')
                                # Si la imagen es relativa, convertirla a absoluta
                                if imagen and not imagen.startswith('http'):
                                    if imagen.startswith('//'):
                                        imagen = f"https:{imagen}"
                                    elif imagen.startswith('/'):
                                        imagen = f"https://www.hardgamers.com.ar{imagen}"
                                    else:
                                        # URL relativa, usar base URL
                                        base_url = response.url.rsplit('/', 1)[0]
                                        imagen = f"{base_url}/{imagen}"
                            
                            # El precio puede estar en el atributo content o en el texto
                            precio_content = precio_elem.get('content', '')
                            precio_texto = precio_elem.get_text(strip=True)
                            
                            # Priorizar el atributo content si existe
                            if precio_content:
                                precio = self.limpiar_precio(precio_content)
                                precio_texto = f"${precio:,.0f}".replace(',', '.')
                            else:
                                precio = self.limpiar_precio(precio_texto)
                            
                            link = ''
                            if link_elem:
                                link = link_elem.get('href', '')
                            
                            if not link.startswith('http'):
                                if link.startswith('/'):
                                    link = f"https://www.hardgamers.com.ar{link}"
                                else:
                                    link = f"https://www.hardgamers.com.ar/{link}"
                            
                            if nombre and precio > 0:  # Solo agregar si tiene precio válido
                                resultados.append({
                                    'nombre': nombre,
                                    'precio': precio,
                                    'precio_texto': precio_texto,
                                    'link': link,
                                    'fuente': 'HardGamers',
                                    'tienda': tienda,
                                    'imagen': imagen,
                                    'descuento': self._extraer_descuento(producto)
                                })
                    except Exception as e:
                        continue
        except Exception as e:
            print(f"Error en hardgamers: {e}")
        
        return resultados
    
    def _extraer_descuento(self, elemento) -> str:
        """Extrae información de descuento si existe"""
        try:
            descuento_elem = (elemento.find('span', class_=lambda x: x and 'descuento' in x.lower()) or
                             elemento.find('div', class_=lambda x: x and 'descuento' in x.lower()) or
                             elemento.find('span', class_=lambda x: x and 'discount' in x.lower()) or
                             elemento.find('div', class_=lambda x: x and 'discount' in x.lower()) or
                             elemento.find('span', class_=lambda x: x and 'off' in x.lower()))
            if descuento_elem:
                return descuento_elem.get_text(strip=True)
            
            # Buscar porcentajes de descuento en el texto
            texto = elemento.get_text()
            descuentos = re.findall(r'\d+%', texto)
            if descuentos:
                return f"{descuentos[0]} OFF"
        except:
            pass
        return ""
    
    def buscar_todo(self, query: str) -> Dict:
        """Busca en ambas páginas y retorna resultados combinados"""
        resultados = {
            'query': query,
            'preciosgamer': [],
            'hardgamers': [],
            'total': 0
        }
        
        # Buscar en paralelo (simulado con llamadas secuenciales)
        resultados['preciosgamer'] = self.buscar_preciosgamer(query)
        time.sleep(1)  # Pausa para no sobrecargar los servidores
        resultados['hardgamers'] = self.buscar_hardgamers(query)
        
        resultados['total'] = len(resultados['preciosgamer']) + len(resultados['hardgamers'])
        
        return resultados
