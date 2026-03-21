from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.extensions import db
from app.models import Incidencia, IncidenciaEvidencia, IncidenciaSeguimiento, SeguimientoEvidencia, Usuario, Vivienda, Notificacion
from app.utils import file_size_bytes, now_date_str, now_time_str, save_upload, to_float, to_int, create_notification

incidencias_bp = Blueprint('incidencias', __name__)


def require_roles(*allowed):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if get_jwt().get('rol') not in allowed:
                return jsonify({'mensaje': 'No autorizado para esta acción.'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@incidencias_bp.post('')
@jwt_required()
def create_incidencia():
    data = request.form if request.content_type and request.content_type.startswith('multipart/form-data') else (request.get_json(silent=True) or {})
    foto = request.files.get('evidencia') if request.files else None
    fecha = data.get('fecha_reporte') or now_date_str()
    hora = data.get('hora_reporte') or now_time_str()
    vivienda_id = to_int(data.get('vivienda_id'))
    sector_id = None
    if vivienda_id:
        vivienda = Vivienda.query.get(vivienda_id)
        sector_id = vivienda.sector_id if vivienda else None
    reporter = Usuario.query.get_or_404(int(get_jwt_identity()))
    estado_inicial = 'EN_PROCESO' if reporter.rol.nombre == 'TECNICO' else 'REPORTADA'
    item = Incidencia(junta_id=1, reportado_por=int(get_jwt_identity()), vivienda_id=vivienda_id, sector_id=sector_id, tipo_incidencia=data.get('tipo_incidencia') or 'OTRO', titulo=data.get('titulo'), descripcion=data.get('descripcion') or 'Sin descripción', prioridad=data.get('prioridad') or 'MEDIA', estado=estado_inicial, visible_publicamente=True, fecha_reporte=fecha, hora_reporte=hora, latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')))
    db.session.add(item)
    db.session.commit()
    evidencia_ruta = None
    if foto:
        ruta, original = save_upload(foto, 'incidencias')
        db.session.add(IncidenciaEvidencia(incidencia_id=item.id, ruta_imagen=ruta, nombre_archivo=original, tipo_archivo=foto.mimetype, tamano_bytes=file_size_bytes(ruta), fecha=fecha, hora=hora, latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')), subido_por=int(get_jwt_identity())))
        evidencia_ruta = ruta
        db.session.commit()
    admins = Usuario.query.join(Usuario.rol).filter_by(nombre='ADMIN').all()
    for a in admins:
        create_notification(a.id, 'Nueva incidencia', f'Se reportó la incidencia: {item.titulo or item.tipo_incidencia}', 'INCIDENCIA', 'incidencias', item.id)
    return jsonify({'mensaje': 'Incidencia registrada correctamente.', 'id': item.id, 'evidencia': evidencia_ruta}), 201


@incidencias_bp.get('')
@jwt_required()
def list_incidencias():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    q = Incidencia.query.order_by(Incidencia.id.desc())
    if user.rol.nombre == 'SOCIO':
        q = q.filter_by(reportado_por=user.id)
    return jsonify([{'id': i.id, 'titulo': i.titulo, 'tipo_incidencia': i.tipo_incidencia, 'descripcion': i.descripcion, 'prioridad': i.prioridad, 'estado': i.estado, 'fecha_reporte': i.fecha_reporte, 'hora_reporte': i.hora_reporte, 'latitud': i.latitud, 'longitud': i.longitud, 'usuario': i.usuario.nombre_completo if i.usuario else None, 'sector': i.sector.nombre if i.sector else None, 'vivienda': i.vivienda.direccion if i.vivienda else None, 'evidencias': [e.ruta_imagen for e in i.evidencias]} for i in q.all()])


@incidencias_bp.post('/<int:incidencia_id>/seguimiento')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def add_seguimiento(incidencia_id):
    data = request.form if request.content_type and request.content_type.startswith('multipart/form-data') else (request.get_json(silent=True) or {})
    foto = request.files.get('evidencia') if request.files else None
    item = Incidencia.query.get_or_404(incidencia_id)
    fecha = data.get('fecha') or now_date_str()
    hora = data.get('hora') or now_time_str()
    materiales = data.get('materiales_usados') or ''
    accion = data.get('accion_realizada') or 'Seguimiento registrado'
    if materiales:
        accion = f"{accion} | Materiales: {materiales}"
    seg = IncidenciaSeguimiento(incidencia_id=item.id, atendido_por=int(get_jwt_identity()), accion_realizada=accion, observacion=data.get('observacion'), estado_anterior=item.estado, estado_nuevo=data.get('estado_nuevo') or 'EN_PROCESO', fecha=fecha, hora=hora, latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')))
    item.estado = seg.estado_nuevo
    db.session.add(seg)
    db.session.commit()
    if foto:
        ruta, original = save_upload(foto, 'seguimientos')
        db.session.add(SeguimientoEvidencia(seguimiento_id=seg.id, ruta_imagen=ruta, nombre_archivo=original, tipo_archivo=foto.mimetype, tamano_bytes=file_size_bytes(ruta), fecha=fecha, hora=hora, latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')), subido_por=int(get_jwt_identity())))
        db.session.commit()
    if item.usuario and item.usuario.id != int(get_jwt_identity()):
        create_notification(item.usuario.id, 'Actualización de incidencia', f'La incidencia {item.titulo or item.tipo_incidencia} cambió a {item.estado}.', 'INCIDENCIA', 'incidencias', item.id)
    return jsonify({'mensaje': 'Seguimiento registrado correctamente.', 'id': seg.id})


@incidencias_bp.put('/<int:incidencia_id>')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def update_incidencia(incidencia_id):
    item = Incidencia.query.get_or_404(incidencia_id)
    data = request.get_json(silent=True) or {}
    for field in ['tipo_incidencia', 'titulo', 'descripcion', 'prioridad', 'estado']:
        if field in data:
            setattr(item, field, data.get(field))
    db.session.commit()
    return jsonify({'mensaje': 'Incidencia actualizada correctamente.'})


@incidencias_bp.delete('/<int:incidencia_id>')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def delete_incidencia(incidencia_id):
    item = Incidencia.query.get_or_404(incidencia_id)
    item.estado = 'CERRADA'
    db.session.commit()
    return jsonify({'mensaje': 'Incidencia cerrada correctamente.'})


@incidencias_bp.get('/mapa')
@jwt_required()
def incidencias_mapa():
    items = Incidencia.query.filter(Incidencia.latitud.isnot(None), Incidencia.longitud.isnot(None)).order_by(Incidencia.id.desc()).all()
    return jsonify([{
        'id': i.id, 'latitud': i.latitud, 'longitud': i.longitud, 'titulo': i.titulo or i.tipo_incidencia, 'estado': i.estado, 'tipo_incidencia': i.tipo_incidencia,
        'descripcion': i.descripcion, 'fecha_reporte': i.fecha_reporte, 'hora_reporte': i.hora_reporte, 'usuario': i.usuario.nombre_completo if i.usuario else None
    } for i in items])
