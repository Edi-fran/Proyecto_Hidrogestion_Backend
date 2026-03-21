from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.extensions import db
from app.models import MovimientoCaja, Pago, Planilla, Usuario, Vivienda
from app.utils import now_date_str

aportes_bp = Blueprint('aportes', __name__)

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


@aportes_bp.post('')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def create_aporte():
    data = request.get_json(silent=True) or {}
    vivienda = Vivienda.query.get(data.get('vivienda_id'))
    if not vivienda or not vivienda.socio_id:
        return jsonify({'mensaje': 'Vivienda no válida.'}), 400
    periodo_anio = int(data.get('periodo_anio') or 2026)
    periodo_mes = int(data.get('periodo_mes') or 1)
    item = Planilla(
        socio_id=vivienda.socio_id,
        vivienda_id=vivienda.id,
        periodo_anio=periodo_anio,
        periodo_mes=periodo_mes,
        numero_planilla=f"PLA-{vivienda.id}-{periodo_anio}-{periodo_mes}",
        fecha_emision=now_date_str(),
        fecha_vencimiento=data.get('fecha_vencimiento'),
        lectura_anterior=0,
        lectura_actual=0,
        consumo_m3=0,
        cargo_fijo=0,
        valor_m3=0,
        subtotal_consumo=float(data.get('valor') or 0),
        recargo=0,
        multa=0,
        otros=0,
        total_pagar=float(data.get('valor') or 0),
        estado=data.get('estado_pago') or 'PENDIENTE'
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'mensaje': 'Aporte registrado correctamente.', 'id': item.id}), 201


@aportes_bp.get('')
@jwt_required()
def list_aportes():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    if user.rol.nombre == 'SOCIO' and user.socio:
        planillas = Planilla.query.filter_by(socio_id=user.socio.id).order_by(Planilla.id.desc()).all()
    else:
        planillas = Planilla.query.order_by(Planilla.id.desc()).all()
    return jsonify([{'id': p.id, 'numero_planilla': p.numero_planilla, 'periodo_anio': p.periodo_anio, 'periodo_mes': p.periodo_mes, 'consumo_m3': p.consumo_m3, 'total_pagar': p.total_pagar, 'estado': p.estado, 'fecha_emision': p.fecha_emision, 'fecha_pago': p.fecha_pago} for p in planillas])


@aportes_bp.get('/recaudacion-resumen')
@jwt_required()
def recaudacion_resumen():
    total_recaudado = sum(m.monto for m in MovimientoCaja.query.filter_by(tipo_movimiento='INGRESO').all())
    total_pendiente = sum(p.total_pagar for p in Planilla.query.filter(Planilla.estado != 'PAGADO').all())
    total_pagadas = Planilla.query.filter_by(estado='PAGADO').count()
    return jsonify({'total_recaudado': total_recaudado, 'total_pendiente': total_pendiente, 'planillas_pagadas': total_pagadas, 'pagos_registrados': Pago.query.count()})
