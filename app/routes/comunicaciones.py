from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.extensions import db
from app.models import Mensaje, Notificacion, OrdenTrabajo, OrdenEvidencia, Incidencia, Usuario
from app.utils import create_notification, file_size_bytes, now_date_str, now_time_str, save_upload, sync_system_alerts, to_float, to_int

comunicaciones_bp = Blueprint("comunicaciones", __name__)


def require_roles(*allowed):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if get_jwt().get("rol") not in allowed:
                return jsonify({"mensaje": "No autorizado para esta acción."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@comunicaciones_bp.get('/notificaciones')
@jwt_required()
def list_notificaciones():
    uid = int(get_jwt_identity())
    items = Notificacion.query.filter_by(usuario_id=uid).order_by(Notificacion.id.desc()).all()
    return jsonify([{
        'id': n.id, 'titulo': n.titulo, 'mensaje': n.mensaje, 'tipo': n.tipo, 'referencia_tabla': n.referencia_tabla, 'referencia_id': n.referencia_id, 'leido': n.leido, 'fecha': n.fecha, 'hora': n.hora
    } for n in items])


@comunicaciones_bp.put('/notificaciones/<int:notificacion_id>/leer')
@jwt_required()
def read_notificacion(notificacion_id):
    n = Notificacion.query.get_or_404(notificacion_id)
    if n.usuario_id != int(get_jwt_identity()):
        return jsonify({'mensaje':'No autorizado.'}), 403
    n.leido = True
    db.session.commit()
    return jsonify({'mensaje':'Notificación marcada como leída.'})




@comunicaciones_bp.post('/notificaciones/sincronizar')
@jwt_required()
def sync_notificaciones():
    result = sync_system_alerts()
    return jsonify({'mensaje': 'Alertas sincronizadas.', **result})


@comunicaciones_bp.put('/mensajes/<int:mensaje_id>/leer')
@jwt_required()
def read_mensaje(mensaje_id):
    uid = int(get_jwt_identity())
    m = Mensaje.query.get_or_404(mensaje_id)
    if m.destinatario_id != uid and m.remitente_id != uid:
        return jsonify({'mensaje': 'No autorizado.'}), 403
    m.leido = True
    if m.estado == 'ENVIADO':
        m.estado = 'LEIDO'
    db.session.commit()
    return jsonify({'mensaje': 'Mensaje marcado como leído.'})

@comunicaciones_bp.get('/mensajes')
@jwt_required()
def list_mensajes():
    uid = int(get_jwt_identity())
    items = Mensaje.query.filter((Mensaje.remitente_id == uid) | (Mensaje.destinatario_id == uid)).order_by(Mensaje.id.desc()).all()
    return jsonify([{
        'id': m.id, 'asunto': m.asunto, 'contenido': m.contenido, 'estado': m.estado, 'leido': m.leido, 'fecha': m.fecha, 'hora': m.hora,
        'remitente': m.remitente.nombre_completo if m.remitente else None,
        'destinatario': m.destinatario.nombre_completo if m.destinatario else None,
        'remitente_id': m.remitente_id, 'destinatario_id': m.destinatario_id
    } for m in items])


@comunicaciones_bp.post('/mensajes')
@jwt_required()
def create_mensaje():
    uid = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    destinatario_id = to_int(data.get('destinatario_id'))
    if not destinatario_id:
        # if no explicit recipient, send to first admin for non-admin or to first tecnico for admin
        sender = Usuario.query.get_or_404(uid)
        if sender.rol.nombre == 'ADMIN':
            dest = Usuario.query.join(Usuario.rol).filter_by(nombre='TECNICO').first()
        else:
            dest = Usuario.query.join(Usuario.rol).filter_by(nombre='ADMIN').first()
        destinatario_id = dest.id if dest else uid
    m = Mensaje(remitente_id=uid, destinatario_id=destinatario_id, asunto=data.get('asunto') or 'Mensaje del sistema', contenido=data.get('contenido') or '', fecha=now_date_str(), hora=now_time_str(), estado='ENVIADO', leido=False)
    db.session.add(m)
    create_notification(destinatario_id, 'Nuevo mensaje', f'Recibiste un mensaje: {m.asunto}', 'MENSAJE', 'mensajes', None)
    db.session.commit()
    return jsonify({'mensaje':'Mensaje enviado correctamente.', 'id': m.id}), 201


@comunicaciones_bp.get('/ordenes')
@jwt_required()
def list_ordenes():
    uid = int(get_jwt_identity())
    rol = get_jwt().get('rol')
    q = OrdenTrabajo.query.order_by(OrdenTrabajo.id.desc())
    if rol == 'TECNICO':
        q = q.filter_by(tecnico_id=uid)
    return jsonify([{
        'id': o.id, 'titulo': o.titulo, 'descripcion': o.descripcion, 'estado': o.estado, 'prioridad': o.prioridad, 'fecha': o.fecha, 'hora': o.hora, 'latitud': o.latitud, 'longitud': o.longitud,
        'tecnico': o.tecnico.nombre_completo if o.tecnico else None, 'incidencia_id': o.incidencia_id, 'materiales_usados': o.materiales_usados,
        'fecha_finalizacion': o.fecha_finalizacion, 'hora_finalizacion': o.hora_finalizacion, 'evidencias': [e.ruta_imagen for e in o.evidencias]
    } for o in q.all()])


@comunicaciones_bp.post('/ordenes')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def create_orden():
    uid = int(get_jwt_identity())
    data = request.form if request.content_type and request.content_type.startswith('multipart/form-data') else (request.get_json(silent=True) or {})
    foto = request.files.get('evidencia') if request.files else None
    tecnico_id = to_int(data.get('tecnico_id')) or uid
    item = OrdenTrabajo(tecnico_id=tecnico_id, creado_por=uid, incidencia_id=to_int(data.get('incidencia_id')), titulo=data.get('titulo') or 'Actividad técnica', descripcion=data.get('descripcion') or '', prioridad=data.get('prioridad') or 'MEDIA', estado=data.get('estado') or ('EN_PROCESO' if tecnico_id == uid else 'ASIGNADA'), fecha=data.get('fecha') or now_date_str(), hora=data.get('hora') or now_time_str(), latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')))
    db.session.add(item)
    db.session.flush()
    if foto:
        ruta, original = save_upload(foto, 'seguimientos')
        db.session.add(OrdenEvidencia(orden_id=item.id, ruta_imagen=ruta, nombre_archivo=original, tipo_archivo=foto.mimetype, tamano_bytes=file_size_bytes(ruta), fecha=item.fecha, hora=item.hora, latitud=item.latitud, longitud=item.longitud, subido_por=uid))
    if item.incidencia_id:
        inc = Incidencia.query.get(item.incidencia_id)
        if inc:
            inc.estado = 'ASIGNADA' if tecnico_id != uid else 'EN_PROCESO'
    create_notification(tecnico_id, 'Nueva orden técnica', f'Se te asignó la actividad: {item.titulo}', 'ORDEN_TECNICA', 'ordenes_trabajo', item.id)
    db.session.commit()
    return jsonify({'mensaje':'Orden registrada correctamente.', 'id': item.id}), 201


@comunicaciones_bp.put('/ordenes/<int:orden_id>/finalizar')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def finish_orden(orden_id):
    uid = int(get_jwt_identity())
    data = request.form if request.content_type and request.content_type.startswith('multipart/form-data') else (request.get_json(silent=True) or {})
    foto = request.files.get('evidencia') if request.files else None
    item = OrdenTrabajo.query.get_or_404(orden_id)
    if get_jwt().get('rol') == 'TECNICO' and item.tecnico_id != uid:
        return jsonify({'mensaje':'No autorizado.'}), 403
    item.estado = 'FINALIZADA'
    item.detalle_finalizacion = data.get('detalle_finalizacion') or item.detalle_finalizacion
    item.materiales_usados = data.get('materiales_usados') or item.materiales_usados
    item.fecha_finalizacion = data.get('fecha_finalizacion') or now_date_str()
    item.hora_finalizacion = data.get('hora_finalizacion') or now_time_str()
    item.latitud = to_float(data.get('latitud')) if data.get('latitud') is not None else item.latitud
    item.longitud = to_float(data.get('longitud')) if data.get('longitud') is not None else item.longitud
    if foto:
        ruta, original = save_upload(foto, 'seguimientos')
        db.session.add(OrdenEvidencia(orden_id=item.id, ruta_imagen=ruta, nombre_archivo=original, tipo_archivo=foto.mimetype, tamano_bytes=file_size_bytes(ruta), fecha=item.fecha_finalizacion, hora=item.hora_finalizacion, latitud=item.latitud, longitud=item.longitud, subido_por=uid))
    if item.incidencia:
        item.incidencia.estado = 'COMPLETADA'
        create_notification(item.incidencia.reportado_por, 'Incidencia completada', f'Se completó tu incidencia: {item.incidencia.titulo or item.incidencia.tipo_incidencia}', 'INCIDENCIA', 'incidencias', item.incidencia.id)
    create_notification(item.creado_por, 'Orden finalizada', f'La actividad {item.titulo} fue finalizada.', 'ORDEN_TECNICA', 'ordenes_trabajo', item.id)
    db.session.commit()
    return jsonify({'mensaje':'Orden finalizada correctamente.'})


@comunicaciones_bp.get('/ordenes/<int:orden_id>/imprimir')
@jwt_required()
def imprimir_orden(orden_id):
    item = OrdenTrabajo.query.get_or_404(orden_id)
    html = render_template('dashboard/orden_print.html', orden=item)
    path = f'instance/orden_{orden_id}.html'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return send_file(path, as_attachment=True, download_name=f'orden_{orden_id}.html')


@comunicaciones_bp.get('/ordenes/<int:orden_id>/evidencias')
@jwt_required()
def descargar_evidencias_orden(orden_id):
    item = OrdenTrabajo.query.get_or_404(orden_id)
    return jsonify({'orden_id': item.id, 'evidencias': [e.ruta_imagen for e in item.evidencias]})



@comunicaciones_bp.get('/ordenes/<int:orden_id>/respaldo')
@jwt_required()
def respaldo_orden(orden_id):
    item = OrdenTrabajo.query.get_or_404(orden_id)
    payload = {
        'orden_id': item.id,
        'titulo': item.titulo,
        'descripcion': item.descripcion,
        'estado': item.estado,
        'prioridad': item.prioridad,
        'fecha': item.fecha,
        'hora': item.hora,
        'latitud': item.latitud,
        'longitud': item.longitud,
        'detalle_finalizacion': item.detalle_finalizacion,
        'materiales_usados': item.materiales_usados,
        'fecha_finalizacion': item.fecha_finalizacion,
        'hora_finalizacion': item.hora_finalizacion,
        'tecnico': item.tecnico.nombre_completo if item.tecnico else None,
        'incidencia_id': item.incidencia_id,
        'evidencias': [
            {
                'ruta_imagen': e.ruta_imagen,
                'fecha': e.fecha,
                'hora': e.hora,
                'latitud': e.latitud,
                'longitud': e.longitud,
            }
            for e in item.evidencias
        ]
    }
    return jsonify(payload)
