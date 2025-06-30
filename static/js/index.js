class MonitoringApp {
    constructor() {
        // Configuración de la API
        this.apiBaseUrl = 'http://127.0.0.1:8000';
        this.currentSection = 'home';
        // Referencias a elementos del DOM
        this.elements = {};
        // Estado de la aplicación
        this.appState = {
            isConnected: false,
            lastUpdate: null,
            autoUpdateInterval: null,
            retryCount: 0,
            maxRetries: 3
        };
        console.log('🚀 Aplicación de Monitoreo Iniciada');
    }

    /**
     * MÉTODO DE INICIALIZACIÓN
     * Se ejecuta cuando la página se carga completamente
     */
    async init() {
        try {
            console.log('📋 Inicializando aplicación...');
            // 1. Configurar referencias del DOM
            this.setupDOMReferences();
            // 2. Configurar eventos
            this.setupEventListeners();
            // 3. Verificar conexión con el servidor
            await this.checkServerConnection();
            // 4. Inicializar componentes
            await this.initializeComponents();
            // 5. Cargar datos iniciales
            await this.loadInitialData();
            // 6. Iniciar actualizaciones automáticas
            this.startAutoUpdate();
            console.log('✅ Aplicación inicializada correctamente');
        } catch (error) {
            console.error('❌ Error al inicializar la aplicación:', error);
            this.showAlert('Error al inicializar la aplicación', 'danger');
        }
    }

    /**
     * VERIFICAR CONEXIÓN CON EL SERVIDOR
     * Verifica si el servidor Python está disponible
     */
    async checkServerConnection() {
        console.log('🔌 Verificando conexión con el servidor...');
        try {
            const response = await this.makeApiRequest('/health', 'GET');
            if (response.ok) {
                this.appState.isConnected = true;
                this.appState.retryCount = 0;
                console.log('✅ Conexión con servidor establecida');
                this.showConnectionStatus(true);
            }
        } catch (error) {
            console.warn('⚠️ No se pudo conectar con el servidor:', error);
            this.appState.isConnected = false;
            this.showConnectionStatus(false);
        }
    }

    /**
     * REALIZAR PETICIÓN A LA API
     * Método centralizado para hacer peticiones HTTP al servidor Python
     */
    async makeApiRequest(endpoint, method = 'GET', data = null) {
        const url = `${this.apiBaseUrl}${endpoint}`;
        
        console.log(`📡 ${method} ${url}`, data ? data : '');
        
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        };

        // Añadir datos para POST/PUT
        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            
            // Log de la respuesta
            console.log(`📡 Respuesta ${response.status}:`, response.statusText);
            
            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status} - ${response.statusText}`);
            }

            const responseData = await response.json();
            console.log('📦 Datos recibidos:', responseData);
            
            return {
                ok: true,
                data: responseData,
                status: response.status
            };
            
        } catch (error) {
            console.error('❌ Error en petición API:', error);
            throw error;
        }
    }

    /**
     * CARGAR DATOS EN TIEMPO REAL
     * Obtiene los datos más recientes del servidor
     */
    async loadRealTimeData() {
        console.log('📊 Cargando datos en tiempo real...');
        
        if (!this.appState.isConnected) {
            console.log('⚠️ Sin conexión, intentando reconectar...');
            await this.checkServerConnection();
            if (!this.appState.isConnected) {
                return;
            }
        }

        try {
            // Obtener datos ambientales más recientes
            const response = await this.makeApiRequest('/api/datos/recientes', 'GET');
            
            if (response.ok && response.data) {
                this.updateStatistics(response.data);
                this.appState.retryCount = 0;
                console.log('✅ Datos actualizados correctamente');
            }
            
        } catch (error) {
            console.error('❌ Error al cargar datos:', error);
            this.handleConnectionError();
        }
    }

    /**
     * GUARDAR DATOS DE MONITOREO
     * Envía nuevos datos de monitoreo al servidor
     */
    async saveMonitoring() {
        console.log('💾 Guardando datos de monitoreo...');
        
        if (!this.appState.isConnected) {
            this.showAlert('Sin conexión con el servidor', 'warning');
            return;
        }

        try {
            // Recopilar datos del formulario
            const monitoringData = this.getFormData();
            
            // Validar datos
            if (!this.validateFormData(monitoringData)) {
                this.showAlert('Por favor completa todos los campos requeridos', 'warning');
                return;
            }

            // Enviar datos al servidor
            const response = await this.makeApiRequest('/api/monitoreo', 'POST', monitoringData);
            
            if (response.ok) {
                this.showAlert('Datos guardados correctamente', 'success');
                this.clearForm();
                // Actualizar datos en tiempo real
                await this.loadRealTimeData();
            }
            
        } catch (error) {
            console.error('❌ Error al guardar datos:', error);
            this.showAlert('Error al guardar los datos', 'danger');
        }
    }

    /**
     * OBTENER DATOS DEL FORMULARIO
     * Extrae los datos del formulario de monitoreo
     */
    getFormData() {
        const formData = {
            temperatura: parseFloat(this.elements.temperatureInput?.value) || null,
            humedad: parseFloat(this.elements.humidityInput?.value) || null,
            observaciones: this.elements.observationsTextarea?.value || '',
            tipo_medicion: this.elements.measurementTypeSelect?.value || 'manual',
            timestamp: new Date().toISOString()
        };
        
        console.log('📝 Datos del formulario:', formData);
        return formData;
    }

    /**
     * VALIDAR DATOS DEL FORMULARIO
     * Valida que los datos sean correctos antes de enviar
     */
    validateFormData(data) {
        // Validaciones básicas
        if (!data.temperatura || data.temperatura < -50 || data.temperatura > 100) {
            console.warn('⚠️ Temperatura inválida');
            return false;
        }
        
        if (!data.humedad || data.humedad < 0 || data.humedad > 100) {
            console.warn('⚠️ Humedad inválida');
            return false;
        }
        
        return true;
    }

    /**
     * LIMPIAR FORMULARIO
     * Limpia todos los campos del formulario
     */
    clearForm() {
        if (this.elements.temperatureInput) this.elements.temperatureInput.value = '';
        if (this.elements.humidityInput) this.elements.humidityInput.value = '';
        if (this.elements.observationsTextarea) this.elements.observationsTextarea.value = '';
        if (this.elements.measurementTypeSelect) this.elements.measurementTypeSelect.selectedIndex = 0;
    }

    /**
     * OBTENER HISTORIAL DE DATOS
     * Obtiene datos históricos para reportes
     */
    async getHistoricalData(dateFrom, dateTo, limit = 100) {
        console.log('📈 Obteniendo datos históricos...');
        
        try {
            const params = new URLSearchParams({
                fecha_inicio: dateFrom,
                fecha_fin: dateTo,
                limite: limit
            });
            
            const response = await this.makeApiRequest(`/api/datos/historial?${params}`, 'GET');
            
            if (response.ok) {
                console.log('✅ Datos históricos obtenidos');
                return response.data;
            }
            
        } catch (error) {
            console.error('❌ Error al obtener datos históricos:', error);
            this.showAlert('Error al cargar datos históricos', 'danger');
            return [];
        }
    }

    /**
     * MANEJAR ERRORES DE CONEXIÓN
     * Gestiona los errores de conexión con reintentos
     */
    handleConnectionError() {
        this.appState.retryCount++;
        
        if (this.appState.retryCount <= this.appState.maxRetries) {
            console.log(`🔄 Reintentando conexión (${this.appState.retryCount}/${this.appState.maxRetries})...`);
            
            setTimeout(async () => {
                await this.checkServerConnection();
            }, 5000); // Reintentar en 5 segundos
            
        } else {
            console.log('❌ Máximo de reintentos alcanzado, usando datos mock');
            this.appState.isConnected = false;
            this.showConnectionStatus(false);
            this.loadMockData();
        }
    }

    /**
     * MOSTRAR ESTADO DE CONEXIÓN
     * Actualiza la interfaz con el estado de conexión
     */
    showConnectionStatus(isConnected) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            if (isConnected) {
                statusElement.innerHTML = '<i class="fas fa-wifi text-success"></i> Conectado';
                statusElement.className = 'badge bg-success';
            } else {
                statusElement.innerHTML = '<i class="fas fa-wifi-slash text-danger"></i> Desconectado';
                statusElement.className = 'badge bg-danger';
            }
        }
    }

    /**
     * CREAR GRÁFICO AMBIENTAL
     * Crea un gráfico con datos ambientales
     */
    async createEnvironmentalChart() {
        console.log('📊 Creando gráfico ambiental...');
        
        if (!this.elements.environmentalChart) {
            console.warn('⚠️ Elemento de gráfico no encontrado');
            return;
        }

        try {
            // Obtener datos para el gráfico
            const chartData = await this.getChartData();
            
            // Configurar el gráfico (ejemplo con Chart.js)
            const ctx = this.elements.environmentalChart.getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: 'Temperatura (°C)',
                        data: chartData.temperature,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.1
                    }, {
                        label: 'Humedad (%)',
                        data: chartData.humidity,
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Monitoreo Ambiental'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
            
        } catch (error) {
            console.error('❌ Error al crear gráfico:', error);
        }
    }

    /**
     * OBTENER DATOS PARA GRÁFICO
     * Prepara los datos para mostrar en gráficos
     */
    async getChartData() {
        if (this.appState.isConnected) {
            try {
                const response = await this.makeApiRequest('/api/datos/grafico', 'GET');
                if (response.ok) {
                    return response.data;
                }
            } catch (error) {
                console.warn('⚠️ Error al obtener datos del gráfico, usando datos mock');
            }
        }
        
        // Datos de ejemplo si no hay conexión
        return {
            labels: ['Hace 5h', 'Hace 4h', 'Hace 3h', 'Hace 2h', 'Hace 1h', 'Ahora'],
            temperature: [22.5, 23.1, 24.2, 24.8, 25.3, 24.5],
            humidity: [65.2, 66.8, 68.1, 67.5, 69.2, 68.2]
        };
    }

    // ... (resto de métodos originales)
    
    /**
     * CONFIGURAR REFERENCIAS DEL DOM
     * Cachea los elementos del DOM que se usan frecuentemente
     */
    setupDOMReferences() {
        console.log('🔗 Configurando referencias del DOM...');
        this.elements = {
            // Secciones principales
            sections: document.querySelectorAll('.page-section'),
            navLinks: document.querySelectorAll('.nav-link'),
            // Formulario de monitoreo
            monitoringForm: document.getElementById('monitoring-form'),
            temperatureInput: document.querySelector('#monitoreo input[type="number"]:first-of-type'),
            humidityInput: document.querySelector('#monitoreo input[type="number"]:last-of-type'),
            observationsTextarea: document.querySelector('#monitoreo textarea'),
            measurementTypeSelect: document.querySelector('#monitoreo select'),
            // Estadísticas
            statNumbers: document.querySelectorAll('.stat-number'),
            lastUpdateTime: document.getElementById('last-update-time'),
            // Gráficos
            environmentalChart: document.getElementById('environmental-chart'),
            // Filtros de reportes
            reportType: document.getElementById('report-type'),
            dateFrom: document.getElementById('date-from'),
            dateTo: document.getElementById('date-to'),
            // Modal de alertas
            alertModal: document.getElementById('alertModal'),
            alertModalTitle: document.getElementById('alertModalTitle'),
            alertModalBody: document.getElementById('alertModalBody')
        };
        console.log('✅ Referencias del DOM configuradas');
    }

    /**
     * CONFIGURAR EVENT LISTENERS
     * Configura todos los eventos de la interfaz
     */
    setupEventListeners() {
        console.log('👂 Configurando event listeners...');
        // Navegación entre secciones
        this.elements.navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const sectionId = link.getAttribute('href').substring(1);
                this.showSection(sectionId);
            });
        });
        // Formulario de monitoreo (si existe)
        if (this.elements.monitoringForm) {
            this.elements.monitoringForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveMonitoring();
            });
        }
        // Eventos del teclado
        document.addEventListener('keydown', (e) => {
            // ESC para cerrar modales
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
        console.log('✅ Event listeners configurados');
    }

    /**
     * INICIALIZAR COMPONENTES
     * Inicializa gráficos, animaciones y otros componentes
     */
    async initializeComponents() {
        console.log('🔧 Inicializando componentes...');
        // Animación de números con delay
        setTimeout(() => {
            this.animateNumbers();
        }, 500);
        // Crear gráfico con delay
        setTimeout(async () => {
            await this.createEnvironmentalChart();
        }, 1000);
        // Actualizar tiempo inicial
        this.updateTime();
        console.log('✅ Componentes inicializados');
    }

    /**
     * CARGAR DATOS INICIALES
     * Carga los datos necesarios al inicio de la aplicación
     */
    async loadInitialData() {
        console.log('📊 Cargando datos iniciales...');
        try {
            // Intentar cargar datos reales
            await this.loadRealTimeData();
        } catch (error) {
            console.warn('⚠️ No se pudieron cargar datos del servidor, usando datos de ejemplo');
            this.loadMockData();
        }
        console.log('✅ Datos iniciales cargados');
    }

    /**
     * NAVEGACIÓN ENTRE SECCIONES
     * Maneja el cambio entre diferentes secciones de la aplicación
     */
    showSection(sectionId) {
        console.log(`🔄 Cambiando a sección: ${sectionId}`);
        // Ocultar todas las secciones
        this.elements.sections.forEach(section => {
            section.style.display = 'none';
        });
        // Mostrar la sección seleccionada
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.style.display = 'block';
            this.currentSection = sectionId;
        }
        // Actualizar navegación activa
        this.elements.navLinks.forEach(link => {
            link.classList.remove('active');
        });
        const activeLink = document.querySelector(`[href="#${sectionId}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
        // Ejecutar acciones específicas por sección
        this.onSectionChange(sectionId);
    }

    /**
     * ACCIONES AL CAMBIAR DE SECCIÓN
     * Ejecuta acciones específicas cuando se cambia de sección
     */
    onSectionChange(sectionId) {
        switch (sectionId) {
            case 'home':
                // Actualizar estadísticas en tiempo real
                this.loadRealTimeData();
                break;
            case 'monitoreo':
                // Preparar formulario
                this.prepareMonitoringForm();
                break;
            case 'reportes':
                // Inicializar filtros de reportes
                this.initializeReportFilters();
                break;
            default:
                console.log(`Sección ${sectionId} cargada`);
        }
    }

    /**
     * PREPARAR FORMULARIO DE MONITOREO
     * Prepara el formulario con valores predeterminados
     */
    prepareMonitoringForm() {
        console.log('📝 Preparando formulario de monitoreo...');
        // Aquí puedes añadir lógica para preparar el formulario
        // Por ejemplo, establecer fecha/hora actual, limpiar campos, etc.
    }

    /**
     * INICIALIZAR FILTROS DE REPORTES
     * Configura los filtros de fecha para reportes
     */
    initializeReportFilters() {
        console.log('🔍 Inicializando filtros de reportes...');
        
        // Establecer fechas predeterminadas (últimos 7 días)
        const today = new Date();
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        
        if (this.elements.dateTo) {
            this.elements.dateTo.value = today.toISOString().split('T')[0];
        }
        if (this.elements.dateFrom) {
            this.elements.dateFrom.value = weekAgo.toISOString().split('T')[0];
        }
    }

    /**
     * SISTEMA DE ALERTAS
     * Muestra alertas al usuario usando Bootstrap Modal
     */
    showAlert(message, type = 'info', title = 'Notificación') {
        console.log(`🔔 Alerta [${type}]: ${message}`);
        try {
            // Usar Bootstrap Modal si está disponible
            if (typeof bootstrap !== 'undefined' && this.elements.alertModal) {
                const modal = new bootstrap.Modal(this.elements.alertModal);
                this.elements.alertModalTitle.textContent = title;
                this.elements.alertModalBody.innerHTML = `
                    <div class="alert alert-${type} mb-0">
                        <i class="fas fa-${this.getAlertIcon(type)} me-2"></i>
                        ${message}
                    </div>
                `;
                modal.show();
            } else {
                // Fallback a alert nativo
                alert(`${title}: ${message}`);
            }
        } catch (error) {
            console.error('Error al mostrar alerta:', error);
            alert(`${title}: ${message}`);
        }
    }

    /**
     * OBTENER ICONO PARA ALERTAS
     * Retorna el icono apropiado según el tipo de alerta
     */
    getAlertIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-triangle',
            'warning': 'exclamation-circle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    /**
     * CERRAR TODOS LOS MODALES
     * Cierra cualquier modal abierto
     */
    closeAllModals() {
        if (typeof bootstrap !== 'undefined') {
            const modals = document.querySelectorAll('.modal.show');
            modals.forEach(modal => {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) {
                    bsModal.hide();
                }
            });
        }
    }

    /**
     * ANIMACIÓN DE NÚMEROS
     * Anima los números estadísticos de la página principal
     */
    animateNumbers() {
        console.log('🎯 Iniciando animación de números...');
        this.elements.statNumbers.forEach(element => {
            const target = parseFloat(element.getAttribute('data-target')) || 0;
            const duration = 2000; // 2 segundos
            const start = 0;
            const increment = target / (duration / 16); // 60 FPS
            let current = start;
            const timer = setInterval(() => {
                current += increment;
                if (current >= target) {
                    current = target;
                    clearInterval(timer);
                }
                element.textContent = current.toFixed(1);
            }, 16);
        });
    }

    /**
     * ACTUALIZAR TIEMPO
     * Actualiza la marca de tiempo de la última actualización
     */
    updateTime() {
        const now = new Date();
        const timeString = now.toLocaleString('es-PE', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        if (this.elements.lastUpdateTime) {
            this.elements.lastUpdateTime.textContent = timeString;
        }
        this.appState.lastUpdate = now;
    }

    /**
     * CARGAR DATOS MOCK (EJEMPLO)
     * Carga datos de ejemplo cuando no hay conexión con el servidor
     */
    loadMockData() {
        console.log('📊 Cargando datos de ejemplo...');
        // Actualizar estadísticas con datos de ejemplo
        const mockData = {
            temperatura: 24.5,
            humedad: 68.2,
            presion: 1013.25,
            timestamp: new Date()
        };
        this.updateStatistics(mockData);
    }

    /**
     * ACTUALIZAR ESTADÍSTICAS
     * Actualiza los números estadísticos en la interfaz
     */
    updateStatistics(data) {
        if (data.temperatura && this.elements.statNumbers[0]) {
            this.elements.statNumbers[0].setAttribute('data-target', data.temperatura);
            this.elements.statNumbers[0].textContent = data.temperatura;
        }
        if (data.humedad && this.elements.statNumbers[1]) {
            this.elements.statNumbers[1].setAttribute('data-target', data.humedad);
            this.elements.statNumbers[1].textContent = data.humedad;
        }
        // Agregar más estadísticas según sea necesario
    }

    /**
     * INICIAR ACTUALIZACIONES AUTOMÁTICAS
     * Inicia un intervalo para actualizar datos automáticamente
     */
    startAutoUpdate() {
        console.log('🔄 Iniciando actualizaciones automáticas...');
        // Limpiar intervalo existente si existe
        if (this.appState.autoUpdateInterval) {
            clearInterval(this.appState.autoUpdateInterval);
        }
        // Actualizar cada 30 segundos
        this.appState.autoUpdateInterval = setInterval(async () => {
            if (this.appState.isConnected) {
                await this.loadRealTimeData();
            }
            this.updateTime();
        }, 30000);
    }

    /**
     * DETENER ACTUALIZACIONES AUTOMÁTICAS
     * Detiene las actualizaciones automáticas
     */
    stopAutoUpdate() {
        if (this.appState.autoUpdateInterval) {
            clearInterval(this.appState.autoUpdateInterval);
            this.appState.autoUpdateInterval = null;
            console.log('⏹️ Actualizaciones automáticas detenidas');
        }
    }
}

// Inicializar la aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', async () => {
    const app = new MonitoringApp();
    await app.init();
    
    // Hacer la instancia global para debugging
    window.monitoringApp = app;
});