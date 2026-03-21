from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from app.extensions import db
from app.models import MovimientoCaja, Pago, Recordatorio, Reunion, Usuario
from app.utils import create_notification, now_date_str, now_time_str, to_float, to_int

admin_extra_bp = Blueprint("admin_extra", __name__)


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


@admin_extra_bp.get('/pagos')
@jwt_required()
def list_pagos():
    uid = int(get_jwt_identity())
    user = Usuario.query.get_or_404(uid)
    q = Pago.query.order_by(Pago.id.desc())
    if user.rol.nombre == 'SOCIO' and user.socio:
        q = q.filter_by(socio_id=user.socio.id)
    elif user.rol.nombre == 'TECNICO' and user.socio:
        q = q.filter_by(socio_id=user.socio.id)
    return jsonify([{
        'id': p.id, 'planilla_id': p.planilla_id, 'socio_id': p.socio_id, 'vivienda_id': p.vivienda_id,
        'valor_pagado': p.valor_pagado, 'fecha_pago': p.fecha_pago, 'hora_pago': p.hora_pago,
        'metodo_pago': p.metodo_pago, 'referencia_pago': p.referencia_pago, 'observacion': p.observacion,
        'registrado_por': p.usuario.nombre_completo if p.usuario else None
    } for p in q.all()])


@admin_extra_bp.get('/movimientos-caja')
@jwt_required()
@require_roles('ADMIN')
def list_movimientos_caja():
    q = MovimientoCaja.query.order_by(MovimientoCaja.id.desc())
    return jsonify([{
        'id': m.id, 'tipo_movimiento': m.tipo_movimiento, 'categoria': m.categoria, 'descripcion': m.descripcion,
        'monto': m.monto, 'fecha': m.fecha, 'hora': m.hora, 'registrado_por': m.usuario.nombre_completo if m.usuario else None
    } for m in q.all()])


@admin_extra_bp.route('/reuniones', methods=['GET', 'POST'])
@jwt_required()
def reuniones():
    if request.method == 'GET':
        return jsonify([{
            'id': r.id, 'titulo': r.titulo, 'descripcion': r.descripcion, 'lugar': r.lugar, 'fecha': r.fecha, 'hora': r.hora, 'estado': r.estado
        } for r in Reunion.query.order_by(Reunion.fecha.desc(), Reunion.hora.desc()).all()])
    if get_jwt().get('rol') != 'ADMIN':
        return jsonify({'mensaje':'No autorizado para esta acción.'}), 403
    data = request.get_json(silent=True) or {}
    r = Reunion(junta_id=1, creado_por=int(get_jwt_identity()), titulo=data.get('titulo') or 'Reunión', descripcion=data.get('descripcion'), lugar=data.get('lugar'), fecha=data.get('fecha') or now_date_str(), hora=data.get('hora') or now_time_str(), estado=data.get('estado') or 'PROGRAMADA')
    db.session.add(r)
    db.session.flush()
    for u in Usuario.query.all():
        create_notification(u.id, 'Nueva reunión', f'Se programó la reunión: {r.titulo}', 'COMUNICADO', 'reuniones', r.id)
    db.session.commit()
    return jsonify({'mensaje':'Reunión creada correctamente.', 'id': r.id}), 201


@admin_extra_bp.put('/reuniones/<int:reunion_id>')
@jwt_required()
@require_roles('ADMIN')
def update_reunion(reunion_id):
    r = Reunion.query.get_or_404(reunion_id)
    data = request.get_json(silent=True) or {}
    r.titulo = data.get('titulo') or r.titulo
    r.descripcion = data.get('descripcion') if 'descripcion' in data else r.descripcion
    r.lugar = data.get('lugar') if 'lugar' in data else r.lugar
    r.fecha = data.get('fecha') or r.fecha
    r.hora = data.get('hora') or r.hora
    r.estado = data.get('estado') or r.estado
    db.session.commit()
    return jsonify({'mensaje':'Reunión actualizada correctamente.'})


@admin_extra_bp.delete('/reuniones/<int:reunion_id>')
@jwt_required()
@require_roles('ADMIN')
def delete_reunion(reunion_id):
    r = Reunion.query.get_or_404(reunion_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({'mensaje':'Reunión eliminada correctamente.'})


@admin_extra_bp.route('/recordatorios', methods=['GET', 'POST'])
@jwt_required()
def recordatorios():
    uid = int(get_jwt_identity())
    if request.method == 'GET':
        q = Recordatorio.query.order_by(Recordatorio.fecha.desc(), Recordatorio.hora.desc())
        if get_jwt().get('rol') != 'ADMIN':
            q = q.filter_by(usuario_id=uid)
        return jsonify([{'id': x.id, 'usuario_id': x.usuario_id, 'titulo': x.titulo, 'descripcion': x.descripcion, 'tipo': x.tipo, 'fecha': x.fecha, 'hora': x.hora, 'enviado': x.enviado} for x in q.all()])
    if get_jwt().get('rol') != 'ADMIN':
        return jsonify({'mensaje':'No autorizado para esta acción.'}), 403
    data = request.get_json(silent=True) or {}
    user_id = to_int(data.get('usuario_id'))
    if not user_id:
        return jsonify({'mensaje':'usuario_id es obligatorio.'}), 400
    x = Recordatorio(usuario_id=user_id, titulo=data.get('titulo') or 'Recordatorio', descripcion=data.get('descripcion'), tipo=data.get('tipo') or 'SISTEMA', fecha=data.get('fecha') or now_date_str(), hora=data.get('hora') or now_time_str(), enviado=False)
    db.session.add(x)
    db.session.flush()
    create_notification(user_id, x.titulo, x.descripcion or 'Tienes un nuevo recordatorio.', x.tipo, 'recordatorios', x.id)
    db.session.commit()
    return jsonify({'mensaje':'Recordatorio creado correctamente.', 'id': x.id}), 201


@admin_extra_bp.put('/recordatorios/<int:recordatorio_id>')
@jwt_required()
@require_roles('ADMIN')
def update_recordatorio(recordatorio_id):
    x = Recordatorio.query.get_or_404(recordatorio_id)
    data = request.get_json(silent=True) or {}
    x.titulo = data.get('titulo') or x.titulo
    x.descripcion = data.get('descripcion') if 'descripcion' in data else x.descripcion
    x.tipo = data.get('tipo') or x.tipo
    x.fecha = data.get('fecha') or x.fecha
    x.hora = data.get('hora') or x.hora
    x.enviado = bool(data.get('enviado', x.enviado))
    db.session.commit()
    return jsonify({'mensaje':'Recordatorio actualizado correctamente.'})


@admin_extra_bp.delete('/recordatorios/<int:recordatorio_id>')
@jwt_required()
@require_roles('ADMIN')
def delete_recordatorio(recordatorio_id):
    x = Recordatorio.query.get_or_404(recordatorio_id)
    db.session.delete(x)
    db.session.commit()
    return jsonify({'mensaje':'Recordatorio eliminado correctamente.'})


@admin_extra_bp.post('/movimientos-caja/egreso')
@jwt_required()
@require_roles('ADMIN')
def create_egreso():
    data = request.get_json(silent=True) or {}
    monto = to_float(data.get('monto'))
    if not monto or monto <= 0:
        return jsonify({'mensaje':'monto válido es obligatorio.'}), 400
    mov = MovimientoCaja(
        tipo_movimiento='EGRESO',
        categoria=data.get('categoria') or 'GENERAL',
        referencia_tabla=data.get('referencia_tabla'),
        referencia_id=to_int(data.get('referencia_id')),
        descripcion=data.get('descripcion') or 'Egreso registrado',
        monto=monto,
        fecha=data.get('fecha') or now_date_str(),
        hora=data.get('hora') or now_time_str(),
        registrado_por=int(get_jwt_identity()),
    )
    db.session.add(mov)
    db.session.commit()
    return jsonify({'mensaje':'Egreso registrado correctamente.', 'id': mov.id}), 201


@admin_extra_bp.get('/movimientos-caja/resumen')
@jwt_required()
@require_roles('ADMIN')
def resumen_movimientos_caja():
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    categoria = request.args.get('categoria')
    q = MovimientoCaja.query
    if desde:
        q = q.filter(MovimientoCaja.fecha >= desde)
    if hasta:
        q = q.filter(MovimientoCaja.fecha <= hasta)
    if categoria:
        q = q.filter(MovimientoCaja.categoria == categoria)
    items = q.order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.hora.desc()).all()
    ingresos = sum(float(x.monto or 0) for x in items if x.tipo_movimiento == 'INGRESO')
    egresos = sum(float(x.monto or 0) for x in items if x.tipo_movimiento == 'EGRESO')
    return jsonify({
        'total_registros': len(items),
        'ingresos': ingresos,
        'egresos': egresos,
        'saldo': ingresos - egresos,
        'items': [{
            'id': x.id, 'tipo_movimiento': x.tipo_movimiento, 'categoria': x.categoria, 'descripcion': x.descripcion,
            'monto': x.monto, 'fecha': x.fecha, 'hora': x.hora, 'registrado_por': x.usuario.nombre_completo if x.usuario else None
        } for x in items]
    })


@admin_extra_bp.post('/movimientos-caja/cierre')
@jwt_required()
@require_roles('ADMIN')
def cierre_caja():
    data = request.get_json(silent=True) or {}
    fecha = data.get('fecha') or now_date_str()
    items = MovimientoCaja.query.filter_by(fecha=fecha).order_by(MovimientoCaja.hora.asc()).all()
    ingresos = sum(float(x.monto or 0) for x in items if x.tipo_movimiento == 'INGRESO')
    egresos = sum(float(x.monto or 0) for x in items if x.tipo_movimiento == 'EGRESO')
    return jsonify({
        'fecha': fecha,
        'ingresos': ingresos,
        'egresos': egresos,
        'saldo': ingresos - egresos,
        'cantidad_movimientos': len(items),
        'detalle': [{
            'id': x.id, 'tipo_movimiento': x.tipo_movimiento, 'categoria': x.categoria, 'descripcion': x.descripcion,
            'monto': x.monto, 'hora': x.hora
        } for x in items]
    })
