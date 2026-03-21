from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.extensions import db
from app.models import Aviso, Usuario
from app.utils import now_date_str, now_time_str

avisos_bp = Blueprint('avisos', __name__)


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


@avisos_bp.get('')
@jwt_required(optional=True)
def list_avisos():
    avisos = Aviso.query.order_by(Aviso.id.desc()).all()
    return jsonify([{'id': a.id, 'titulo': a.titulo, 'contenido': a.contenido, 'tipo_aviso': a.tipo_aviso, 'prioridad': a.prioridad, 'fecha_publicacion': a.fecha_publicacion, 'hora_publicacion': a.hora_publicacion, 'estado': a.estado} for a in avisos])


@avisos_bp.post('')
@jwt_required()
@require_roles('ADMIN')
def create_aviso():
    data = request.get_json(silent=True) or {}
    aviso = Aviso(junta_id=1, creado_por=int(get_jwt_identity()), titulo=data.get('titulo') or 'Aviso sin título', contenido=data.get('contenido') or '', tipo_aviso=data.get('tipo_aviso') or 'COMUNICADO', prioridad=data.get('prioridad') or 'MEDIA', fecha_publicacion=data.get('fecha_publicacion') or now_date_str(), hora_publicacion=data.get('hora_publicacion') or now_time_str(), fecha_inicio=data.get('fecha_inicio'), hora_inicio=data.get('hora_inicio'), fecha_fin=data.get('fecha_fin'), hora_fin=data.get('hora_fin'), aplica_a_todos=True, estado=data.get('estado', 'PUBLICADO'))
    db.session.add(aviso)
    db.session.commit()
    return jsonify({'mensaje': 'Aviso creado correctamente.', 'id': aviso.id}), 201


@avisos_bp.put('/<int:aviso_id>')
@jwt_required()
@require_roles('ADMIN')
def update_aviso(aviso_id):
    aviso = Aviso.query.get_or_404(aviso_id)
    data = request.get_json(silent=True) or {}
    for field in ['titulo', 'contenido', 'tipo_aviso', 'prioridad', 'estado', 'fecha_inicio', 'hora_inicio', 'fecha_fin', 'hora_fin']:
        if field in data:
            setattr(aviso, field, data.get(field))
    db.session.commit()
    return jsonify({'mensaje': 'Aviso actualizado correctamente.'})


@avisos_bp.delete('/<int:aviso_id>')
@jwt_required()
@require_roles('ADMIN')
def delete_aviso(aviso_id):
    aviso = Aviso.query.get_or_404(aviso_id)
    db.session.delete(aviso)
    db.session.commit()
    return jsonify({'mensaje': 'Aviso eliminado correctamente.'})
