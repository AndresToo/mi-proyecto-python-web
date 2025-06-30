# Importación de librerías 
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, make_response
# Removemos CORS para evitar problemas
from database.models import DatabaseManager  # manejar la base de datos
import json
import csv
import io
import os
import logging
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import pandas as pd

# Configuración de logging para debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicialización de la aplicación Flask
app = Flask(__name__)

# Configuración de seguridad básica
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-desarrollo-cambiar-en-produccion')

# Inicialización de la base de datos
db = DatabaseManager()

# ==================== UTILIDADES Y HELPERS ====================

def validar_numero(valor, nombre_campo="valor"):
    """
    Valida que un valor sea un número válido
    Args:
        valor: El valor a validar
        nombre_campo: Nombre del campo para el mensaje de error
    Returns:
        float: El valor convertido a float
    Raises:
        ValueError: Si el valor no es válido
    """
    try:
        numero = float(valor)
        if numero < -100 or numero > 1000:  # Rango razonable para datos ambientales
            raise ValueError(f"{nombre_campo} fuera del rango válido (-100 a 1000)")
        return numero
    except (ValueError, TypeError):
        raise ValueError(f"{nombre_campo} debe ser un número válido")

def registrar_visita():
    """Registra la visita del usuario en el log"""
    try:
        ip_cliente = request.headers.get('X-Forwarded-For', request.remote_addr)
        navegador = request.user_agent.string
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        logger.info(f"Nueva visita - IP: {ip_cliente}, Navegador: {navegador[:50]}...")
        
        # Crear directorio logs si no existe
        os.makedirs('logs', exist_ok=True)
        
        with open('logs/visitas.log', 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - IP: {ip_cliente} - Navegador: {navegador}\n")
    except Exception as e:
        logger.error(f"Error al registrar visita: {e}")

def obtener_estadisticas_rapidas():
    """Obtiene estadísticas básicas del sistema"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Total de mediciones
        cursor.execute("SELECT COUNT(*) FROM mediciones")
        total_mediciones = cursor.fetchone()[0]
        
        # Mediciones de hoy
        cursor.execute("""
            SELECT COUNT(*) FROM mediciones 
            WHERE DATE(fecha_medicion) = DATE('now')
        """)
        mediciones_hoy = cursor.fetchone()[0]
        
        # Estaciones activas
        cursor.execute("SELECT COUNT(*) FROM estaciones_monitoreo WHERE estado = 'activa'")
        estaciones_activas = cursor.fetchone()[0]
        
        # Último registro
        cursor.execute("""
            SELECT MAX(fecha_medicion) FROM mediciones
        """)
        ultimo_registro = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_mediciones': total_mediciones,
            'mediciones_hoy': mediciones_hoy,
            'estaciones_activas': estaciones_activas,
            'ultimo_registro': ultimo_registro
        }
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {e}")
        return {
            'total_mediciones': 0,
            'mediciones_hoy': 0,
            'estaciones_activas': 0,
            'ultimo_registro': None
        }

# ==================== RUTAS PRINCIPALES ====================

@app.route('/')
def index():
    """Página principal del sistema"""
    registrar_visita()
    estadisticas = obtener_estadisticas_rapidas()
    return render_template('index.html', estadisticas=estadisticas)

@app.route('/monitoreo')
def monitoreo():
    """Página del formulario de monitoreo"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Obtener estaciones activas
        cursor.execute("SELECT * FROM estaciones_monitoreo WHERE estado = 'activa'")
        estaciones = cursor.fetchall()
        
        # Obtener parámetros disponibles
        cursor.execute("SELECT * FROM parametros_ambientales ORDER BY nombre_parametro")
        parametros = cursor.fetchall()
        
        conn.close()
        
        return render_template('monitoreo.html', 
                             estaciones=estaciones, 
                             parametros=parametros)
    except Exception as e:
        logger.error(f"Error en página monitoreo: {e}")
        return render_template('error.html', 
                             mensaje="Error al cargar la página de monitoreo"), 500

@app.route('/reportes')
def reportes():
    """Página de reportes y visualización"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Obtener las últimas 50 mediciones con información completa
        cursor.execute('''
            SELECT m.fecha_medicion, e.nombre_estacion, p.nombre_parametro, 
                   m.valor_medido, p.unidad_medida, p.valor_limite_permisible,
                   m.responsable_medicion,
                   CASE 
                       WHEN m.valor_medido > p.valor_limite_permisible THEN 'Excede límite'
                       ELSE 'Normal'
                   END as estado
            FROM mediciones m
            JOIN estaciones_monitoreo e ON m.id_estacion = e.id_estacion
            JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
            ORDER BY m.fecha_medicion DESC
            LIMIT 50
        ''')
        
        mediciones = cursor.fetchall()
        
        # Obtener resumen por parámetro
        cursor.execute('''
            SELECT p.nombre_parametro, COUNT(*) as total_mediciones,
                   AVG(m.valor_medido) as promedio,
                   MIN(m.valor_medido) as minimo,
                   MAX(m.valor_medido) as maximo
            FROM mediciones m
            JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
            WHERE m.fecha_medicion >= datetime('now', '-30 days')
            GROUP BY p.nombre_parametro
        ''')
        
        resumen_parametros = cursor.fetchall()
        conn.close()
        
        return render_template('reportes.html', 
                             mediciones=mediciones,
                             resumen_parametros=resumen_parametros)
    except Exception as e:
        logger.error(f"Error en página reportes: {e}")
        return render_template('error.html', 
                             mensaje="Error al cargar los reportes"), 500

# ==================== RUTAS DE PROCESAMIENTO ====================

@app.route('/agregar_medicion', methods=['POST'])
def agregar_medicion():
    """Agrega una nueva medición desde el formulario web"""
    try:
        # Validar que se recibieron datos
        if not request.form:
            return jsonify({'success': False, 'message': 'No se recibieron datos'})
        
        data = request.form
        
        # Validaciones básicas
        campos_requeridos = ['estacion', 'parametro', 'valor', 'responsable']
        for campo in campos_requeridos:
            if not data.get(campo):
                return jsonify({
                    'success': False, 
                    'message': f'El campo {campo} es obligatorio'
                })
        
        # Validar el valor numérico
        try:
            valor_medido = validar_numero(data['valor'], 'Valor de medición')
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)})
        
        # Insertar en la base de datos
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO mediciones 
            (id_estacion, id_parametro, valor_medido, fecha_medicion, 
             responsable_medicion, condiciones_climaticas, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(data['estacion']),
            int(data['parametro']),
            valor_medido,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data['responsable'].strip(),
            data.get('condiciones', '').strip(),
            data.get('observaciones', '').strip()
        ))
        
        conn.commit()
        medicion_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"Nueva medición agregada - ID: {medicion_id}, Valor: {valor_medido}")
        
        return jsonify({
            'success': True, 
            'message': 'Medición agregada correctamente',
            'id': medicion_id
        })
    
    except Exception as e:
        logger.error(f"Error al agregar medición: {e}")
        return jsonify({
            'success': False, 
            'message': f'Error interno del servidor: {str(e)}'
        }), 500

# ==================== API ENDPOINTS ====================

@app.route('/health')
def health_check():
    """Verifica el estado del servidor"""
    try:
        # Verificar conexión a la base de datos
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'message': 'Servidor funcionando correctamente',
            'database': 'conectada'
        })
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'message': 'Error en el servidor',
            'error': str(e)
        }), 500

@app.route('/api/datos/recientes')
def datos_recientes():
    """Obtiene los datos más recientes de cada parámetro"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Obtener la medición más reciente de cada parámetro
        cursor.execute('''
            SELECT p.nombre_parametro, m.valor_medido, p.unidad_medida, 
                   m.fecha_medicion, e.nombre_estacion, p.valor_limite_permisible
            FROM mediciones m
            JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
            JOIN estaciones_monitoreo e ON m.id_estacion = e.id_estacion
            WHERE m.fecha_medicion = (
                SELECT MAX(m2.fecha_medicion) 
                FROM mediciones m2 
                WHERE m2.id_parametro = m.id_parametro
            )
            ORDER BY m.fecha_medicion DESC
        ''')
        
        datos = cursor.fetchall()
        conn.close()
        
        if not datos:
            # Datos de ejemplo si la base está vacía
            logger.warning("No hay datos en la base de datos, devolviendo datos de ejemplo")
            return jsonify({
                'temperatura': {
                    'valor': 24.5,
                    'unidad': '°C',
                    'fecha': datetime.now().isoformat(),
                    'estacion': 'Sistema de Ejemplo',
                    'limite': 30.0,
                    'estado': 'normal'
                }
            })
        
        # Convertir a formato JSON organizado
        resultado = {}
        for fila in datos:
            parametro_key = fila[0].lower().replace(' ', '_').replace('ñ', 'n')
            valor = fila[1]
            limite = fila[5]
            
            resultado[parametro_key] = {
                'valor': valor,
                'unidad': fila[2],
                'fecha': fila[3],
                'estacion': fila[4],
                'limite': limite,
                'estado': 'alerta' if valor > limite else 'normal'
            }
        
        logger.info(f"Enviando datos recientes de {len(resultado)} parámetros")
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Error al obtener datos recientes: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/datos_grafico/<parametro>')
def datos_grafico_parametro(parametro):
    """Obtiene datos históricos de un parámetro específico para gráficos"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Obtener datos de los últimos 30 días
        cursor.execute('''
            SELECT DATE(m.fecha_medicion) as fecha, 
                   AVG(m.valor_medido) as promedio,
                   COUNT(*) as cantidad_mediciones
            FROM mediciones m
            JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
            WHERE p.nombre_parametro LIKE ?
            AND m.fecha_medicion >= datetime('now', '-30 days')
            GROUP BY DATE(m.fecha_medicion)
            ORDER BY fecha ASC
        ''', (f'%{parametro}%',))
        
        datos = cursor.fetchall()
        conn.close()
        
        if not datos:
            # Generar datos de ejemplo para demostración
            fechas_ejemplo = []
            valores_ejemplo = []
            for i in range(7):
                fecha = (datetime.now() - timedelta(days=6-i)).strftime('%Y-%m-%d')
                valor = 20 + (i * 2) + (i % 3)  # Valores de ejemplo variados
                fechas_ejemplo.append(fecha)
                valores_ejemplo.append(valor)
            
            return jsonify([
                {'fecha': fecha, 'valor': valor} 
                for fecha, valor in zip(fechas_ejemplo, valores_ejemplo)
            ])
        
        # Convertir a formato esperado por el frontend
        resultado = [
            {
                'fecha': fila[0], 
                'valor': round(fila[1], 2),
                'cantidad': fila[2]
            } 
            for fila in datos
        ]
        
        logger.info(f"Enviando {len(resultado)} puntos de datos para {parametro}")
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Error al obtener datos de gráfico para {parametro}: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/monitoreo', methods=['POST'])
def api_agregar_monitoreo():
    """Recibe datos de monitoreo desde dispositivos externos (JSON)"""
    try:
        # Verificar que se recibió JSON
        if not request.is_json:
            return jsonify({
                'success': False, 
                'message': 'Contenido debe ser JSON'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False, 
                'message': 'No se recibieron datos válidos'
            }), 400
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Obtener o crear estación por defecto
        cursor.execute("""
            SELECT id_estacion FROM estaciones_monitoreo 
            WHERE estado = 'activa' 
            ORDER BY id_estacion 
            LIMIT 1
        """)
        estacion_result = cursor.fetchone()
        
        if not estacion_result:
            # Crear estación por defecto
            cursor.execute('''
                INSERT INTO estaciones_monitoreo (nombre_estacion, ubicacion, estado)
                VALUES (?, ?, ?)
            ''', ('Estación API', 'Remoto', 'activa'))
            estacion_id = cursor.lastrowid
            logger.info(f"Creada nueva estación con ID: {estacion_id}")
        else:
            estacion_id = estacion_result[0]
        
        mediciones_guardadas = 0
        
        # Procesar cada parámetro recibido
        for parametro, valor in data.items():
            if parametro in ['observaciones', 'timestamp']:
                continue  # Saltar campos no numéricos
            
            try:
                valor_numerico = validar_numero(valor, parametro)
            except ValueError as e:
                logger.warning(f"Valor inválido para {parametro}: {valor}")
                continue
            
            # Buscar o crear parámetro
            cursor.execute("""
                SELECT id_parametro FROM parametros_ambientales 
                WHERE LOWER(nombre_parametro) LIKE LOWER(?)
            """, (f'%{parametro}%',))
            
            param_result = cursor.fetchone()
            
            if not param_result:
                # Crear nuevo parámetro
                unidad = self._obtener_unidad_por_parametro(parametro)
                limite = self._obtener_limite_por_parametro(parametro)
                
                cursor.execute('''
                    INSERT INTO parametros_ambientales 
                    (nombre_parametro, unidad_medida, valor_limite_permisible)
                    VALUES (?, ?, ?)
                ''', (parametro.title(), unidad, limite))
                param_id = cursor.lastrowid
                logger.info(f"Creado nuevo parámetro: {parametro}")
            else:
                param_id = param_result[0]
            
            # Insertar medición
            cursor.execute('''
                INSERT INTO mediciones 
                (id_estacion, id_parametro, valor_medido, fecha_medicion, 
                 responsable_medicion, observaciones)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                estacion_id,
                param_id,
                valor_numerico,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Sistema Automático',
                data.get('observaciones', '')
            ))
            
            mediciones_guardadas += 1
            logger.info(f"Guardado {parametro}: {valor_numerico}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'{mediciones_guardadas} mediciones guardadas correctamente',
            'mediciones_procesadas': mediciones_guardadas
        })
        
    except Exception as e:
        logger.error(f"Error en API de monitoreo: {e}")
        return jsonify({
            'success': False, 
            'message': f'Error interno: {str(e)}'
        }), 500

def _obtener_unidad_por_parametro(self, parametro):
    """Determina la unidad de medida según el parámetro"""
    parametro_lower = parametro.lower()
    if 'temperatura' in parametro_lower:
        return '°C'
    elif 'humedad' in parametro_lower:
        return '%'
    elif 'presion' in parametro_lower:
        return 'hPa'
    elif 'viento' in parametro_lower:
        return 'm/s'
    elif 'lluvia' in parametro_lower or 'precipitacion' in parametro_lower:
        return 'mm'
    else:
        return 'unidad'

def _obtener_limite_por_parametro(self, parametro):
    """Determina el límite permisible según el parámetro"""
    parametro_lower = parametro.lower()
    if 'temperatura' in parametro_lower:
        return 35.0
    elif 'humedad' in parametro_lower:
        return 85.0
    elif 'presion' in parametro_lower:
        return 1020.0
    else:
        return 100.0

# ==================== EXPORTACIÓN DE DATOS ====================

def obtener_datos_completos():
    """Obtiene todos los datos de mediciones para exportación"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT m.fecha_medicion, e.nombre_estacion, p.nombre_parametro, 
                   m.valor_medido, p.unidad_medida, p.valor_limite_permisible,
                   m.responsable_medicion, m.condiciones_climaticas, m.observaciones,
                   CASE 
                       WHEN m.valor_medido > p.valor_limite_permisible THEN 'Excede límite'
                       ELSE 'Normal'
                   END as estado
            FROM mediciones m
            JOIN estaciones_monitoreo e ON m.id_estacion = e.id_estacion
            JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
            ORDER BY m.fecha_medicion DESC
        ''')
        
        datos = cursor.fetchall()
        conn.close()
        
        return datos
    except Exception as e:
        logger.error(f"Error al obtener datos completos: {e}")
        return []

@app.route('/exportar/csv')
def exportar_csv():
    """Exporta todos los datos a formato CSV"""
    try:
        datos = obtener_datos_completos()
        
        if not datos:
            return jsonify({'error': 'No hay datos para exportar'}), 404
        
        # Crear buffer en memoria
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Escribir encabezados
        headers = [
            'Fecha', 'Estación', 'Parámetro', 'Valor', 'Unidad', 
            'Límite', 'Responsable', 'Condiciones', 'Observaciones', 'Estado'
        ]
        writer.writerow(headers)
        
        # Escribir datos
        for fila in datos:
            writer.writerow(fila)
        
        output.seek(0)
        
        # Crear respuesta HTTP
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        filename = f'monitoreo_ambiental_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        logger.info(f"Exportando {len(datos)} registros a CSV")
        return response
        
    except Exception as e:
        logger.error(f"Error al exportar CSV: {e}")
        return jsonify({'error': f'Error al generar CSV: {str(e)}'}), 500

@app.route('/exportar/excel')
def exportar_excel():
    """Exporta todos los datos a formato Excel"""
    try:
        datos = obtener_datos_completos()
        
        if not datos:
            return jsonify({'error': 'No hay datos para exportar'}), 404
        
        # Crear DataFrame
        df = pd.DataFrame(datos, columns=[
            'Fecha', 'Estación', 'Parámetro', 'Valor', 'Unidad', 
            'Límite', 'Responsable', 'Condiciones', 'Observaciones', 'Estado'
        ])
        
        # Crear buffer en memoria
        output = io.BytesIO()
        
        # Crear archivo Excel
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Monitoreo Ambiental', index=False)
            
            # Formatear columnas
            workbook = writer.book
            worksheet = writer.sheets['Monitoreo Ambiental']
            
            # Ajustar ancho de columnas automáticamente
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        # Crear respuesta HTTP
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = f'monitoreo_ambiental_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        logger.info(f"Exportando {len(datos)} registros a Excel")
        return response
        
    except Exception as e:
        logger.error(f"Error al exportar Excel: {e}")
        return jsonify({'error': f'Error al generar Excel: {str(e)}'}), 500

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(404)
def pagina_no_encontrada(e):
    """Maneja errores 404"""
    return render_template('error.html', 
                         mensaje="Página no encontrada",
                         codigo=404), 404

@app.errorhandler(500)
def error_interno(e):
    """Maneja errores 500"""
    logger.error(f"Error interno del servidor: {e}")
    return render_template('error.html', 
                         mensaje="Error interno del servidor",
                         codigo=500), 500

# ==================== INICIO DE LA APLICACIÓN ====================

if __name__ == '__main__':
    # Configuración del servidor
    port = int(os.environ.get('PORT', 8000))
    is_local = os.environ.get('RAILWAY_STATIC_URL') is None
    
    # Crear directorios necesarios
    os.makedirs('logs', exist_ok=True)
    
    print("🚀 Iniciando Sistema de Monitoreo Ambiental...")
    print(f"🌐 Puerto: {port}")
    print(f"📍 Entorno: {'Local' if is_local else 'Producción'}")
    print(f"🔒 Modo debug: {is_local}")
    
    # Ejecutar aplicación
    app.run(
        debug=is_local,
        host='127.0.0.1' if is_local else '0.0.0.0',
        port=port,
        threaded=True  # Permite múltiples conexiones simultáneas
    )