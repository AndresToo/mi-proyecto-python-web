# Importación de librerías 
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, make_response
from database.models import DatabaseManager  # manejar la base de datos
import json
import csv
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import pandas as pd

# Inicialización de la base de datos
app = Flask(__name__)
db = DatabaseManager()

# principal: página de inicio
@app.route('/')
def index():
    ip_cliente = request.headers.get('X-Forwarded-For', request.remote_addr)
    navegador = request.user_agent.string
    print(f"📥 Nueva visita desde IP: {ip_cliente} - Navegador: {navegador}")

    with open('ips.log', 'a') as f:
        f.write(f"{datetime.now()} - IP: {ip_cliente} - Navegador: {navegador}\n")
    return render_template('index.html')

# formulario de monitoreo
@app.route('/monitoreo')
def monitoreo():
    # parámetros desde la base de datos
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM estaciones_monitoreo WHERE estado = 'activa'")
    estaciones = cursor.fetchall()
    
    cursor.execute("SELECT * FROM parametros_ambientales")
    parametros = cursor.fetchall()
    
    conn.close()
    
    return render_template('monitoreo.html', estaciones=estaciones, parametros=parametros)

# Ruta para agregar una medición desde un formulario
@app.route('/agregar_medicion', methods=['POST'])
def agregar_medicion():
    try:
        data = request.form  # Recoge los datos del formulario
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Inserta la nueva medición en la base de datos
        cursor.execute('''
            INSERT INTO mediciones 
            (id_estacion, id_parametro, valor_medido, fecha_medicion, responsable_medicion, condiciones_climaticas, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['estacion'],
            data['parametro'],
            float(data['valor']),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Fecha y hora actual
            data['responsable'],
            data['condiciones'],
            data['observaciones']
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Medición agregada correctamente'})
    
    except Exception as e:
        # En caso de error, devuelve el mensaje de excepción
        return jsonify({'success': False, 'message': str(e)})

@app.route('/reportes')
def reportes():
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Obtener últimas mediciones
    cursor.execute('''
        SELECT m.fecha_medicion, e.nombre_estacion, p.nombre_parametro, 
               m.valor_medido, p.unidad_medida, p.valor_limite_permisible
        FROM mediciones m
        JOIN estaciones_monitoreo e ON m.id_estacion = e.id_estacion
        JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
        ORDER BY m.fecha_medicion DESC
        LIMIT 20
    ''')
    
    mediciones = cursor.fetchall()
    conn.close()
    
    return render_template('reportes.html', mediciones=mediciones)

# API para enviar datos en JSON para gráficos (por parámetro)
@app.route('/api/datos_grafico/<parametro>')
def datos_grafico(parametro):
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Calcula el promedio diario del parámetro solicitado (últimos 30 días)
    cursor.execute('''
        SELECT DATE(m.fecha_medicion) as fecha, AVG(m.valor_medido) as promedio
        FROM mediciones m
        JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
        WHERE p.nombre_parametro = ?
        GROUP BY DATE(m.fecha_medicion)
        ORDER BY fecha DESC
        LIMIT 30
    ''', (parametro,))
    
    datos = cursor.fetchall()
    conn.close()
    
    # Devuelve los datos en formato JSON
    return jsonify([{'fecha': row[0], 'valor': row[1]} for row in datos])

# NUEVAS FUNCIONES DE DESCARGA
# Función para obtener todos los datos de mediciones con estado
def obtener_datos_completos():
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Consulta completa con join y evaluación de límites
    cursor.execute('''
        SELECT m.fecha_medicion, e.nombre_estacion, p.nombre_parametro, 
               m.valor_medido, p.unidad_medida, p.valor_limite_permisible,
               m.responsable_medicion, m.condiciones_climaticas, m.observaciones,
               CASE 
                   WHEN m.valor_medido > p.valor_limite_permisible THEN 'Excede límite'
                   ELSE 'Dentro del límite'
               END as estado
        FROM mediciones m
        JOIN estaciones_monitoreo e ON m.id_estacion = e.id_estacion
        JOIN parametros_ambientales p ON m.id_parametro = p.id_parametro
        ORDER BY m.fecha_medicion DESC
    ''')
    
    datos = cursor.fetchall()
    conn.close()
    
    return datos

# Exportar datos a CSV
@app.route('/exportar/csv')
def exportar_csv():
    """Exportar datos a CSV"""
    try:
        datos = obtener_datos_completos()
        # Crear un buffer en memoria
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Escribir encabezados
        headers = ['Fecha', 'Estación', 'Parámetro', 'Valor', 'Unidad', 
                  'Límite', 'Responsable', 'Condiciones', 'Observaciones', 'Estado']
        writer.writerow(headers)
        
        # Escribir datos
        for fila in datos:
            writer.writerow(fila)
        
        # Preparar respuesta
        output.seek(0)
        
        # Crear respuesta HTTP
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=monitoreo_ambiental_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Exportar datos a Excel
@app.route('/exportar/excel')
def exportar_excel():
    """Exportar datos a Excel"""
    try:
        datos = obtener_datos_completos()
        
        # Crear DataFrame
        df = pd.DataFrame(datos, columns=[
            'Fecha', 'Estación', 'Parámetro', 'Valor', 'Unidad', 
            'Límite', 'Responsable de la medicion', 'Condiciones', 'Observaciones', 'Estado'
        ])
        
        # Crear buffer en memoria
        output = io.BytesIO()
        
        # Crear archivo Excel con pandas
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Monitoreo Ambiental', index=False)
            
            # Obtener el workbook y worksheet para formatear
            workbook = writer.book
            worksheet = writer.sheets['Monitoreo Ambiental']
            
            # Ajustar ancho de columnas
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
        response.headers['Content-Disposition'] = f'attachment; filename=monitoreo_ambiental_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Exportar datos a PDF
@app.route('/exportar/pdf')
def exportar_pdf():
    """Generar reporte PDF"""
    try:
        datos = obtener_datos_completos()
        
        # Crear buffer en memoria
        buffer = io.BytesIO()
        
        # Crear documento PDF
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elementos = []
        
        # Estilos
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Centrado
        )
        
        # Título
        titulo = Paragraph("Reporte de Monitoreo Ambiental - Puerto Huacho", titulo_style)
        elementos.append(titulo)
        
        # Fecha de generación
        fecha_gen = Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal'])
        elementos.append(fecha_gen)
        elementos.append(Spacer(1, 20))
        
        # Resumen estadístico si hay datos
        if datos:
            # Calcular estadísticas básicas
            total_mediciones = len(datos)
            exceden_limite = sum(1 for fila in datos if fila[9] == 'Excede límite')
            
            resumen_texto = f"""
            Resumen del Reporte:
            • Total de mediciones: {total_mediciones}
            • Mediciones que exceden límites: {exceden_limite}
            • Porcentaje de cumplimiento: {((total_mediciones - exceden_limite) / total_mediciones * 100):.1f}%
            """
            
            resumen = Paragraph(resumen_texto, styles['Normal'])
            elementos.append(resumen)
            elementos.append(Spacer(1, 20))
        
        # Tabla de datos
        if datos:
            # Preparar datos para la tabla (limitamos a los primeros 50 registros para el PDF)
            datos_tabla = [['Fecha', 'Estación', 'Parámetro', 'Valor', 'Estado']]
            
            for fila in datos[:50]:  # Limitar a 50 registros
                fecha_formateada = fila[0][:16] if len(fila[0]) > 16 else fila[0]  # Acortar fecha
                estacion = fila[1][:15] if len(fila[1]) > 15 else fila[1]  # Acortar nombre
                parametro = fila[2][:12] if len(fila[2]) > 12 else fila[2]  # Acortar parámetro
                valor_unidad = f"{fila[3]} {fila[4]}"
                estado = fila[9]
                
                datos_tabla.append([fecha_formateada, estacion, parametro, valor_unidad, estado])
            
            # Crear tabla
            tabla = Table(datos_tabla)
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elementos.append(tabla)
            
            if len(datos) > 50:
                nota = Paragraph(f"Nota: Se muestran los primeros 50 registros de {len(datos)} totales.", styles['Normal'])
                elementos.append(Spacer(1, 10))
                elementos.append(nota)
        else:
            sin_datos = Paragraph("No hay datos disponibles para mostrar.", styles['Normal'])
            elementos.append(sin_datos)
        
        # Construir PDF
        doc.build(elementos)
        buffer.seek(0)
        
        # Crear respuesta HTTP
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=reporte_monitoreo_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import os

    port = int(os.environ.get('PORT', 8000))

    # Detectar si está en entorno local
    is_local = os.environ.get('RAILWAY_STATIC_URL') is None

    app.run(
        debug=True,
        host='127.0.0.1' if is_local else '0.0.0.0',
        port=port
    )
