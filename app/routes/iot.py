from __future__ import annotations
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Lectura, Medidor, Notificacion, Socio, Usuario
from app.utils import now_date_str, now_time_str, to_float, to_int

iot_bp = Blueprint('iot', __name__)


@iot_bp.post('/lectura')
def recibir_lectura_iot():
    data = request.get_json(silent=True) or {}
    medidor_id       = to_int(data.get('medidor_id'))
    vivienda_id      = to_int(data.get('vivienda_id'))
    socio_id         = to_int(data.get('socio_id'))
    lectura_actual   = to_float(data.get('lectura_actual'))
    lectura_anterior = to_float(data.get('lectura_anterior')) or 0
    caudal_lpm       = to_float(data.get('caudal_lpm')) or 0
    caudal_m3h       = to_float(data.get('caudal_m3h')) or 0
    flujo_activo     = data.get('flujo_activo', False)
    litros           = to_float(data.get('litros_consumidos')) or 0
    m3               = to_float(data.get('m3_consumidos')) or 0

    if not medidor_id or lectura_actual is None:
        return jsonify({'mensaje': 'medidor_id y lectura_actual son obligatorios'}), 400

    medidor = Medidor.query.get(medidor_id)
    if not medidor:
        return jsonify({'mensaje': 'Medidor no encontrado'}), 404

    fecha = now_date_str()
    hora  = now_time_str()

    lectura = Lectura(
        medidor_id        = medidor_id,
        vivienda_id       = vivienda_id or medidor.vivienda_id,
        socio_id          = socio_id or medidor.socio_id,
        tomado_por        = 1,
        lectura_anterior  = lectura_anterior,
        lectura_actual    = lectura_actual,
        consumo_calculado = m3,
        observacion       = f'IoT|Caudal:{caudal_lpm:.2f}L/min|{caudal_m3h:.4f}m³/h|{litros:.2f}L|{"ACTIVO" if flujo_activo else "DETENIDO"}',
        fecha_lectura     = fecha,
        hora_lectura      = hora,
        estado            = 'REGISTRADA',
    )
    db.session.add(lectura)
    db.session.commit()

    hora_int = int(hora.split(':')[0])
    if flujo_activo and 2 <= hora_int <= 4:
        _alerta(socio_id or medidor.socio_id,
            '⚠️ Fuga nocturna detectada',
            f'Flujo activo a las {hora}. Posible fuga en medidor {medidor.numero_medidor}.')

    if litros > 500:
        _alerta(socio_id or medidor.socio_id,
            '⚠️ Consumo excesivo',
            f'{litros:.1f} litros registrados en medidor {medidor.numero_medidor}.')

    return jsonify({
        'mensaje'   : 'Lectura IoT guardada.',
        'lectura_id': lectura.id,
        'litros'    : litros,
        'm3'        : m3,
    }), 201


@iot_bp.get('/estadisticas/<int:medidor_id>')
@jwt_required(optional=True)
def estadisticas_iot(medidor_id):
    lecturas = Lectura.query.filter_by(
        medidor_id=medidor_id
    ).order_by(Lectura.id.desc()).limit(50).all()

    total_m3     = sum(l.consumo_calculado or 0 for l in lecturas)
    total_litros = total_m3 * 1000

    por_dia = {}
    for l in lecturas:
        fecha = l.fecha_lectura or 'Sin fecha'
        por_dia[fecha] = por_dia.get(fecha, 0) + (l.consumo_calculado or 0)

    return jsonify({
        'medidor_id'    : medidor_id,
        'total_lecturas': len(lecturas),
        'total_m3'      : round(total_m3, 5),
        'total_litros'  : round(total_litros, 2),
        'por_dia'       : [{'fecha': k, 'm3': round(v, 5), 'litros': round(v*1000, 2)}
                          for k, v in sorted(por_dia.items(), reverse=True)],
        'ultimas'       : [{
            'id'         : l.id,
            'fecha'      : l.fecha_lectura,
            'hora'       : l.hora_lectura,
            'm3'         : l.consumo_calculado,
            'litros'     : (l.consumo_calculado or 0) * 1000,
            'observacion': l.observacion,
        } for l in lecturas[:10]],
    })


@iot_bp.get('/tiempo-real/<int:medidor_id>')
def tiempo_real(medidor_id):
    try:
        import requests
        r = requests.get('http://192.168.18.51/datos', timeout=3)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e), 'mensaje': 'ESP32 no disponible'}), 503


@iot_bp.get('/mi-medidor')
@jwt_required()
def mi_medidor():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    if not user.socio:
        return jsonify({'mensaje': 'No tienes socio asociado'}), 404
    medidor = Medidor.query.filter_by(socio_id=user.socio.id).first()
    if not medidor:
        return jsonify({'mensaje': 'No tienes medidor asociado'}), 404
    return jsonify({
        'medidor_id'    : medidor.id,
        'numero_medidor': medidor.numero_medidor,
        'vivienda_id'   : medidor.vivienda_id,
        'socio_id'      : user.socio.id,
        'esp32_ip'      : '192.168.18.51',
    })


def _alerta(socio_id, titulo, mensaje):
    try:
        socio = Socio.query.get(socio_id)
        if socio and socio.usuario_id:
            db.session.add(Notificacion(
                usuario_id = socio.usuario_id,
                titulo     = titulo,
                mensaje    = mensaje,
                tipo       = 'ALERTA',
                leido      = False,
                fecha      = now_date_str(),
                hora       = now_time_str(),
            ))
            db.session.commit()
    except Exception as e:
        print(f'Error alerta IoT: {e}')