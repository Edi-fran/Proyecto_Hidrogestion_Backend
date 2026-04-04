from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.extensions import db
from app.models import MovimientoCaja, Pago, Planilla, Usuario, TarifaAsignada, Notificacion
from app.utils import now_date_str, now_time_str, create_notification, sync_system_alerts

planillas_bp = Blueprint('planillas', __name__)


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


@planillas_bp.get('')
@jwt_required()
def list_planillas():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    q = Planilla.query.order_by(Planilla.id.desc())
    if user.rol.nombre == 'SOCIO' and user.socio:
        q = q.filter_by(socio_id=user.socio.id)
    return jsonify([{'id': p.id, 'numero_planilla': p.numero_planilla, 'socio': p.socio.usuario.nombre_completo if p.socio and p.socio.usuario else None, 'periodo_anio': p.periodo_anio, 'periodo_mes': p.periodo_mes, 'consumo_m3': p.consumo_m3, 'total_pagar': p.total_pagar, 'estado': p.estado, 'fecha_emision': p.fecha_emision, 'fecha_pago': p.fecha_pago} for p in q.all()])


@planillas_bp.post('/<int:planilla_id>/marcar-pagado')
@jwt_required()
@require_roles('ADMIN')
def marcar_pagado(planilla_id):
    planilla = Planilla.query.get_or_404(planilla_id)
    data = request.get_json(silent=True) or {}
    fecha = data.get('fecha_pago') or now_date_str()
    hora = data.get('hora_pago') or now_time_str()
    planilla.estado = 'PAGADO'
    planilla.fecha_pago = fecha
    planilla.hora_pago = hora
    planilla.metodo_pago = data.get('metodo_pago') or 'EFECTIVO'
    planilla.referencia_pago = data.get('referencia_pago')
    pago = Pago(planilla_id=planilla.id, socio_id=planilla.socio_id, vivienda_id=planilla.vivienda_id, valor_pagado=data.get('valor_pagado') or planilla.total_pagar, fecha_pago=fecha, hora_pago=hora, metodo_pago=planilla.metodo_pago, referencia_pago=planilla.referencia_pago, registrado_por=int(get_jwt_identity()), observacion=data.get('observacion'))
    db.session.add(pago)
    db.session.flush()
    db.session.add(MovimientoCaja(tipo_movimiento='INGRESO', categoria='AGUA', referencia_tabla='pagos', referencia_id=pago.id, descripcion=f'Cobro planilla {planilla.numero_planilla}', monto=float(data.get('valor_pagado') or planilla.total_pagar), fecha=fecha, hora=hora, registrado_por=int(get_jwt_identity())))
    create_notification(planilla.socio.usuario_id, 'Planilla pagada', f'Se registró el pago de la planilla {planilla.numero_planilla}.', 'PAGO', 'planillas', planilla.id)
    db.session.commit()
    return jsonify({'mensaje': 'Planilla marcada como pagada.', 'pago_id': pago.id})


@planillas_bp.get('/<int:planilla_id>/descargar')
@jwt_required(optional=True)
def descargar_planilla(planilla_id):
    import os
    from flask_jwt_extended import decode_token
    token_param = request.args.get('access_token')
    if token_param:
        try:
            data = decode_token(token_param)
            usuario_id = int(data['sub'])
        except Exception:
            return jsonify({'mensaje': 'Token inválido.'}), 401
    else:
        usuario_id = int(get_jwt_identity())
    planilla = Planilla.query.get_or_404(planilla_id)
    user = Usuario.query.get_or_404(usuario_id)
    if user.rol.nombre == 'SOCIO' and (not user.socio or user.socio.id != planilla.socio_id):
        return jsonify({'mensaje': 'No autorizado.'}), 403
    html = render_template('dashboard/planilla_print.html', planilla=planilla)
    carpeta = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'instance'))
    os.makedirs(carpeta, exist_ok=True)
    path = os.path.join(carpeta, f'planilla_{planilla.id}.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return send_file(path, as_attachment=False, download_name=f'{planilla.numero_planilla}.html')


@planillas_bp.put('/<int:planilla_id>/estado')
@jwt_required()
@require_roles('ADMIN')
def cambiar_estado_planilla(planilla_id):
    planilla = Planilla.query.get_or_404(planilla_id)
    data = request.get_json(silent=True) or {}
    nuevo_estado = (data.get('estado') or '').upper()
    if nuevo_estado not in {'PENDIENTE','PAGADO','VENCIDO','ANULADO'}:
        return jsonify({'mensaje':'Estado inválido.'}), 400
    planilla.estado = nuevo_estado
    if nuevo_estado == 'VENCIDO' and planilla.multa == 0:
        asignada = TarifaAsignada.query.filter_by(vivienda_id=planilla.vivienda_id, estado='ACTIVA').order_by(TarifaAsignada.id.desc()).first()
        multa = float(asignada.multa_atraso if asignada else 0)
        planilla.multa = multa
        planilla.total_pagar = float(planilla.subtotal_consumo or 0) + float(planilla.cargo_fijo or 0) + float(planilla.recargo or 0) + float(planilla.otros or 0) + multa
    db.session.commit()
    return jsonify({'mensaje':'Estado actualizado correctamente.', 'estado': planilla.estado, 'total_pagar': planilla.total_pagar, 'multa': planilla.multa})


@planillas_bp.post('/<int:planilla_id>/recalcular')
@jwt_required()
@require_roles('ADMIN')
def recalcular_planilla(planilla_id):
    planilla = Planilla.query.get_or_404(planilla_id)
    consumo = planilla.consumo or (planilla.lectura.consumo if planilla.lectura and hasattr(planilla.lectura, 'consumo') else None)
    if not consumo:
        return jsonify({'mensaje':'No existe consumo asociado.'}), 400
    asignada = TarifaAsignada.query.filter_by(vivienda_id=planilla.vivienda_id, estado='ACTIVA').order_by(TarifaAsignada.id.desc()).first()
    if asignada:
        excedente = max(0, float(consumo.consumo_m3 or 0) - float(asignada.base_consumo_m3 or 0))
        subtotal = float(asignada.valor_base or 0) + excedente * float(asignada.valor_adicional_m3 or 0)
        consumo.cargo_fijo = float(asignada.valor_base or 0)
        consumo.valor_m3 = float(asignada.valor_adicional_m3 or 0)
        consumo.subtotal_consumo = subtotal
        consumo.total_pagar = subtotal + float(consumo.multa or 0)
        planilla.cargo_fijo = consumo.cargo_fijo
        planilla.valor_m3 = consumo.valor_m3
        planilla.subtotal_consumo = subtotal
        planilla.total_pagar = subtotal + float(planilla.multa or 0) + float(planilla.recargo or 0) + float(planilla.otros or 0)
    db.session.commit()
    return jsonify({'mensaje':'Planilla recalculada.', 'total_pagar': planilla.total_pagar})

@planillas_bp.get('/estadistica-semestral')
@jwt_required()
def estadistica_semestral():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    q = Planilla.query.order_by(Planilla.periodo_anio.desc(), Planilla.periodo_mes.desc())
    if user.rol.nombre == 'SOCIO' and user.socio:
        q = q.filter_by(socio_id=user.socio.id)
    elif user.rol.nombre == 'TECNICO' and user.socio:
        q = q.filter_by(socio_id=user.socio.id)
    items = q.limit(6).all()[::-1]
    return jsonify([{
        'etiqueta': f"{i.periodo_mes:02d}/{i.periodo_anio}", 'consumo_m3': i.consumo_m3, 'total_pagar': i.total_pagar, 'estado': i.estado
    } for i in items])


@planillas_bp.post('/sincronizar-alertas')
@jwt_required()
def sincronizar_alertas_planillas():
    result = sync_system_alerts()
    return jsonify({'mensaje':'Alertas sincronizadas.', **result})



@planillas_bp.get('/<int:planilla_id>/comprobante')
@jwt_required()
def comprobante_pago(planilla_id):
    planilla = Planilla.query.get_or_404(planilla_id)
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    if user.rol.nombre == 'SOCIO' and (not user.socio or user.socio.id != planilla.socio_id):
        return jsonify({'mensaje': 'No autorizado.'}), 403
    if planilla.estado != 'PAGADO':
        return jsonify({'mensaje': 'La planilla aún no está pagada.'}), 400
    html = render_template('dashboard/planilla_print.html', planilla=planilla)
    import os
    carpeta = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'instance'))
    os.makedirs(carpeta, exist_ok=True)
    path = os.path.join(carpeta, f'comprobante_{planilla.id}.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return send_file(path, as_attachment=True, download_name=f'comprobante_{planilla.numero_planilla}.html')
