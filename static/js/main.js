document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const alertToggleBtn = document.getElementById('alertToggleBtn');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const error = document.getElementById('error');
    const errorText = document.getElementById('errorText');
    const searchHistory = document.getElementById('searchHistory');
    const historyList = document.getElementById('historyList');
    const clearHistoryBtn = document.getElementById('clearHistory');
    const alertsSection = document.getElementById('alertsSection');
    const watchedQueriesEl = document.getElementById('watchedQueries');
    const alertsListEl = document.getElementById('alertsList');
    const clearAlertsBtn = document.getElementById('clearAlerts');
    const homeAlertsCountEl = document.getElementById('homeAlertsCount');
    const homeAlertsStatusEl = document.getElementById('homeAlertsStatus');
    const checkAlertsBtn = document.getElementById('checkAlertsBtn');
    const retryPreciosgamerBtn = document.getElementById('retryPreciosgamerBtn');

    let currentData = null;
    let currentView = 'grid';
    let priceMin = null;
    let priceMax = null;

    const MAX_HISTORY_ITEMS = 10;
    const MAX_STORED_ALERTS = 100;
    const ALERT_QUERIES_KEY = 'alertQueries';
    const PRICE_ALERTS_KEY = 'priceAlerts';
    const ALERTS_LAST_CHECK_KEY = 'alertsLastCheck';

    // Cargar estado inicial
    cargarHistorial();
    renderAlertQueries();
    renderPriceAlerts();
    actualizarBotonAlerta();
    actualizarEstadoAlertasHome();

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            buscar();
        }
    });

    searchInput.addEventListener('input', actualizarBotonAlerta);
    searchBtn.addEventListener('click', buscar);
    alertToggleBtn.addEventListener('click', toggleAlertaBusquedaActual);

    searchInput.addEventListener('focus', mostrarHistorial);
    searchInput.addEventListener('blur', () => {
        setTimeout(() => ocultarHistorial(), 200);
    });

    clearHistoryBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        limpiarHistorialCompleto();
    });

    clearAlertsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm('Estas seguro de limpiar las alertas detectadas?')) {
            localStorage.removeItem(PRICE_ALERTS_KEY);
            renderPriceAlerts();
            actualizarEstadoAlertasHome();
        }
    });

    checkAlertsBtn.addEventListener('click', chequearAlertasAhora);
    retryPreciosgamerBtn.addEventListener('click', reintentarPreciosgamer);

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            activarTab(btn.dataset.tab);
        });
    });

    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            cambiarVista(btn.dataset.view);
        });
    });

    const applyFiltersBtn = document.getElementById('applyFilters');
    const clearFiltersBtn = document.getElementById('clearFilters');
    const priceMinSlider = document.getElementById('priceMinSlider');
    const priceMaxSlider = document.getElementById('priceMaxSlider');
    const priceMinValueEl = document.getElementById('priceMinValue');
    const priceMaxValueEl = document.getElementById('priceMaxValue');
    const sortSelect = document.getElementById('sortSelect');

    let priceRangeMin = 0;
    let priceRangeMax = 100;

    applyFiltersBtn.addEventListener('click', aplicarFiltros);
    clearFiltersBtn.addEventListener('click', limpiarFiltros);
    priceMinSlider.addEventListener('input', actualizarValoresSlider);
    priceMaxSlider.addEventListener('input', actualizarValoresSlider);
    sortSelect.addEventListener('change', () => {
        if (currentData) mostrarResultados(currentData, { resetSliders: false });
    });

    watchedQueriesEl.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.alert-query-remove');
        const runBtn = e.target.closest('.alert-query-run');

        if (removeBtn) {
            const query = decodeURIComponent(removeBtn.dataset.query || '');
            quitarQueryAlerta(query);
            return;
        }

        if (runBtn) {
            const query = decodeURIComponent(runBtn.dataset.query || '');
            searchInput.value = query;
            actualizarBotonAlerta();
            buscar();
        }
    });

    alertsListEl.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.alert-item-remove');
        if (!removeBtn) return;

        const alertId = removeBtn.dataset.alertId;
        const alerts = obtenerPriceAlerts().filter(item => item.id !== alertId);
        guardarPriceAlerts(alerts);
        renderPriceAlerts();
    });

    function cambiarVista(view) {
        currentView = view;

        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.view === view) {
                btn.classList.add('active');
            }
        });

        document.querySelectorAll('.products-container').forEach(container => {
            container.classList.remove('grid-view', 'list-view');
            container.classList.add(`${view}-view`);
        });
    }

    function precioDesdeSlider(sliderValue) {
        return priceRangeMin + (priceRangeMax - priceRangeMin) * (parseFloat(sliderValue) / 100);
    }

    function actualizarValoresSlider() {
        let minVal = parseFloat(priceMinSlider.value);
        let maxVal = parseFloat(priceMaxSlider.value);
        if (minVal > maxVal) {
            priceMinSlider.value = maxVal;
            priceMaxSlider.value = minVal;
            minVal = parseFloat(priceMinSlider.value);
            maxVal = parseFloat(priceMaxSlider.value);
        }
        priceMinValueEl.textContent = formatPriceShort(precioDesdeSlider(minVal));
        priceMaxValueEl.textContent = formatPriceShort(precioDesdeSlider(maxVal));
    }

    function formatPriceShort(val) {
        if (val === 0 || isNaN(val)) return '0';
        if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
        if (val >= 1000) return (val / 1000).toFixed(0) + 'k';
        return Math.round(val).toString();
    }

    function aplicarFiltros() {
        priceMin = precioDesdeSlider(priceMinSlider.value);
        priceMax = precioDesdeSlider(priceMaxSlider.value);
        if (priceMin <= priceRangeMin) priceMin = null;
        if (priceMax >= priceRangeMax) priceMax = null;

        if (currentData) {
            mostrarResultados(currentData, { resetSliders: false });
        }
    }

    function limpiarFiltros() {
        priceMinSlider.value = 0;
        priceMaxSlider.value = 100;
        priceMin = null;
        priceMax = null;
        actualizarValoresSlider();
        if (currentData) {
            mostrarResultados(currentData, { resetSliders: false });
        }
    }

    function ordenarProductos(productos, orden) {
        const list = [...productos];
        if (orden === 'price_asc') {
            list.sort((a, b) => (a.precio || 0) - (b.precio || 0));
        } else if (orden === 'price_desc') {
            list.sort((a, b) => (b.precio || 0) - (a.precio || 0));
        } else if (orden === 'best_deal') {
            list.sort((a, b) => {
                const hasDescA = a.descuento && String(a.descuento).length > 0 ? 1 : 0;
                const hasDescB = b.descuento && String(b.descuento).length > 0 ? 1 : 0;
                if (hasDescB !== hasDescA) return hasDescB - hasDescA;
                return (a.precio || 0) - (b.precio || 0);
            });
        }
        return list;
    }

    function filtrarProductos(productos) {
        if (!priceMin && !priceMax) {
            return productos;
        }

        return productos.filter(producto => {
            const precio = producto.precio;

            if (priceMin != null && precio < priceMin) {
                return false;
            }

            if (priceMax != null && precio > priceMax) {
                return false;
            }

            return true;
        });
    }

    function buscar() {
        const query = searchInput.value.trim();

        if (!query) {
            mostrarError('Por favor ingresa un termino de busqueda');
            return;
        }

        guardarEnHistorial(query);
        ocultarHistorial();

        loading.classList.remove('hidden');
        results.classList.add('hidden');
        error.classList.add('hidden');

        fetch('/buscar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        })
            .then(response => response.json())
            .then(data => {
                loading.classList.add('hidden');

                if (data.error) {
                    mostrarError(data.error);
                    return;
                }

                currentData = data;
                mostrarResultados(data, { resetSliders: true });
                procesarAlertasDeBajada(query, data);
                actualizarBotonAlerta();
            })
            .catch(err => {
                loading.classList.add('hidden');
                mostrarError('Error al buscar. Intenta nuevamente.');
                console.error(err);
            });
    }

    async function reintentarPreciosgamer() {
        const query = searchInput.value.trim() || (currentData && currentData.query) || '';
        if (!query) {
            mostrarError('Primero realiza una busqueda para poder reintentar PreciosGamer.');
            return;
        }

        setRetryPreciosgamerBusy(true, 'Reintentando...');
        error.classList.add('hidden');

        try {
            const resp = await fetch('/buscar/preciosgamer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const data = await resp.json();
            if (data.error) {
                mostrarError(data.error);
                return;
            }

            if (!currentData || !currentData.hardgamers) {
                currentData = {
                    query,
                    preciosgamer: data.preciosgamer || [],
                    hardgamers: [],
                    todos: data.preciosgamer || [],
                    total: (data.preciosgamer || []).length
                };
            } else {
                currentData.query = query;
                currentData.preciosgamer = data.preciosgamer || [];
                const merged = [...(currentData.preciosgamer || []), ...(currentData.hardgamers || [])];
                merged.sort((a, b) => (a.precio || 0) - (b.precio || 0));
                currentData.todos = merged;
                currentData.total = merged.length;
            }

            mostrarResultados(currentData, { resetSliders: false, activeTab: 'preciosgamer' });
        } catch (err) {
            mostrarError('No se pudo reintentar PreciosGamer. Intenta nuevamente.');
            console.error(err);
        } finally {
            setRetryPreciosgamerBusy(false, 'Reintentar PreciosGamer');
        }
    }

    function setRetryPreciosgamerBusy(isBusy, label) {
        retryPreciosgamerBtn.disabled = isBusy;
        retryPreciosgamerBtn.querySelector('span').textContent = label;
    }

    async function chequearAlertasAhora() {
        const watched = obtenerAlertQueries();
        if (watched.length === 0) {
            mostrarError('No hay busquedas seguidas. Marca una con la estrella para activar alertas.');
            return;
        }

        setCheckAlertsBusy(true, 'Chequeando...');
        error.classList.add('hidden');

        let nuevas = 0;
        for (const item of watched) {
            try {
                const resp = await fetch('/buscar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: item.query })
                });
                const data = await resp.json();
                if (data && !data.error) {
                    nuevas += procesarAlertasDeBajada(item.query, data);
                }
            } catch (_e) {
                // Continúa con la siguiente query aunque una falle.
            }
        }

        localStorage.setItem(ALERTS_LAST_CHECK_KEY, String(Date.now()));
        actualizarEstadoAlertasHome(nuevas);
        setCheckAlertsBusy(false, 'Chequear alertas ahora');
    }

    function setCheckAlertsBusy(isBusy, label) {
        checkAlertsBtn.disabled = isBusy;
        checkAlertsBtn.querySelector('span').textContent = label;
    }

    function mostrarResultados(data, opts = {}) {
        results.classList.remove('hidden');
        const resetSliders = opts.resetSliders === true;

        const todos = data.todos || [];
        if (todos.length > 0 && resetSliders) {
            const precios = todos.map(p => p.precio).filter(p => p != null && p > 0);
            priceRangeMin = precios.length ? Math.floor(Math.min(...precios)) : 0;
            priceRangeMax = precios.length ? Math.ceil(Math.max(...precios)) : priceRangeMin + 1;
            if (priceRangeMax <= priceRangeMin) priceRangeMax = priceRangeMin + 1;
            priceMinSlider.value = 0;
            priceMaxSlider.value = 100;
            actualizarValoresSlider();
        }

        const productosFiltrados = filtrarProductos(todos);
        const totalFiltrado = productosFiltrados.length;
        const totalOriginal = data.total || 0;

        if (priceMin != null || priceMax != null) {
            document.getElementById('statsText').textContent =
                `Mostrando ${totalFiltrado} de ${totalOriginal} resultados para "${data.query}"`;
        } else {
            document.getElementById('statsText').textContent =
                `Se encontraron ${totalOriginal} resultados para "${data.query}"`;
        }

        const orden = sortSelect.value;
        const preciosgamerFiltrados = ordenarProductos(filtrarProductos(data.preciosgamer || []), orden);
        const hardgamersFiltrados = ordenarProductos(filtrarProductos(data.hardgamers || []), orden);
        const todosFiltrados = ordenarProductos(productosFiltrados, orden);

        mostrarProductos('todosResults', todosFiltrados);
        mostrarProductos('preciosgamerResults', preciosgamerFiltrados);
        mostrarProductos('hardgamersResults', hardgamersFiltrados);

        activarTab(opts.activeTab || 'todos');
    }

    function mostrarProductos(containerId, productos) {
        const container = document.getElementById(containerId);

        if (productos.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No se encontraron productos</p></div>';
            return;
        }

        container.innerHTML = productos.map((producto, index) => `
            <div class="product-card" style="animation-delay: ${index * 0.05}s">
                ${producto.imagen ? `
                    <div class="product-image-container">
                        <img src="${producto.imagen}" alt="${escapeHtml(producto.nombre)}" class="product-image" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'200\' height=\'200\'%3E%3Crect fill=\'%23ddd\' width=\'200\' height=\'200\'/%3E%3Ctext fill=\'%23999\' font-family=\'sans-serif\' font-size=\'14\' dy=\'10.5\' font-weight=\'bold\' x=\'50%25\' y=\'50%25\' text-anchor=\'middle\'%3ESin imagen%3C/text%3E%3C/svg%3E';">
                    </div>
                ` : ''}
                <div class="product-card-body">
                    <div class="product-name">${escapeHtml(producto.nombre)}</div>
                    ${renderPriceChange(producto)}
                    ${producto.descuento ? `<div class="product-descuento">${escapeHtml(producto.descuento)}</div>` : ''}
                    <div class="product-info">
                        <div class="product-source">${escapeHtml(producto.fuente)}</div>
                        ${producto.tienda ? `<div class="product-store"><i class="fas fa-store"></i> ${escapeHtml(producto.tienda)}</div>` : ''}
                    </div>
                </div>
                <div class="product-price-block">
                    <div class="product-price">$${formatearPrecio(producto.precio)}</div>
                </div>
                <a href="${producto.link}" target="_blank" class="product-link">
                    <i class="fas fa-external-link-alt"></i>
                    <span>Ver oferta</span>
                </a>
            </div>
        `).join('');
    }

    function renderPriceChange(producto) {
        const change = producto.price_change;
        if (!change || change.previous_price == null) {
            return '';
        }

        const delta = Number(change.delta || 0);
        const pct = Number(change.delta_pct || 0);

        if (delta < 0) {
            return `<div class="price-change down"><i class="fas fa-arrow-down"></i> Bajo $${formatearPrecio(Math.abs(delta))} (${Math.abs(pct).toFixed(2)}%)</div>`;
        }

        if (delta > 0) {
            return `<div class="price-change up"><i class="fas fa-arrow-up"></i> Subio $${formatearPrecio(Math.abs(delta))} (${Math.abs(pct).toFixed(2)}%)</div>`;
        }

        return '<div class="price-change flat"><i class="fas fa-minus"></i> Sin cambios</div>';
    }

    function procesarAlertasDeBajada(query, data) {
        if (!query || !estaSiguiendoQuery(query)) {
            renderAlertsSection();
            return 0;
        }

        const top15 = (data.todos || [])
            .filter(p => (p.precio || 0) > 0)
            .sort((a, b) => (a.precio || 0) - (b.precio || 0))
            .slice(0, 15);

        const nuevos = [];
        top15.forEach(producto => {
            const change = producto.price_change;
            if (!change || change.previous_price == null) return;
            if (Number(change.delta || 0) >= 0) return;

            const capturedAt = (data.historial && data.historial.capturado_en) || 'sin-fecha';
            const baseKey = `${query}|${producto.link || producto.nombre}|${capturedAt}`;
            const id = hashString(baseKey);

            nuevos.push({
                id,
                timestamp: Date.now(),
                query,
                nombre: producto.nombre,
                tienda: producto.tienda || '',
                fuente: producto.fuente || '',
                precioAnterior: Number(change.previous_price || 0),
                precioActual: Number(change.current_price || producto.precio || 0),
                delta: Number(change.delta || 0),
                deltaPct: Number(change.delta_pct || 0),
                link: producto.link || ''
            });
        });

        if (nuevos.length === 0) {
            renderAlertsSection();
            return 0;
        }

        const actuales = obtenerPriceAlerts();
        const existentes = new Set(actuales.map(item => item.id));
        const agregados = nuevos.filter(item => !existentes.has(item.id));

        if (agregados.length > 0) {
            const merged = [...agregados, ...actuales].slice(0, MAX_STORED_ALERTS);
            guardarPriceAlerts(merged);
        }

        renderPriceAlerts();
        actualizarEstadoAlertasHome();
        return agregados.length;
    }

    function formatearPrecio(precio) {
        if (precio === 0 || Number.isNaN(precio)) return 'N/A';
        return Number(precio).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    function mostrarError(mensaje) {
        errorText.textContent = mensaje;
        error.classList.remove('hidden');
    }

    function activarTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        const btn = document.querySelector(`[data-tab="${tabName}"]`);
        const content = document.getElementById(tabName);

        if (btn) btn.classList.add('active');
        if (content) content.classList.add('active');
    }

    function guardarEnHistorial(query) {
        let historial = obtenerHistorial();
        historial = historial.filter(item => item.query.toLowerCase() !== query.toLowerCase());

        historial.unshift({
            query,
            timestamp: Date.now()
        });

        historial = historial.slice(0, MAX_HISTORY_ITEMS);
        localStorage.setItem('searchHistory', JSON.stringify(historial));
        mostrarHistorial();
    }

    function obtenerHistorial() {
        try {
            const historial = localStorage.getItem('searchHistory');
            return historial ? JSON.parse(historial) : [];
        } catch (_e) {
            return [];
        }
    }

    function cargarHistorial() {
        const historial = obtenerHistorial();
        if (historial.length > 0) {
            mostrarHistorial();
        }
    }

    function mostrarHistorial() {
        const historial = obtenerHistorial();

        if (historial.length === 0) {
            historyList.innerHTML = '<div class="history-empty">No hay busquedas recientes</div>';
        } else {
            historyList.innerHTML = historial.map((item, index) => {
                const tiempo = formatearTiempo(item.timestamp);
                const encodedQuery = encodeURIComponent(item.query);
                return `
                    <div class="history-item" data-query="${escapeHtml(item.query)}">
                        <div class="history-item-content" onclick="seleccionarBusqueda(decodeURIComponent('${encodedQuery}'))">
                            <i class="fas fa-history history-item-icon"></i>
                            <span class="history-item-text">${escapeHtml(item.query)}</span>
                            <span class="history-item-time">${tiempo}</span>
                        </div>
                        <button class="history-item-remove" onclick="eliminarDelHistorial(${index}, event)" title="Eliminar">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                `;
            }).join('');
        }

        searchHistory.classList.remove('hidden');
    }

    function ocultarHistorial() {
        searchHistory.classList.add('hidden');
    }

    function seleccionarBusqueda(query) {
        searchInput.value = query;
        actualizarBotonAlerta();
        buscar();
    }

    function eliminarDelHistorial(index, event) {
        event.stopPropagation();
        const historial = obtenerHistorial();
        historial.splice(index, 1);
        localStorage.setItem('searchHistory', JSON.stringify(historial));
        mostrarHistorial();
    }

    function limpiarHistorialCompleto() {
        if (confirm('Estas seguro de que quieres limpiar todo el historial?')) {
            localStorage.removeItem('searchHistory');
            ocultarHistorial();
        }
    }

    function formatearTiempo(timestamp) {
        const ahora = Date.now();
        const diferencia = ahora - timestamp;
        const minutos = Math.floor(diferencia / 60000);
        const horas = Math.floor(diferencia / 3600000);
        const dias = Math.floor(diferencia / 86400000);

        if (minutos < 1) return 'Ahora';
        if (minutos < 60) return `${minutos}m`;
        if (horas < 24) return `${horas}h`;
        return `${dias}d`;
    }

    function actualizarEstadoAlertasHome(nuevasDetectadas = 0) {
        const alerts = obtenerPriceAlerts();
        const watchedCount = obtenerAlertQueries().length;
        const total = alerts.length;
        const lastCheckRaw = localStorage.getItem(ALERTS_LAST_CHECK_KEY);
        const lastCheck = lastCheckRaw ? Number(lastCheckRaw) : null;

        homeAlertsCountEl.textContent = `${total} alertas activas`;

        if (nuevasDetectadas > 0) {
            homeAlertsStatusEl.textContent = `Se detectaron ${nuevasDetectadas} bajas nuevas. Seguimientos activos: ${watchedCount}.`;
            return;
        }

        if (total > 0) {
            homeAlertsStatusEl.textContent = `Hay bajas detectadas listas para revisar. Seguimientos activos: ${watchedCount}.`;
            return;
        }

        if (lastCheck) {
            homeAlertsStatusEl.textContent = `Ultimo chequeo: ${formatearTiempo(lastCheck)}. Sin bajadas detectadas.`;
            return;
        }

        homeAlertsStatusEl.textContent = 'Todavia no se detectaron bajadas.';
    }

    function obtenerAlertQueries() {
        try {
            const raw = localStorage.getItem(ALERT_QUERIES_KEY);
            const list = raw ? JSON.parse(raw) : [];
            return Array.isArray(list) ? list : [];
        } catch (_e) {
            return [];
        }
    }

    function guardarAlertQueries(queries) {
        localStorage.setItem(ALERT_QUERIES_KEY, JSON.stringify(queries));
    }

    function estaSiguiendoQuery(query) {
        return obtenerAlertQueries().some(item => item.query.toLowerCase() === query.toLowerCase());
    }

    function toggleAlertaBusquedaActual() {
        const query = searchInput.value.trim();
        if (!query) {
            mostrarError('Primero escribe una busqueda para agregarla a alertas.');
            return;
        }

        let queries = obtenerAlertQueries();
        const idx = queries.findIndex(item => item.query.toLowerCase() === query.toLowerCase());

        if (idx >= 0) {
            queries.splice(idx, 1);
        } else {
            queries.unshift({ query, createdAt: Date.now() });
        }

        guardarAlertQueries(queries);
        renderAlertQueries();
        actualizarBotonAlerta();

        if (currentData && currentData.query && currentData.query.toLowerCase() === query.toLowerCase()) {
            procesarAlertasDeBajada(query, currentData);
        }
    }

    function quitarQueryAlerta(query) {
        const queries = obtenerAlertQueries().filter(item => item.query.toLowerCase() !== query.toLowerCase());
        guardarAlertQueries(queries);
        renderAlertQueries();
        actualizarBotonAlerta();
    }

    function renderAlertQueries() {
        const queries = obtenerAlertQueries();

        if (queries.length === 0) {
            watchedQueriesEl.innerHTML = '<div class="history-empty">No hay busquedas en seguimiento</div>';
            renderAlertsSection();
            actualizarEstadoAlertasHome();
            return;
        }

        watchedQueriesEl.innerHTML = queries.map(item => `
            <div class="alert-query-item">
                <div class="alert-query-text">
                    <i class="fas fa-star"></i>
                    <span>${escapeHtml(item.query)}</span>
                </div>
                <div class="alert-query-actions">
                    <button class="alert-query-run" data-query="${encodeURIComponent(item.query)}" title="Buscar ahora">
                        <i class="fas fa-search"></i>
                    </button>
                    <button class="alert-query-remove" data-query="${encodeURIComponent(item.query)}" title="Quitar seguimiento">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `).join('');

        renderAlertsSection();
        actualizarEstadoAlertasHome();
    }

    function actualizarBotonAlerta() {
        const query = searchInput.value.trim();
        const isTracking = query && estaSiguiendoQuery(query);

        alertToggleBtn.classList.toggle('active', Boolean(isTracking));
        alertToggleBtn.querySelector('span').textContent = isTracking ? 'Siguiendo' : 'Alertar';

        const icon = alertToggleBtn.querySelector('i');
        icon.className = isTracking ? 'fas fa-star' : 'fa-regular fa-star';
    }

    function obtenerPriceAlerts() {
        try {
            const raw = localStorage.getItem(PRICE_ALERTS_KEY);
            const list = raw ? JSON.parse(raw) : [];
            return Array.isArray(list) ? list : [];
        } catch (_e) {
            return [];
        }
    }

    function guardarPriceAlerts(alerts) {
        localStorage.setItem(PRICE_ALERTS_KEY, JSON.stringify(alerts));
    }

    function renderPriceAlerts() {
        const alerts = obtenerPriceAlerts();

        if (alerts.length === 0) {
            alertsListEl.innerHTML = '<div class="history-empty">Sin alertas por ahora</div>';
            renderAlertsSection();
            actualizarEstadoAlertasHome();
            return;
        }

        alertsListEl.innerHTML = alerts.map(alert => `
            <div class="alert-item">
                <div class="alert-item-main">
                    <div class="alert-item-title">${escapeHtml(alert.nombre)}</div>
                    <div class="alert-item-meta">
                        <span><i class="fas fa-filter"></i> ${escapeHtml(alert.query)}</span>
                        <span><i class="fas fa-store"></i> ${escapeHtml(alert.tienda || alert.fuente || 'Tienda')}</span>
                        <span><i class="fas fa-clock"></i> ${formatearTiempo(alert.timestamp)}</span>
                    </div>
                    <div class="alert-item-prices">
                        <span class="old-price">$${formatearPrecio(alert.precioAnterior)}</span>
                        <span class="new-price">$${formatearPrecio(alert.precioActual)}</span>
                        <span class="drop-pill"><i class="fas fa-arrow-down"></i> $${formatearPrecio(Math.abs(alert.delta))} (${Math.abs(alert.deltaPct).toFixed(2)}%)</span>
                    </div>
                </div>
                <div class="alert-item-actions">
                    ${alert.link ? `<a href="${alert.link}" target="_blank" class="alert-item-link" title="Ver oferta"><i class="fas fa-external-link-alt"></i></a>` : ''}
                    <button class="alert-item-remove" data-alert-id="${alert.id}" title="Eliminar alerta">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `).join('');

        renderAlertsSection();
        actualizarEstadoAlertasHome();
    }

    function renderAlertsSection() {
        const hasQueries = obtenerAlertQueries().length > 0;
        const hasAlerts = obtenerPriceAlerts().length > 0;
        alertsSection.classList.toggle('hidden', !(hasQueries || hasAlerts));
    }

    function hashString(value) {
        let h = 0;
        for (let i = 0; i < value.length; i += 1) {
            h = Math.imul(31, h) + value.charCodeAt(i) | 0;
        }
        return `a${Math.abs(h)}`;
    }

    window.seleccionarBusqueda = seleccionarBusqueda;
    window.eliminarDelHistorial = eliminarDelHistorial;
});
