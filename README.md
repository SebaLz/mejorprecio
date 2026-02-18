# Buscador de Ofertas Gaming

Aplicacion web que agrega resultados de busqueda de ofertas desde PreciosGamer y HardGamers.

## Instalacion

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Ejecutar la aplicacion:
```bash
python app.py
```

3. Abrir en el navegador:
```
http://localhost:5000
```

## Uso

- Ingresa un termino de busqueda (ej: "RTX 3060", "Ryzen 5", "SSD")
- Los resultados se muestran de ambas fuentes
- Puedes filtrar por fuente usando las pestanas
- Los resultados estan ordenados por precio

## Historial de precios (sin base de datos externa)

El proyecto guarda historial de precios con dos backends:

- `local` (default): guarda en `data/price_history.json` (util para desarrollo local).
- `github`: guarda el JSON en un archivo del repositorio usando la API de GitHub (compatible con Vercel Serverless).

### Variables de entorno

- `PRICE_HISTORY_BACKEND`: `local` o `github`.
- `PRICE_HISTORY_FILE`: ruta local del JSON (solo modo `local`).
- `PRICE_HISTORY_MAX_PRODUCTS`: maximo de productos persistidos.
- `PRICE_HISTORY_MAX_POINTS`: maximo de puntos por producto.

Para modo `github`:

- `GITHUB_TOKEN`: token con permisos de contenido sobre el repo.
- `GITHUB_REPO`: formato `owner/repo`.
- `GITHUB_BRANCH`: rama destino (default `main`).
- `GITHUB_HISTORY_PATH`: archivo JSON a actualizar (default `data/price_history.json`).

### Endpoints nuevos

- `POST /buscar`: ademas de resultados, agrega `historial` y `price_change` por producto.
- `GET /historial?query=rtx&limit=20`: devuelve items guardados y su serie historica.

## Alertas en frontend

- Boton con estrella (`Alertar`) junto al buscador para seguir una busqueda.
- Barra en home con estado de alertas y boton `Chequear alertas ahora`.
- Apartado `Alertas` que muestra:
- Busquedas seguidas.
- Bajadas detectadas en productos dentro del top 15 mas barato.
- Las alertas se guardan en `localStorage` del navegador.

## Notas

- Los selectores CSS en `scraper.py` pueden necesitar ajustes segun cambios en las paginas.
- Se recomienda usar proxies o rate limiting para evitar bloqueos.
- Considera usar Selenium si las paginas cargan contenido dinamico con JavaScript.

## Estructura del proyecto

```text
Test/
|-- app.py
|-- price_history.py
|-- scraper.py
|-- requirements.txt
|-- templates/
|   `-- index.html
|-- static/
|   |-- css/
|   |   `-- style.css
|   `-- js/
|       `-- main.js
`-- README.md
```
