import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='database/puerto_huacho.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Crear todas las tablas necesarias"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabla: Estaciones de Monitoreo
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estaciones_monitoreo (
                id_estacion INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_estacion TEXT NOT NULL,
                latitud REAL,
                longitud REAL,
                tipo_estacion TEXT,
                fecha_instalacion DATE,
                estado TEXT DEFAULT 'activa'
            )
        ''')
        
        # Tabla: Parámetros Ambientales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parametros_ambientales (
                id_parametro INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_parametro TEXT NOT NULL,
                unidad_medida TEXT,
                valor_limite_permisible REAL,
                tipo_matriz TEXT,
                descripcion TEXT
            )
        ''')
        
        # Tabla: Mediciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mediciones (
                id_medicion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_estacion INTEGER,
                id_parametro INTEGER,
                valor_medido REAL,
                fecha_medicion DATETIME,
                responsable_medicion TEXT,
                condiciones_climaticas TEXT,
                observaciones TEXT,
                FOREIGN KEY (id_estacion) REFERENCES estaciones_monitoreo (id_estacion),
                FOREIGN KEY (id_parametro) REFERENCES parametros_ambientales (id_parametro)
            )
        ''')
        
        # Tabla: Actividades Pesqueras
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actividades_pesqueras (
                id_actividad INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_actividad TEXT,
                embarcacion TEXT,
                tonelaje_procesado REAL,
                fecha_actividad DATE,
                hora_inicio TIME,
                hora_fin TIME,
                zona_puerto TEXT
            )
        ''')
        
        # Tabla: Aspectos Ambientales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aspectos_ambientales (
                id_aspecto INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_aspecto TEXT,
                descripcion TEXT,
                tipo_aspecto TEXT,
                fuente_generadora TEXT,
                frecuencia TEXT,
                magnitud TEXT
            )
        ''')
        
        # Tabla: Impactos Ambientales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS impactos_ambientales (
                id_impacto INTEGER PRIMARY KEY AUTOINCREMENT,
                id_aspecto INTEGER,
                descripcion_impacto TEXT,
                componente_afectado TEXT,
                tipo_impacto TEXT,
                magnitud INTEGER,
                importancia INTEGER,
                reversibilidad TEXT,
                duracion TEXT,
                FOREIGN KEY (id_aspecto) REFERENCES aspectos_ambientales (id_aspecto)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Insertar datos iniciales
        self.insert_initial_data()
    
    def insert_initial_data(self):
        """Insertar datos básicos para empezar"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Verificar si ya hay datos
        cursor.execute("SELECT COUNT(*) FROM estaciones_monitoreo")
        if cursor.fetchone()[0] == 0:
            
            # Estaciones de monitoreo
            estaciones = [
                ('Entrada del Muelle', -11.12204, -77.6160, 'agua'),
                ('Zona de embarque', -11.12132, -77.6176, 'agua'),
            ]
            
            cursor.executemany('''
                INSERT INTO estaciones_monitoreo 
                (nombre_estacion, latitud, longitud, tipo_estacion)
                VALUES (?, ?, ?, ?)
            ''', estaciones)
        
            
            # Parámetros ambientales µg/m³
            parametros = [
                ('pH', 'escala', 6.5 - 8.5, 'agua', 'Potencial de hidrógeno'),
                ('Oxígeno Disuelto (OD)', 'mg/L', 5.0, 'agua', 'Concentración de oxígeno en agua'),
                ('Salinidad', 'ppm', 35, 'agua', 'Sales disueltas en el agua'),
                ('Temperatura', '°C', 25, 'agua', 'Temperatura del agua'),
            ]
            
            cursor.executemany('''
                INSERT INTO parametros_ambientales 
                (nombre_parametro, unidad_medida, valor_limite_permisible, tipo_matriz, descripcion)
                VALUES (?, ?, ?, ?, ?)
            ''', parametros)
            
        conn.commit()
        conn.close()