from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.extensions import db
from app.models import Auditoria, Consumo, Lectura, LecturaEvidencia, Medidor, Planilla, ReclamoLectura, RutaLecturacion, RutaMedidor, Socio, Tarifa, TarifaAsignada, Usuario, Vivienda
from app.utils import export_csv, file_size_bytes, now_date_str, now_time_str, save_upload, to_float, to_int, create_notification

lecturas_bp = Blueprint('lecturas', __name__)


def require_roles(*allowed):
    def decorator(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            rol = get_jwt().get('rol')
            if rol not in allowed:
                return jsonify({'mensaje': 'No autorizado para esta acción.'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _find_medidor(data):
    medidor_id = to_int(data.get('medidor_id'))
    if medidor_id:
        return Medidor.query.get_or_404(medidor_id)
    numero_medidor = data.get('numero_medidor')
    if numero_medidor:
        item = Medidor.query.filter_by(numero_medidor=numero_medidor).first()
        if item:
            return item
    cedula = data.get('cedula')
    if cedula:
        return Medidor.query.join(Socio, Medidor.socio_id == Socio.id).join(Usuario, Socio.usuario_id == Usuario.id).filter(Usuario.cedula == cedula).first_or_404()
    vivienda_id = to_int(data.get('vivienda_id'))
    if vivienda_id:
        return Medidor.query.filter_by(vivienda_id=vivienda_id).first_or_404()
    return None


def _indicator(consumo):
    if consumo <= 10:
        return 'BAJO'
    if consumo <= 20:
        return 'MEDIO'
    if consumo <= 30:
        return 'ALTO'
    return 'CRITICO'


def _active_tarifa():
    return Tarifa.query.filter_by(estado='ACTIVA').order_by(Tarifa.id.desc()).first()


def _tarifa_para_vivienda(socio_id, vivienda_id):
    personalizada = TarifaAsignada.query.filter_by(vivienda_id=vivienda_id, estado='ACTIVA').order_by(TarifaAsignada.id.desc()).first()
    if personalizada:
        return personalizada
    personalizada = TarifaAsignada.query.filter_by(socio_id=socio_id, estado='ACTIVA').order_by(TarifaAsignada.id.desc()).first()
    return personalizada


def _calcular_cobro(consumo, socio_id, vivienda_id):
    asignada = _tarifa_para_vivienda(socio_id, vivienda_id)
    if asignada:
        excedente = max(0, consumo - (asignada.base_consumo_m3 or 0))
        subtotal = float(asignada.valor_base or 0) + (excedente * float(asignada.valor_adicional_m3 or 0))
        return {
            'tarifa_id': asignada.tarifa_id,
            'cargo_fijo': float(asignada.valor_base or 0),
            'valor_m3': float(asignada.valor_adicional_m3 or 0),
            'subtotal': subtotal,
            'multa': 0.0,
            'otros': 0.0,
            'base_consumo_m3': float(asignada.base_consumo_m3 or 0),
            'nombre': asignada.nombre,
        }
    tarifa = _active_tarifa()
    excedente = max(0, consumo - 10)
    subtotal = float(tarifa.cargo_fijo if tarifa else 2.0) + (excedente * float(tarifa.valor_m3 if tarifa else 0.5))
    return {
        'tarifa_id': tarifa.id if tarifa else None,
        'cargo_fijo': float(tarifa.cargo_fijo if tarifa else 2.0),
        'valor_m3': float(tarifa.valor_m3 if tarifa else 0.5),
        'subtotal': subtotal,
        'multa': 0.0,
        'otros': 0.0,
        'base_consumo_m3': 10.0,
        'nombre': tarifa.nombre if tarifa else 'Tarifa general',
    }


@lecturas_bp.get('/medidores-disponibles')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def medidores_disponibles():
    user_id = int(get_jwt_identity())
    rol = get_jwt().get('rol')
    q = request.args.get('q', '').strip()
    sector_id = to_int(request.args.get('sector_id'))
    query = Medidor.query.join(Vivienda).join(Medidor.socio).join(Usuario)
    if rol == 'TECNICO':
        query = query.join(RutaMedidor, RutaMedidor.medidor_id == Medidor.id).join(RutaLecturacion, RutaLecturacion.id == RutaMedidor.ruta_id).filter(RutaLecturacion.tecnico_id == user_id)
    if q:
        query = query.filter((Medidor.numero_medidor.contains(q)) | (Usuario.cedula.contains(q)) | (Usuario.nombres.contains(q)) | (Usuario.apellidos.contains(q)))
    if sector_id:
        query = query.filter(Vivienda.sector_id == sector_id)
    return jsonify([{'id': m.id, 'numero_medidor': m.numero_medidor, 'cedula': m.socio.usuario.cedula, 'socio': m.socio.usuario.nombre_completo, 'direccion': m.vivienda.direccion, 'sector': m.vivienda.sector.nombre if m.vivienda.sector else None, 'latitud': m.vivienda.latitud, 'longitud': m.vivienda.longitud} for m in query.order_by(Medidor.numero_medidor).all()])


@lecturas_bp.post('')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def create_lectura():
    data = request.form if request.content_type and request.content_type.startswith('multipart/form-data') else (request.get_json(silent=True) or {})
    foto = request.files.get('evidencia') if request.files else None
    medidor = _find_medidor(data)
    if not medidor:
        return jsonify({'mensaje': 'Debe enviar medidor_id, numero_medidor o cedula.'}), 400
    vivienda = medidor.vivienda
    socio = medidor.socio
    ultima = Lectura.query.filter_by(medidor_id=medidor.id).order_by(Lectura.id.desc()).first()
    lectura_anterior = ultima.lectura_actual if ultima else (to_float(data.get('lectura_anterior')) or 0)
    lectura_actual = to_float(data.get('lectura_actual'))
    if lectura_actual is None:
        return jsonify({'mensaje': 'lectura_actual es obligatoria.'}), 400
    consumo = max(0, lectura_actual - (lectura_anterior or 0))
    fecha = data.get('fecha_lectura') or now_date_str()
    hora = data.get('hora_lectura') or now_time_str()
    lectura = Lectura(medidor_id=medidor.id, vivienda_id=vivienda.id, socio_id=socio.id, tomado_por=int(get_jwt_identity()), lectura_anterior=lectura_anterior, lectura_actual=lectura_actual, consumo_calculado=consumo, observacion=data.get('observacion'), fecha_lectura=fecha, hora_lectura=hora, latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')), estado=data.get('estado', 'REGISTRADA'))
    db.session.add(lectura)
    db.session.commit()
    cobro = _calcular_cobro(consumo, socio.id, vivienda.id)
    subtotal = cobro['subtotal']
    total = subtotal + cobro.get('multa', 0) + cobro.get('otros', 0)
    anio = int(datetime.now().strftime('%Y'))
    mes = int(datetime.now().strftime('%m'))
    consumo_row = Consumo(lectura_id=lectura.id, vivienda_id=vivienda.id, socio_id=socio.id, periodo_anio=anio, periodo_mes=mes, lectura_inicial=lectura_anterior, lectura_final=lectura_actual, consumo_m3=consumo, tarifa_id=cobro['tarifa_id'], cargo_fijo=cobro['cargo_fijo'], valor_m3=cobro['valor_m3'], subtotal_consumo=subtotal, multa=cobro.get('multa', 0), total_pagar=total, indicador=_indicator(consumo), observacion=f"Generado automáticamente desde lectura. {cobro['nombre']}")
    db.session.add(consumo_row)
    db.session.commit()
    numero = f'PLN-{anio}{mes:02d}-{vivienda.id:04d}'
    planilla = Planilla.query.filter_by(vivienda_id=vivienda.id, periodo_anio=anio, periodo_mes=mes).first()
    if not planilla:
        planilla = Planilla(socio_id=socio.id, vivienda_id=vivienda.id, lectura_id=lectura.id, consumo_id=consumo_row.id, periodo_anio=anio, periodo_mes=mes, numero_planilla=numero, fecha_emision=fecha, fecha_vencimiento=(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'), lectura_anterior=lectura_anterior, lectura_actual=lectura_actual, consumo_m3=consumo, cargo_fijo=consumo_row.cargo_fijo, valor_m3=consumo_row.valor_m3, subtotal_consumo=subtotal, multa=consumo_row.multa, total_pagar=total, estado='PENDIENTE')
        db.session.add(planilla)
    else:
        planilla.lectura_id = lectura.id
        planilla.consumo_id = consumo_row.id
        planilla.lectura_anterior = lectura_anterior
        planilla.lectura_actual = lectura_actual
        planilla.consumo_m3 = consumo
        planilla.cargo_fijo = consumo_row.cargo_fijo
        planilla.valor_m3 = consumo_row.valor_m3
        planilla.subtotal_consumo = subtotal
        planilla.multa = consumo_row.multa
        planilla.total_pagar = total
    evidencia_data = None
    if foto:
        ruta, original = save_upload(foto, 'lecturas')
        evidencia = LecturaEvidencia(lectura_id=lectura.id, ruta_imagen=ruta, nombre_archivo=original, tipo_archivo=foto.mimetype, tamano_bytes=file_size_bytes(ruta), fecha=fecha, hora=hora, latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')), subido_por=int(get_jwt_identity()))
        db.session.add(evidencia)
        evidencia_data = ruta
    create_notification(socio.usuario_id, 'Nueva lectura registrada', f'Se registró una lectura de {consumo} m³. Planilla: {planilla.numero_planilla}', 'LECTURA', 'lecturas', lectura.id)
    db.session.commit()
    return jsonify({'mensaje': 'Lectura registrada correctamente.', 'id': lectura.id, 'consumo': consumo, 'total_planilla': total, 'planilla_numero': planilla.numero_planilla, 'evidencia': evidencia_data}), 201


@lecturas_bp.get('')
@jwt_required()
def list_lecturas():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    q = Lectura.query.order_by(Lectura.id.desc())
    if user.rol.nombre == 'SOCIO' and user.socio:
        q = q.filter_by(socio_id=user.socio.id)
    lecturas = q.all()
    return jsonify([{'id': l.id, 'socio': l.socio.usuario.nombre_completo if l.socio and l.socio.usuario else None, 'cedula': l.socio.usuario.cedula if l.socio and l.socio.usuario else None, 'medidor': l.medidor.numero_medidor if l.medidor else None, 'direccion': l.vivienda.direccion if l.vivienda else None, 'lectura_anterior': l.lectura_anterior, 'lectura_actual': l.lectura_actual, 'consumo_calculado': l.consumo_calculado, 'indicador': l.consumo.indicador if l.consumo else None, 'fecha_lectura': l.fecha_lectura, 'hora_lectura': l.hora_lectura, 'latitud': l.latitud, 'longitud': l.longitud, 'estado': l.estado, 'observacion': l.observacion, 'evidencias': [e.ruta_imagen for e in l.evidencias]} for l in lecturas])


@lecturas_bp.get('/reporte.csv')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def export_lecturas_csv():
    lecturas = Lectura.query.order_by(Lectura.id.desc()).all()
    path = Path('instance/reportes/lecturas.csv')
    path.parent.mkdir(parents=True, exist_ok=True)
    export_csv(path, ['ID', 'Cedula', 'Socio', 'Medidor', 'Direccion', 'Anterior', 'Actual', 'Consumo', 'Fecha', 'Hora', 'Latitud', 'Longitud'], [[l.id, l.socio.usuario.cedula if l.socio and l.socio.usuario else '', l.socio.usuario.nombre_completo if l.socio and l.socio.usuario else '', l.medidor.numero_medidor if l.medidor else '', l.vivienda.direccion if l.vivienda else '', l.lectura_anterior, l.lectura_actual, l.consumo_calculado, l.fecha_lectura, l.hora_lectura, l.latitud, l.longitud] for l in lecturas])
    return send_file(path, as_attachment=True, download_name='lecturas.csv')


@lecturas_bp.put('/<int:lectura_id>')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def update_lectura(lectura_id):
    item = Lectura.query.get_or_404(lectura_id)
    data = request.get_json(silent=True) or {}
    for field in ['observacion', 'estado']:
        if field in data:
            setattr(item, field, data.get(field))
    if 'lectura_actual' in data:
        nueva = to_float(data.get('lectura_actual'))
        if nueva is not None:
            item.lectura_actual = nueva
            item.consumo_calculado = max(0, nueva - (item.lectura_anterior or 0))
            if item.consumo:
                item.consumo.lectura_final = nueva
                item.consumo.consumo_m3 = item.consumo_calculado
                item.consumo.subtotal_consumo = item.consumo_calculado * (item.consumo.valor_m3 or 0)
                item.consumo.total_pagar = item.consumo.subtotal_consumo + (item.consumo.cargo_fijo or 0) + (item.consumo.recargo or 0) + (item.consumo.multa or 0)
                item.consumo.indicador = _indicator(item.consumo_calculado)
                planilla = Planilla.query.filter_by(consumo_id=item.consumo.id).first()
                if planilla and planilla.estado != 'PAGADO':
                    planilla.lectura_actual = nueva
                    planilla.consumo_m3 = item.consumo_calculado
                    planilla.subtotal_consumo = item.consumo.subtotal_consumo
                    planilla.total_pagar = item.consumo.total_pagar
    db.session.commit()
    return jsonify({'mensaje': 'Lectura actualizada correctamente.'})


@lecturas_bp.delete('/<int:lectura_id>')
@jwt_required()
@require_roles('ADMIN')
def delete_lectura(lectura_id):
    item = Lectura.query.get_or_404(lectura_id)
    item.estado = 'ANULADA'
    planilla = Planilla.query.filter_by(lectura_id=item.id).first()
    if planilla and planilla.estado != 'PAGADO':
        planilla.estado = 'ANULADO'
        planilla.observacion = ((planilla.observacion or '') + ' | Anulada por administración').strip()
    db.session.commit()
    return jsonify({'mensaje': 'Lectura anulada correctamente.'})


@lecturas_bp.post('/<int:lectura_id>/reclamar')
@jwt_required()
def reclamar_lectura(lectura_id):
    lectura = Lectura.query.get_or_404(lectura_id)
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    data = request.get_json(silent=True) or {}
    motivo = (data.get('motivo') or 'RECLAMO DE LECTURA').strip()
    descripcion = data.get('descripcion')
    reclamo = ReclamoLectura(lectura_id=lectura.id, reportado_por=user.id, motivo=motivo, descripcion=descripcion, estado='ABIERTO', fecha=now_date_str(), hora=now_time_str())
    lectura.estado = 'OBSERVADA'
    db.session.add(reclamo)
    admins = Usuario.query.join(Usuario.rol).filter_by(nombre='ADMIN').all()
    for admin in admins:
        create_notification(admin.id, 'Reclamo de lectura', f'Se reportó un reclamo para la lectura {lectura.id}. Motivo: {motivo}', 'LECTURA', 'lecturas', lectura.id)
    db.session.commit()
    return jsonify({'mensaje': 'Reclamo registrado correctamente.', 'reclamo_id': reclamo.id})


@lecturas_bp.post('/<int:lectura_id>/anular-recalcular')
@jwt_required()
@require_roles('ADMIN')
def anular_recalcular_lectura(lectura_id):
    lectura = Lectura.query.get_or_404(lectura_id)
    data = request.get_json(silent=True) or {}
    motivo = data.get('motivo') or 'Corrección de lectura'
    corrected = to_float(data.get('lectura_correcta'))
    lectura.estado = 'ANULADA'
    if lectura.consumo:
        lectura.consumo.observacion = (lectura.consumo.observacion or '') + f' | Anulada: {motivo}'
    for p in Planilla.query.filter_by(lectura_id=lectura.id).all():
        if p.estado != 'PAGADO':
            p.estado = 'ANULADO'
            p.observacion = ((p.observacion or '') + f' | Anulada por corrección: {motivo}').strip()
    db.session.add(Auditoria(usuario_id=int(get_jwt_identity()), tabla_afectada='lecturas', registro_id=lectura.id, accion='ANULAR', detalle=motivo, fecha=now_date_str(), hora=now_time_str(), ip=request.remote_addr))

    nueva_id = None
    if corrected is not None:
        medidor = lectura.medidor
        vivienda = lectura.vivienda
        socio = lectura.socio
        lectura_anterior = lectura.lectura_anterior or 0
        consumo = max(0, corrected - lectura_anterior)
        nueva = Lectura(medidor_id=medidor.id if medidor else None, vivienda_id=vivienda.id, socio_id=socio.id, tomado_por=int(get_jwt_identity()), lectura_anterior=lectura_anterior, lectura_actual=corrected, consumo_calculado=consumo, observacion=f'Lectura corregida desde {lectura.id}. {motivo}', fecha_lectura=now_date_str(), hora_lectura=now_time_str(), latitud=lectura.latitud, longitud=lectura.longitud, estado='REGISTRADA')
        db.session.add(nueva)
        db.session.flush()
        cobro = _calcular_cobro(consumo, socio.id, vivienda.id)
        subtotal = cobro['subtotal']
        total = subtotal + cobro.get('multa', 0) + cobro.get('otros', 0)
        anio = int(datetime.now().strftime('%Y'))
        mes = int(datetime.now().strftime('%m'))
        consumo_row = Consumo(lectura_id=nueva.id, vivienda_id=vivienda.id, socio_id=socio.id, periodo_anio=anio, periodo_mes=mes, lectura_inicial=lectura_anterior, lectura_final=corrected, consumo_m3=consumo, tarifa_id=cobro['tarifa_id'], cargo_fijo=cobro['cargo_fijo'], valor_m3=cobro['valor_m3'], subtotal_consumo=subtotal, multa=cobro.get('multa', 0), total_pagar=total, indicador=_indicator(consumo), observacion=f'Generado por recálculo de lectura {lectura.id}')
        db.session.add(consumo_row)
        db.session.flush()
        numero = f'PLN-{anio}{mes:02d}-{vivienda.id:04d}-R{nueva.id}'
        planilla = Planilla(socio_id=socio.id, vivienda_id=vivienda.id, lectura_id=nueva.id, consumo_id=consumo_row.id, periodo_anio=anio, periodo_mes=mes, numero_planilla=numero, fecha_emision=now_date_str(), fecha_vencimiento=(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'), lectura_anterior=lectura_anterior, lectura_actual=corrected, consumo_m3=consumo, cargo_fijo=consumo_row.cargo_fijo, valor_m3=consumo_row.valor_m3, subtotal_consumo=subtotal, multa=consumo_row.multa, total_pagar=total, estado='PENDIENTE', observacion=f'Regenerada por corrección de lectura {lectura.id}')
        db.session.add(planilla)
        nueva_id = nueva.id
        create_notification(socio.usuario_id, 'Lectura corregida', f'Se corrigió la lectura anterior y se regeneró la planilla {numero}.', 'LECTURA', 'lecturas', nueva.id)
    db.session.commit()
    return jsonify({'mensaje': 'Lectura anulada y recalculada correctamente.' if nueva_id else 'Lectura anulada correctamente.', 'nueva_lectura_id': nueva_id})


@lecturas_bp.get('/reclamos')
@jwt_required()
def list_reclamos_lectura():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    q = ReclamoLectura.query.order_by(ReclamoLectura.id.desc())
    if user.rol.nombre == 'SOCIO' and user.socio:
        q = q.join(ReclamoLectura.lectura).filter(Lectura.socio_id == user.socio.id)
    return jsonify([{
        'id': r.id, 'lectura_id': r.lectura_id, 'motivo': r.motivo, 'descripcion': r.descripcion, 'estado': r.estado,
        'fecha': r.fecha, 'hora': r.hora, 'reportado_por': r.usuario.nombre_completo if r.usuario else None
    } for r in q.all()])