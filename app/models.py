from __future__ import annotations

from datetime import datetime
from app.extensions import db


class TimestampMixin:
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, onupdate=datetime.utcnow)


class Rol(TimestampMixin, db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(255))
    estado = db.Column(db.String(20), default='ACTIVO', nullable=False)


class JuntaAgua(TimestampMixin, db.Model):
    __tablename__ = 'juntas_agua'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    parroquia = db.Column(db.String(100))
    canton = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    direccion = db.Column(db.String(255))
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(120))
    logo = db.Column(db.String(255))
    estado = db.Column(db.String(20), default='ACTIVA', nullable=False)


class Sector(TimestampMixin, db.Model):
    __tablename__ = 'sectores'
    id = db.Column(db.Integer, primary_key=True)
    junta_id = db.Column(db.Integer, db.ForeignKey('juntas_agua.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    estado = db.Column(db.String(20), default='ACTIVO', nullable=False)
    junta = db.relationship('JuntaAgua', backref='sectores')


class Usuario(TimestampMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    rol_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    cedula = db.Column(db.String(20), unique=True)
    nombres = db.Column(db.String(120), nullable=False)
    apellidos = db.Column(db.String(120), nullable=False)
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(120), unique=True)
    username = db.Column(db.String(80), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    foto_perfil = db.Column(db.String(255))
    direccion_referencia = db.Column(db.String(255))
    estado = db.Column(db.String(20), default='ACTIVO', nullable=False)
    ultimo_login = db.Column(db.DateTime)
    rol = db.relationship('Rol', backref='usuarios')

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()


class Socio(TimestampMixin, db.Model):
    __tablename__ = 'socios'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, unique=True)
    junta_id = db.Column(db.Integer, db.ForeignKey('juntas_agua.id'), nullable=False)
    codigo_socio = db.Column(db.String(50), unique=True)
    numero_medidor = db.Column(db.String(50), unique=True)
    estado_servicio = db.Column(db.String(20), default='ACTIVO', nullable=False)
    fecha_ingreso = db.Column(db.String(10))
    observacion = db.Column(db.Text)
    usuario = db.relationship('Usuario', backref=db.backref('socio', uselist=False))
    junta = db.relationship('JuntaAgua', backref='socios')


class Vivienda(TimestampMixin, db.Model):
    __tablename__ = 'viviendas'
    id = db.Column(db.Integer, primary_key=True)
    socio_id = db.Column(db.Integer, db.ForeignKey('socios.id'), nullable=False)
    sector_id = db.Column(db.Integer, db.ForeignKey('sectores.id'), nullable=False)
    codigo_vivienda = db.Column(db.String(50), unique=True)
    direccion = db.Column(db.String(255), nullable=False)
    referencia = db.Column(db.String(255))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    tipo_vivienda = db.Column(db.String(50), default='CASA')
    estado = db.Column(db.String(20), default='ACTIVA', nullable=False)
    socio = db.relationship('Socio', backref='viviendas')
    sector = db.relationship('Sector', backref='viviendas')


class Medidor(TimestampMixin, db.Model):
    __tablename__ = 'medidores'
    id = db.Column(db.Integer, primary_key=True)
    socio_id = db.Column(db.Integer, db.ForeignKey('socios.id'), nullable=False)
    vivienda_id = db.Column(db.Integer, db.ForeignKey('viviendas.id'), nullable=False)
    numero_medidor = db.Column(db.String(50), unique=True, nullable=False)
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    estado = db.Column(db.String(20), default='ACTIVO', nullable=False)
    fecha_instalacion = db.Column(db.String(10))
    observacion = db.Column(db.Text)
    socio = db.relationship('Socio', backref='medidores')
    vivienda = db.relationship('Vivienda', backref='medidores')


class RutaLecturacion(TimestampMixin, db.Model):
    __tablename__ = 'rutas_lecturacion'
    id = db.Column(db.Integer, primary_key=True)
    junta_id = db.Column(db.Integer, db.ForeignKey('juntas_agua.id'), nullable=False)
    sector_id = db.Column(db.Integer, db.ForeignKey('sectores.id'))
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    estado = db.Column(db.String(20), default='ACTIVA', nullable=False)
    junta = db.relationship('JuntaAgua', backref='rutas_lecturacion')
    sector = db.relationship('Sector', backref='rutas_lecturacion')
    tecnico = db.relationship('Usuario', backref='rutas_asignadas')


class RutaMedidor(TimestampMixin, db.Model):
    __tablename__ = 'ruta_medidores'
    id = db.Column(db.Integer, primary_key=True)
    ruta_id = db.Column(db.Integer, db.ForeignKey('rutas_lecturacion.id'), nullable=False)
    medidor_id = db.Column(db.Integer, db.ForeignKey('medidores.id'), nullable=False)
    ruta = db.relationship('RutaLecturacion', backref='items')
    medidor = db.relationship('Medidor', backref='rutas')


class Aviso(TimestampMixin, db.Model):
    __tablename__ = 'avisos'
    id = db.Column(db.Integer, primary_key=True)
    junta_id = db.Column(db.Integer, db.ForeignKey('juntas_agua.id'), nullable=False)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    tipo_aviso = db.Column(db.String(50), nullable=False)
    prioridad = db.Column(db.String(20), default='MEDIA', nullable=False)
    fecha_publicacion = db.Column(db.String(10), nullable=False)
    hora_publicacion = db.Column(db.String(8), nullable=False)
    fecha_inicio = db.Column(db.String(10))
    hora_inicio = db.Column(db.String(8))
    fecha_fin = db.Column(db.String(10))
    hora_fin = db.Column(db.String(8))
    aplica_a_todos = db.Column(db.Boolean, default=True, nullable=False)
    estado = db.Column(db.String(20), default='PUBLICADO', nullable=False)
    junta = db.relationship('JuntaAgua', backref='avisos')
    creador = db.relationship('Usuario', backref='avisos_creados')


class Lectura(TimestampMixin, db.Model):
    __tablename__ = 'lecturas'
    id = db.Column(db.Integer, primary_key=True)
    medidor_id = db.Column(db.Integer, db.ForeignKey('medidores.id'))
    vivienda_id = db.Column(db.Integer, db.ForeignKey('viviendas.id'), nullable=False)
    socio_id = db.Column(db.Integer, db.ForeignKey('socios.id'), nullable=False)
    tomado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    lectura_anterior = db.Column(db.Float)
    lectura_actual = db.Column(db.Float, nullable=False)
    consumo_calculado = db.Column(db.Float, nullable=False, default=0)
    observacion = db.Column(db.Text)
    fecha_lectura = db.Column(db.String(10), nullable=False)
    hora_lectura = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    estado = db.Column(db.String(20), default='REGISTRADA', nullable=False)
    medidor = db.relationship('Medidor', backref='lecturas')
    vivienda = db.relationship('Vivienda', backref='lecturas')
    socio = db.relationship('Socio', backref='lecturas')
    operador = db.relationship('Usuario', backref='lecturas_tomadas')


class LecturaEvidencia(TimestampMixin, db.Model):
    __tablename__ = 'lecturas_evidencias'
    id = db.Column(db.Integer, primary_key=True)
    lectura_id = db.Column(db.Integer, db.ForeignKey('lecturas.id'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    nombre_archivo = db.Column(db.String(255))
    tipo_archivo = db.Column(db.String(50))
    tamano_bytes = db.Column(db.Integer)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    subido_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    lectura = db.relationship('Lectura', backref='evidencias')
    usuario = db.relationship('Usuario', backref='lecturas_evidencias')


class Tarifa(TimestampMixin, db.Model):
    __tablename__ = 'tarifas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    cargo_fijo = db.Column(db.Float, default=0, nullable=False)
    valor_m3 = db.Column(db.Float, default=0, nullable=False)
    mora = db.Column(db.Float, default=0, nullable=False)
    estado = db.Column(db.String(20), default='ACTIVA', nullable=False)
    fecha_inicio = db.Column(db.String(10))
    fecha_fin = db.Column(db.String(10))




class TarifaAsignada(TimestampMixin, db.Model):
    __tablename__ = 'tarifas_asignadas'
    id = db.Column(db.Integer, primary_key=True)
    socio_id = db.Column(db.Integer, db.ForeignKey('socios.id'))
    vivienda_id = db.Column(db.Integer, db.ForeignKey('viviendas.id'))
    tarifa_id = db.Column(db.Integer, db.ForeignKey('tarifas.id'))
    nombre = db.Column(db.String(100), nullable=False, default='Tarifa personalizada')
    base_consumo_m3 = db.Column(db.Float, default=0, nullable=False)
    valor_base = db.Column(db.Float, default=0, nullable=False)
    valor_adicional_m3 = db.Column(db.Float, default=0, nullable=False)
    multa_atraso = db.Column(db.Float, default=0, nullable=False)
    estado = db.Column(db.String(20), default='ACTIVA', nullable=False)
    socio = db.relationship('Socio', backref='tarifas_asignadas')
    vivienda = db.relationship('Vivienda', backref='tarifas_asignadas')
    tarifa = db.relationship('Tarifa', backref='asignaciones')


class Consumo(TimestampMixin, db.Model):
    __tablename__ = 'consumos'
    id = db.Column(db.Integer, primary_key=True)
    lectura_id = db.Column(db.Integer, db.ForeignKey('lecturas.id'), nullable=False, unique=True)
    vivienda_id = db.Column(db.Integer, db.ForeignKey('viviendas.id'), nullable=False)
    socio_id = db.Column(db.Integer, db.ForeignKey('socios.id'), nullable=False)
    periodo_anio = db.Column(db.Integer, nullable=False)
    periodo_mes = db.Column(db.Integer, nullable=False)
    lectura_inicial = db.Column(db.Float)
    lectura_final = db.Column(db.Float)
    consumo_m3 = db.Column(db.Float, nullable=False)
    tarifa_id = db.Column(db.Integer, db.ForeignKey('tarifas.id'))
    cargo_fijo = db.Column(db.Float, default=0)
    valor_m3 = db.Column(db.Float, default=0)
    subtotal_consumo = db.Column(db.Float, default=0)
    recargo = db.Column(db.Float, default=0)
    multa = db.Column(db.Float, default=0)
    total_pagar = db.Column(db.Float, default=0)
    indicador = db.Column(db.String(20), default='BAJO')
    observacion = db.Column(db.Text)
    lectura = db.relationship('Lectura', backref=db.backref('consumo', uselist=False))
    vivienda = db.relationship('Vivienda', backref='consumos')
    socio = db.relationship('Socio', backref='consumos')
    tarifa = db.relationship('Tarifa', backref='consumos')


class Planilla(TimestampMixin, db.Model):
    __tablename__ = 'planillas'
    id = db.Column(db.Integer, primary_key=True)
    socio_id = db.Column(db.Integer, db.ForeignKey('socios.id'), nullable=False)
    vivienda_id = db.Column(db.Integer, db.ForeignKey('viviendas.id'), nullable=False)
    lectura_id = db.Column(db.Integer, db.ForeignKey('lecturas.id'))
    consumo_id = db.Column(db.Integer, db.ForeignKey('consumos.id'))
    periodo_anio = db.Column(db.Integer, nullable=False)
    periodo_mes = db.Column(db.Integer, nullable=False)
    numero_planilla = db.Column(db.String(50), unique=True, nullable=False)
    fecha_emision = db.Column(db.String(10), nullable=False)
    fecha_vencimiento = db.Column(db.String(10))
    lectura_anterior = db.Column(db.Float)
    lectura_actual = db.Column(db.Float)
    consumo_m3 = db.Column(db.Float, nullable=False)
    cargo_fijo = db.Column(db.Float, default=0)
    valor_m3 = db.Column(db.Float, default=0)
    subtotal_consumo = db.Column(db.Float, default=0)
    recargo = db.Column(db.Float, default=0)
    multa = db.Column(db.Float, default=0)
    otros = db.Column(db.Float, default=0)
    total_pagar = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(20), default='PENDIENTE', nullable=False)
    fecha_pago = db.Column(db.String(10))
    hora_pago = db.Column(db.String(8))
    metodo_pago = db.Column(db.String(30))
    referencia_pago = db.Column(db.String(120))
    observacion = db.Column(db.Text)
    pdf_ruta = db.Column(db.String(255))
    socio = db.relationship('Socio', backref='planillas')
    vivienda = db.relationship('Vivienda', backref='planillas')
    lectura = db.relationship('Lectura', backref='planillas')
    consumo = db.relationship('Consumo', backref='planillas')


class Pago(TimestampMixin, db.Model):
    __tablename__ = 'pagos'
    id = db.Column(db.Integer, primary_key=True)
    planilla_id = db.Column(db.Integer, db.ForeignKey('planillas.id'), nullable=False)
    socio_id = db.Column(db.Integer, db.ForeignKey('socios.id'), nullable=False)
    vivienda_id = db.Column(db.Integer, db.ForeignKey('viviendas.id'), nullable=False)
    valor_pagado = db.Column(db.Float, nullable=False)
    fecha_pago = db.Column(db.String(10), nullable=False)
    hora_pago = db.Column(db.String(8), nullable=False)
    metodo_pago = db.Column(db.String(30))
    referencia_pago = db.Column(db.String(120))
    registrado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    observacion = db.Column(db.Text)
    comprobante_pdf_ruta = db.Column(db.String(255))
    planilla = db.relationship('Planilla', backref='pagos')
    socio = db.relationship('Socio', backref='pagos')
    vivienda = db.relationship('Vivienda', backref='pagos')
    usuario = db.relationship('Usuario', backref='pagos_registrados')


class MovimientoCaja(TimestampMixin, db.Model):
    __tablename__ = 'movimientos_caja'
    id = db.Column(db.Integer, primary_key=True)
    tipo_movimiento = db.Column(db.String(20), nullable=False)
    categoria = db.Column(db.String(30), nullable=False)
    referencia_tabla = db.Column(db.String(50))
    referencia_id = db.Column(db.Integer)
    descripcion = db.Column(db.Text)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    registrado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    usuario = db.relationship('Usuario', backref='movimientos_caja')


class Incidencia(TimestampMixin, db.Model):
    __tablename__ = 'incidencias'
    id = db.Column(db.Integer, primary_key=True)
    junta_id = db.Column(db.Integer, db.ForeignKey('juntas_agua.id'), nullable=False)
    reportado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    vivienda_id = db.Column(db.Integer, db.ForeignKey('viviendas.id'))
    sector_id = db.Column(db.Integer, db.ForeignKey('sectores.id'))
    tipo_incidencia = db.Column(db.String(50), nullable=False)
    titulo = db.Column(db.String(150))
    descripcion = db.Column(db.Text, nullable=False)
    prioridad = db.Column(db.String(20), default='MEDIA', nullable=False)
    estado = db.Column(db.String(20), default='REPORTADA', nullable=False)
    visible_publicamente = db.Column(db.Boolean, default=True, nullable=False)
    fecha_reporte = db.Column(db.String(10), nullable=False)
    hora_reporte = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    junta = db.relationship('JuntaAgua', backref='incidencias')
    usuario = db.relationship('Usuario', backref='incidencias_reportadas')
    vivienda = db.relationship('Vivienda', backref='incidencias')
    sector = db.relationship('Sector', backref='incidencias')


class IncidenciaEvidencia(TimestampMixin, db.Model):
    __tablename__ = 'incidencias_evidencias'
    id = db.Column(db.Integer, primary_key=True)
    incidencia_id = db.Column(db.Integer, db.ForeignKey('incidencias.id'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    nombre_archivo = db.Column(db.String(255))
    tipo_archivo = db.Column(db.String(50))
    tamano_bytes = db.Column(db.Integer)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    subido_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    incidencia = db.relationship('Incidencia', backref='evidencias')
    usuario = db.relationship('Usuario', backref='incidencias_evidencias')


class IncidenciaSeguimiento(TimestampMixin, db.Model):
    __tablename__ = 'incidencias_seguimiento'
    id = db.Column(db.Integer, primary_key=True)
    incidencia_id = db.Column(db.Integer, db.ForeignKey('incidencias.id'), nullable=False)
    atendido_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    accion_realizada = db.Column(db.Text, nullable=False)
    observacion = db.Column(db.Text)
    estado_anterior = db.Column(db.String(20))
    estado_nuevo = db.Column(db.String(20))
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    incidencia = db.relationship('Incidencia', backref='seguimientos')
    tecnico = db.relationship('Usuario', backref='seguimientos_realizados')


class SeguimientoEvidencia(TimestampMixin, db.Model):
    __tablename__ = 'seguimiento_evidencias'
    id = db.Column(db.Integer, primary_key=True)
    seguimiento_id = db.Column(db.Integer, db.ForeignKey('incidencias_seguimiento.id'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    nombre_archivo = db.Column(db.String(255))
    tipo_archivo = db.Column(db.String(50))
    tamano_bytes = db.Column(db.Integer)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    subido_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    seguimiento = db.relationship('IncidenciaSeguimiento', backref='evidencias')
    usuario = db.relationship('Usuario', backref='seguimiento_evidencias')


class Notificacion(TimestampMixin, db.Model):
    __tablename__ = 'notificaciones'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    referencia_tabla = db.Column(db.String(50))
    referencia_id = db.Column(db.Integer)
    leido = db.Column(db.Boolean, default=False, nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    usuario = db.relationship('Usuario', backref='notificaciones')


class Recordatorio(TimestampMixin, db.Model):
    __tablename__ = 'recordatorios'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    tipo = db.Column(db.String(30), nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    enviado = db.Column(db.Boolean, default=False, nullable=False)
    usuario = db.relationship('Usuario', backref='recordatorios')


class Reunion(TimestampMixin, db.Model):
    __tablename__ = 'reuniones'
    id = db.Column(db.Integer, primary_key=True)
    junta_id = db.Column(db.Integer, db.ForeignKey('juntas_agua.id'), nullable=False)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    lugar = db.Column(db.String(150))
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    estado = db.Column(db.String(20), default='PROGRAMADA', nullable=False)
    junta = db.relationship('JuntaAgua', backref='reuniones')
    creador = db.relationship('Usuario', backref='reuniones_creadas')


class Sesion(TimestampMixin, db.Model):
    __tablename__ = 'sesiones'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    jti = db.Column(db.String(64), unique=True, nullable=False)
    tipo_token = db.Column(db.String(20), default='REFRESH', nullable=False)
    refresh_token_hash = db.Column(db.String(255))
    access_token_hash = db.Column(db.String(255))
    dispositivo = db.Column(db.String(120))
    sistema_operativo = db.Column(db.String(120))
    ip = db.Column(db.String(80))
    user_agent = db.Column(db.String(255))
    fecha_emision = db.Column(db.String(19), nullable=False)
    fecha_expiracion = db.Column(db.String(19), nullable=False)
    ultimo_uso = db.Column(db.String(19))
    revocado = db.Column(db.Boolean, default=False, nullable=False)
    fecha_revocacion = db.Column(db.String(19))
    usuario = db.relationship('Usuario', backref='sesiones')


class DispositivoPush(TimestampMixin, db.Model):
    __tablename__ = 'dispositivos_push'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    token_push = db.Column(db.String(255), unique=True, nullable=False)
    plataforma = db.Column(db.String(20), nullable=False)
    dispositivo = db.Column(db.String(120))
    activo = db.Column(db.Boolean, default=True, nullable=False)
    ultimo_uso = db.Column(db.String(19))
    usuario = db.relationship('Usuario', backref='dispositivos_push')


class Auditoria(TimestampMixin, db.Model):
    __tablename__ = 'auditoria'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    tabla_afectada = db.Column(db.String(50), nullable=False)
    registro_id = db.Column(db.Integer)
    accion = db.Column(db.String(20), nullable=False)
    detalle = db.Column(db.Text)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    ip = db.Column(db.String(80))
    usuario = db.relationship('Usuario', backref='auditoria')


class ConfiguracionSistema(TimestampMixin, db.Model):
    __tablename__ = 'configuracion_sistema'
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(120), unique=True, nullable=False)
    valor = db.Column(db.String(255))
    descripcion = db.Column(db.Text)


class Mensaje(TimestampMixin, db.Model):
    __tablename__ = 'mensajes'
    id = db.Column(db.Integer, primary_key=True)
    remitente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    asunto = db.Column(db.String(150), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), default='ENVIADO', nullable=False)
    leido = db.Column(db.Boolean, default=False, nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    remitente = db.relationship('Usuario', foreign_keys=[remitente_id], backref='mensajes_enviados')
    destinatario = db.relationship('Usuario', foreign_keys=[destinatario_id], backref='mensajes_recibidos')


class OrdenTrabajo(TimestampMixin, db.Model):
    __tablename__ = 'ordenes_trabajo'
    id = db.Column(db.Integer, primary_key=True)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    incidencia_id = db.Column(db.Integer, db.ForeignKey('incidencias.id'))
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), default='ASIGNADA', nullable=False)
    prioridad = db.Column(db.String(20), default='MEDIA', nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    detalle_finalizacion = db.Column(db.Text)
    materiales_usados = db.Column(db.Text)
    fecha_finalizacion = db.Column(db.String(10))
    hora_finalizacion = db.Column(db.String(8))
    tecnico = db.relationship('Usuario', foreign_keys=[tecnico_id], backref='ordenes_asignadas')
    creador = db.relationship('Usuario', foreign_keys=[creado_por], backref='ordenes_creadas')
    incidencia = db.relationship('Incidencia', backref='ordenes_trabajo')


class OrdenEvidencia(TimestampMixin, db.Model):
    __tablename__ = 'ordenes_evidencias'
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_trabajo.id'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    nombre_archivo = db.Column(db.String(255))
    tipo_archivo = db.Column(db.String(50))
    tamano_bytes = db.Column(db.Integer)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    subido_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    orden = db.relationship('OrdenTrabajo', backref='evidencias')
    usuario = db.relationship('Usuario', backref='ordenes_evidencias')


class ReclamoLectura(TimestampMixin, db.Model):
    __tablename__ = 'reclamos_lectura'
    id = db.Column(db.Integer, primary_key=True)
    lectura_id = db.Column(db.Integer, db.ForeignKey('lecturas.id'), nullable=False)
    reportado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    motivo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    estado = db.Column(db.String(20), default='ABIERTO', nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    hora = db.Column(db.String(8), nullable=False)
    lectura = db.relationship('Lectura', backref='reclamos')
    usuario = db.relationship('Usuario', backref='reclamos_lectura')
