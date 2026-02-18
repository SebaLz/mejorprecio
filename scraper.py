import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict
import re
import unicodedata
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException


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
                chrome_options.add_argument('--headless')
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
            except Exception:
                pass
            self.driver = None

    def _slugify_query(self, query: str) -> str:
        """Normaliza query a slug ascii estable para URLs de PreciosGamer."""
        if not query:
            return ""
        normalized = unicodedata.normalize("NFKD", query)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower().strip()
        ascii_text = re.sub(r"[^a-z0-9]+", "_", ascii_text)
        return re.sub(r"_+", "_", ascii_text).strip("_")

    def limpiar_precio(self, precio_str: str) -> float:
        """Convierte un string de precio a numero"""
        if not precio_str:
            return 0.0

        precio_limpio = precio_str.replace('$', '').replace(' ', '').strip()

        if '.' in precio_limpio and ',' in precio_limpio:
            precio_limpio = precio_limpio.replace('.', '').replace(',', '.')
        elif '.' in precio_limpio:
            if precio_limpio.count('.') > 1:
                precio_limpio = precio_limpio.replace('.', '')
        elif ',' in precio_limpio:
            precio_limpio = precio_limpio.replace(',', '.')

        precio_limpio = re.sub(r'[^\d.]', '', precio_limpio)

        try:
            return float(precio_limpio) if precio_limpio else 0.0
        except Exception:
            return 0.0

    def _extract_preciosgamer_from_soup(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extrae resultados de PreciosGamer desde HTML parseado."""
        resultados = []
        if not soup:
            return resultados

        productos = soup.find_all('div', class_=lambda x: x and 'product-b' in str(x))
        if not productos:
            productos = soup.select("article, div[class*='product'], div[data-v-5ed66c8a]")

        for producto in productos[:40]:
            try:
                descripcion_container = (
                    producto.find('div', class_=lambda x: x and 'product-description' in str(x))
                    or producto.find('div', class_=lambda x: x and 'content-container' in str(x))
                    or producto
                )

                nombre_elem = (
                    descripcion_container.find('a', class_=lambda x: x and 'title' in str(x))
                    or descripcion_container.find('a', class_=lambda x: x and 'link-text' in str(x))
                    or descripcion_container.find('h3', class_=lambda x: x and 'title' in str(x).lower())
                    or descripcion_container.find(attrs={'itemprop': 'name'})
                )

                precio_elem = (
                    producto.find('div', class_=lambda x: x and 'current-price' in str(x))
                    or producto.find('div', class_=lambda x: x and 'price-value' in str(x).lower())
                    or producto.find('h2', class_=lambda x: x and 'price' in str(x).lower())
                    or producto.find(attrs={'itemprop': 'price'})
                )

                if not nombre_elem or not precio_elem:
                    continue

                precio_content = precio_elem.get('content', '') if hasattr(precio_elem, 'get') else ''
                precio_texto = precio_elem.get_text(strip=True) if hasattr(precio_elem, 'get_text') else ''
                precio = self.limpiar_precio(precio_content) if precio_content else self.limpiar_precio(precio_texto)
                if precio <= 0:
                    continue

                nombre = nombre_elem.get_text(strip=True)

                tienda_elem = (
                    descripcion_container.find('p', class_=lambda x: x and 'reseller' in str(x).lower())
                    or descripcion_container.find('span', class_=lambda x: x and 'reseller' in str(x).lower())
                )
                tienda = tienda_elem.get_text(strip=True) if tienda_elem else ''

                img_elem = producto.find('img')
                imagen = ''
                if img_elem:
                    imagen = img_elem.get('src', '') or img_elem.get('data-src', '')
                    if imagen and not imagen.startswith('http'):
                        if imagen.startswith('//'):
                            imagen = f"https:{imagen}"
                        elif imagen.startswith('/'):
                            imagen = f"https://preciosgamer.com{imagen}"
                        else:
                            imagen = f"{base_url}/{imagen}"

                link_elem = (
                    producto.find('a', class_=lambda x: x and 'img-container' in str(x))
                    or producto.find('a', href=True)
                )
                link = link_elem.get('href', '') if link_elem else ''
                if link and not link.startswith('http'):
                    if link.startswith('/'):
                        link = f"https://preciosgamer.com{link}"
                    else:
                        link = f"https://preciosgamer.com/{link}"
                if not link:
                    link = base_url

                resultados.append({
                    'nombre': nombre,
                    'precio': precio,
                    'precio_texto': precio_texto if precio_texto else f"${precio:,.0f}".replace(',', '.'),
                    'link': link,
                    'fuente': 'PreciosGamer',
                    'tienda': tienda,
                    'imagen': imagen,
                    'descuento': self._extraer_descuento(producto)
                })
            except Exception:
                continue

        return resultados

    def buscar_preciosgamer(self, query: str) -> List[Dict]:
        """Busca productos en preciosgamer.com con estrategia robusta de fallbacks."""
        resultados = []

        try:
            query_slug = self._slugify_query(query)
            if not query_slug:
                query_slug = query.replace(' ', '_').lower()

            query_encoded = quote_plus(query)
            url = f"https://preciosgamer.com/{query_slug}"
            fallback_url = (
                f"https://preciosgamer.com/{query_slug}"
                f"?changedate=365&order=asc_price&rate=down&search={query_encoded}"
            )

            driver = self._get_driver()
            if driver:
                try:
                    print(f"PreciosGamer: Accediendo a {url} con Selenium...")
                    driver.get(url)

                    deadline = time.time() + 25
                    while time.time() < deadline:
                        cards = driver.find_elements(By.CSS_SELECTOR, "div[class*='product'], article")
                        has_price = False
                        for card in cards[:30]:
                            text = card.text.lower()
                            if ('$' in text or 'precio' in text) and len(text) > 20:
                                has_price = True
                                break
                        if has_price:
                            break
                        driver.execute_script("window.scrollBy(0, 500);")
                        time.sleep(0.5)

                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    resultados = self._extract_preciosgamer_from_soup(soup, url)

                    if not resultados:
                        print(f"PreciosGamer: Sin resultados en slug, probando fallback {fallback_url}")
                        driver.get(fallback_url)
                        time.sleep(2)
                        soup = BeautifulSoup(driver.page_source, 'html.parser')
                        resultados = self._extract_preciosgamer_from_soup(soup, fallback_url)
                except Exception as e:
                    print(f"PreciosGamer: Error con Selenium: {e}")

            if not resultados:
                for candidate in (url, fallback_url):
                    try:
                        print(f"PreciosGamer: Fallback requests para {candidate}...")
                        response = requests.get(candidate, headers=self.headers, timeout=15)
                        if response.status_code != 200:
                            continue
                        soup = BeautifulSoup(response.content, 'html.parser')
                        resultados = self._extract_preciosgamer_from_soup(soup, candidate)
                        if resultados:
                            break
                    except Exception:
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
            url = f"https://www.hardgamers.com.ar/search?text={query.replace(' ', '+')}"
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                productos = soup.find_all('article', class_='product')

                for producto in productos[:20]:
                    try:
                        nombre_elem = producto.find('h3', class_='product-title', itemprop='name')
                        precio_elem = producto.find('h2', class_='product-price', itemprop='price')
                        img_elem = producto.find('img', itemprop='image')
                        link_elem = producto.find('a')

                        if nombre_elem and precio_elem:
                            nombre = nombre_elem.get_text(strip=True)

                            tienda_elem = producto.find('h4', class_='subtitle')
                            tienda = tienda_elem.get_text(strip=True) if tienda_elem else ''

                            imagen = ''
                            if img_elem:
                                imagen = img_elem.get('src', '')
                                if imagen and not imagen.startswith('http'):
                                    if imagen.startswith('//'):
                                        imagen = f"https:{imagen}"
                                    elif imagen.startswith('/'):
                                        imagen = f"https://www.hardgamers.com.ar{imagen}"
                                    else:
                                        base_url = response.url.rsplit('/', 1)[0]
                                        imagen = f"{base_url}/{imagen}"

                            precio_content = precio_elem.get('content', '')
                            precio_texto = precio_elem.get_text(strip=True)

                            if precio_content:
                                precio = self.limpiar_precio(precio_content)
                                precio_texto = f"${precio:,.0f}".replace(',', '.')
                            else:
                                precio = self.limpiar_precio(precio_texto)

                            link = link_elem.get('href', '') if link_elem else ''
                            if not link.startswith('http'):
                                if link.startswith('/'):
                                    link = f"https://www.hardgamers.com.ar{link}"
                                else:
                                    link = f"https://www.hardgamers.com.ar/{link}"

                            if nombre and precio > 0:
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
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error en hardgamers: {e}")

        return resultados

    def _extraer_descuento(self, elemento) -> str:
        """Extrae informaciÃ³n de descuento si existe"""
        try:
            descuento_elem = (
                elemento.find('span', class_=lambda x: x and 'descuento' in x.lower())
                or elemento.find('div', class_=lambda x: x and 'descuento' in x.lower())
                or elemento.find('span', class_=lambda x: x and 'discount' in x.lower())
                or elemento.find('div', class_=lambda x: x and 'discount' in x.lower())
                or elemento.find('span', class_=lambda x: x and 'off' in x.lower())
            )
            if descuento_elem:
                return descuento_elem.get_text(strip=True)

            texto = elemento.get_text()
            descuentos = re.findall(r'\d+%', texto)
            if descuentos:
                return f"{descuentos[0]} OFF"
        except Exception:
            pass
        return ""

    def buscar_todo(self, query: str) -> Dict:
        """Busca en ambas paginas y retorna resultados combinados"""
        resultados = {
            'query': query,
            'preciosgamer': [],
            'hardgamers': [],
            'total': 0
        }

        resultados['preciosgamer'] = self.buscar_preciosgamer(query)
        time.sleep(1)
        resultados['hardgamers'] = self.buscar_hardgamers(query)

        resultados['total'] = len(resultados['preciosgamer']) + len(resultados['hardgamers'])
        return resultados
