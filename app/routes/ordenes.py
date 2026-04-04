from __future__ import annotations
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import db
from app.models import OrdenTrabajo, OrdenEvidencia, Usuario
from app.utils import now_date_str, now_time_str, save_upload, file_size_bytes, to_float

ordenes_bp = Blueprint('ordenes', __name__)

def require_roles(*allowed):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if get_jwt().get('rol') not in allowed:
                return jsonify({'mensaje': 'No autorizado.'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@ordenes_bp.get('')
@jwt_required()
def list_ordenes():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    q = OrdenTrabajo.query.order_by(OrdenTrabajo.id.desc())
    if user.rol.nombre == 'TECNICO':
        q = q.filter_by(tecnico_id=user.id)
    return jsonify([{
        'id': o.id,
        'titulo': o.titulo,
        'descripcion': o.descripcion,
        'estado': o.estado,
        'prioridad': o.prioridad,
        'fecha': o.fecha,
        'hora': o.hora,
        'latitud': o.latitud,
        'longitud': o.longitud,
        'tecnico': o.tecnico.nombre_completo if o.tecnico else None,
        'incidencia_id': o.incidencia_id,
        'detalle_finalizacion': o.detalle_finalizacion,
        'materiales_usados': o.materiales_usados,
        'fecha_finalizacion': o.fecha_finalizacion,
        'hora_finalizacion': o.hora_finalizacion,
    } for o in q.all()])

@ordenes_bp.post('/<int:orden_id>/finalizar')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def finalizar_orden(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    data = request.form if request.content_type and request.content_type.startswith('multipart') else (request.get_json(silent=True) or {})
    foto = request.files.get('evidencia') if request.files else None

    orden.estado = 'FINALIZADA'
    orden.detalle_finalizacion = data.get('detalle_finalizacion') or 'Actividad completada'
    orden.materiales_usados = data.get('materiales_usados') or ''
    orden.fecha_finalizacion = now_date_str()
    orden.hora_finalizacion = now_time_str()
    if data.get('latitud'):
        orden.latitud = to_float(data.get('latitud'))
    if data.get('longitud'):
        orden.longitud = to_float(data.get('longitud'))

    if foto:
        ruta, original = save_upload(foto, 'ordenes')
        db.session.add(OrdenEvidencia(
            orden_id=orden.id,
            ruta_imagen=ruta,
            nombre_archivo=original,
            tipo_archivo=foto.mimetype,
            tamano_bytes=file_size_bytes(ruta),
            fecha=now_date_str(),
            hora=now_time_str(),
            subido_por=int(get_jwt_identity())
        ))

    db.session.commit()
    return jsonify({'mensaje': 'Orden finalizada correctamente.', 'id': orden.id})