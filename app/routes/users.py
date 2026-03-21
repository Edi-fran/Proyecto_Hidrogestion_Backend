from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import DispositivoPush, JuntaAgua, Medidor, Rol, RutaLecturacion, RutaMedidor, Sector, Socio, Tarifa, TarifaAsignada, Usuario, Vivienda
from app.utils import now_date_str, save_upload, to_float, to_int


users_bp = Blueprint('users', __name__)


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


def _serialize_user(u: Usuario):
    socio = u.socio
    vivienda = socio.viviendas[0] if socio and socio.viviendas else None
    medidor = socio.medidores[0] if socio and socio.medidores else None
    return {
        'id': u.id,
        'cedula': u.cedula,
        'nombre': u.nombre_completo,
        'username': u.username,
        'email': u.email,
        'telefono': u.telefono,
        'rol': u.rol.nombre,
        'foto_perfil': u.foto_perfil,
        'estado': u.estado,
        'codigo_socio': socio.codigo_socio if socio else None,
        'numero_medidor': medidor.numero_medidor if medidor else (socio.numero_medidor if socio else None),
        'direccion': vivienda.direccion if vivienda else None,
        'sector': vivienda.sector.nombre if vivienda and vivienda.sector else None,
    }


@users_bp.get('/usuarios')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def list_usuarios():
    q = request.args.get('q', '').strip()
    query = Usuario.query.order_by(Usuario.id.desc())
    if q:
        query = query.filter((Usuario.cedula.contains(q)) | (Usuario.nombres.contains(q)) | (Usuario.apellidos.contains(q)) | (Usuario.username.contains(q)))
    return jsonify([_serialize_user(u) for u in query.all()])


@users_bp.get('/usuarios/<int:user_id>')
@jwt_required()
@require_roles('ADMIN', 'TECNICO', 'SOCIO')
def get_usuario(user_id):
    if get_jwt().get('rol') == 'SOCIO' and int(get_jwt_identity()) != user_id:
        return jsonify({'mensaje': 'No autorizado.'}), 403
    return jsonify(_serialize_user(Usuario.query.get_or_404(user_id)))


@users_bp.post('/usuarios')
@jwt_required()
@require_roles('ADMIN')
def create_usuario():
    data = request.form if request.content_type and request.content_type.startswith('multipart/form-data') else (request.get_json(silent=True) or {})
    foto = request.files.get('foto_perfil') if request.files else None
    rol_nombre = (data.get('rol') or 'SOCIO').upper()
    rol = Rol.query.filter_by(nombre=rol_nombre).first()
    if not rol:
        return jsonify({'mensaje': 'Rol no válido.'}), 400
    if Usuario.query.filter_by(username=data.get('username')).first():
        return jsonify({'mensaje': 'El username ya existe.'}), 409
    ruta_foto = None
    if foto:
        ruta_foto, _ = save_upload(foto, 'usuarios')
    user = Usuario(rol_id=rol.id, cedula=data.get('cedula'), nombres=data.get('nombres') or 'Sin nombres', apellidos=data.get('apellidos') or 'Sin apellidos', telefono=data.get('telefono'), email=data.get('email'), username=data.get('username'), password_hash=generate_password_hash(data.get('password') or 'Temporal123*'), foto_perfil=ruta_foto, direccion_referencia=data.get('direccion_referencia'), estado=data.get('estado', 'ACTIVO'))
    db.session.add(user)
    db.session.commit()
    if rol.nombre == 'SOCIO':
        junta = JuntaAgua.query.get(to_int(data.get('junta_id'))) or JuntaAgua.query.first()
        socio = Socio(usuario_id=user.id, junta_id=junta.id, codigo_socio=data.get('codigo_socio') or f'SOC-{user.id:03d}', numero_medidor=data.get('numero_medidor') or f'MED-{user.id:03d}', estado_servicio=data.get('estado_servicio', 'ACTIVO'), fecha_ingreso=now_date_str())
        db.session.add(socio)
        db.session.commit()
        sector = Sector.query.get(to_int(data.get('sector_id'))) or Sector.query.first()
        vivienda = Vivienda(socio_id=socio.id, sector_id=sector.id, codigo_vivienda=data.get('codigo_vivienda') or f'VIV-{user.id:03d}', direccion=data.get('direccion') or 'Sin dirección registrada', referencia=data.get('referencia'), latitud=to_float(data.get('latitud')), longitud=to_float(data.get('longitud')), tipo_vivienda=data.get('tipo_vivienda', 'CASA'))
        db.session.add(vivienda)
        db.session.commit()
        medidor = Medidor(socio_id=socio.id, vivienda_id=vivienda.id, numero_medidor=data.get('numero_medidor') or f'MED-{user.id:03d}', marca=data.get('marca_medidor'), modelo=data.get('modelo_medidor'), estado='ACTIVO', fecha_instalacion=now_date_str())
        db.session.add(medidor)
        db.session.commit()
        ruta_id = to_int(data.get('ruta_id'))
        if ruta_id:
            db.session.add(RutaMedidor(ruta_id=ruta_id, medidor_id=medidor.id))
            db.session.commit()
    return jsonify({'mensaje': 'Usuario creado correctamente.', 'usuario': _serialize_user(user)}), 201


@users_bp.put('/usuarios/<int:user_id>')
@jwt_required()
@require_roles('ADMIN')
def update_usuario(user_id):
    user = Usuario.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    for field in ['cedula', 'nombres', 'apellidos', 'telefono', 'email', 'username', 'direccion_referencia', 'estado']:
        if field in data:
            setattr(user, field, data.get(field))
    if data.get('password'):
        user.password_hash = generate_password_hash(data['password'])
    if data.get('rol'):
        rol = Rol.query.filter_by(nombre=data['rol'].upper()).first()
        if rol:
            user.rol_id = rol.id
    if user.socio:
        if 'codigo_socio' in data:
            user.socio.codigo_socio = data.get('codigo_socio')
        if 'numero_medidor' in data:
            user.socio.numero_medidor = data.get('numero_medidor')
            medidor = user.socio.medidores[0] if user.socio.medidores else None
            if medidor:
                medidor.numero_medidor = data.get('numero_medidor')
    db.session.commit()
    return jsonify({'mensaje': 'Usuario actualizado correctamente.', 'usuario': _serialize_user(user)})


@users_bp.delete('/usuarios/<int:user_id>')
@jwt_required()
@require_roles('ADMIN')
def delete_usuario(user_id):
    user = Usuario.query.get_or_404(user_id)
    user.estado = 'INACTIVO'
    db.session.commit()
    return jsonify({'mensaje': 'Usuario desactivado correctamente.'})


@users_bp.get('/mi-vivienda')
@jwt_required()
def my_home():
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
    if not user.socio or not user.socio.viviendas:
        return jsonify({'mensaje': 'No hay vivienda asociada.'}), 404
    vivienda = user.socio.viviendas[0]
    medidor = user.socio.medidores[0] if user.socio.medidores else None
    return jsonify({'vivienda_id': vivienda.id, 'codigo_vivienda': vivienda.codigo_vivienda, 'direccion': vivienda.direccion, 'referencia': vivienda.referencia, 'latitud': vivienda.latitud, 'longitud': vivienda.longitud, 'sector': vivienda.sector.nombre if vivienda.sector else None, 'numero_medidor': medidor.numero_medidor if medidor else user.socio.numero_medidor, 'codigo_socio': user.socio.codigo_socio})


@users_bp.get('/medidores')
@jwt_required()
@require_roles('ADMIN', 'TECNICO')
def list_medidores():
    q = request.args.get('q', '').strip()
    sector_id = to_int(request.args.get('sector_id'))
    tecnico_id = to_int(request.args.get('tecnico_id'))
    query = Medidor.query.join(Vivienda).join(Socio).join(Usuario).order_by(Medidor.id.desc())
    if q:
        query = query.filter((Medidor.numero_medidor.contains(q)) | (Usuario.cedula.contains(q)) | (Usuario.nombres.contains(q)) | (Usuario.apellidos.contains(q)))
    if sector_id:
        query = query.filter(Vivienda.sector_id == sector_id)
    if tecnico_id:
        query = query.join(RutaMedidor, RutaMedidor.medidor_id == Medidor.id).join(RutaLecturacion, RutaLecturacion.id == RutaMedidor.ruta_id).filter(RutaLecturacion.tecnico_id == tecnico_id)
    return jsonify([{'id': m.id, 'numero_medidor': m.numero_medidor, 'socio': m.socio.usuario.nombre_completo, 'cedula': m.socio.usuario.cedula, 'vivienda_id': m.vivienda_id, 'direccion': m.vivienda.direccion if m.vivienda else None, 'sector': m.vivienda.sector.nombre if m.vivienda and m.vivienda.sector else None, 'latitud': m.vivienda.latitud if m.vivienda else None, 'longitud': m.vivienda.longitud if m.vivienda else None} for m in query.all()])


@users_bp.post('/push-token')
@jwt_required()
def register_push_token():
    data = request.get_json(silent=True) or {}
    token_push = data.get('token_push')
    if not token_push:
        return jsonify({'mensaje': 'token_push es obligatorio.'}), 400
    item = DispositivoPush.query.filter_by(token_push=token_push).first()
    if not item:
        item = DispositivoPush(usuario_id=int(get_jwt_identity()), token_push=token_push, plataforma=(data.get('plataforma') or 'ANDROID').upper(), dispositivo=data.get('dispositivo'), activo=True)
        db.session.add(item)
    else:
        item.usuario_id = int(get_jwt_identity())
        item.activo = True
        item.dispositivo = data.get('dispositivo')
    db.session.commit()
    return jsonify({'mensaje': 'Token push registrado correctamente.'})


@users_bp.put('/medidores/<int:medidor_id>')
@jwt_required()
@require_roles('ADMIN')
def update_medidor(medidor_id):
    medidor = Medidor.query.get_or_404(medidor_id)
    data = request.get_json(silent=True) or {}
    for field in ['numero_medidor', 'marca', 'modelo', 'estado']:
        if field in data:
            setattr(medidor, field, data.get(field))
    db.session.commit()
    return jsonify({'mensaje': 'Medidor actualizado correctamente.'})


@users_bp.delete('/medidores/<int:medidor_id>')
@jwt_required()
@require_roles('ADMIN')
def delete_medidor(medidor_id):
    medidor = Medidor.query.get_or_404(medidor_id)
    medidor.estado = 'INACTIVO'
    db.session.commit()
    return jsonify({'mensaje': 'Medidor desactivado correctamente.'})


@users_bp.get('/sectores')
@jwt_required()
def list_sectores():
    return jsonify([{'id': s.id, 'nombre': s.nombre} for s in Sector.query.order_by(Sector.nombre).all()])


@users_bp.get('/tarifas-asignadas')
@jwt_required()
def list_tarifas_asignadas():
    q = TarifaAsignada.query.order_by(TarifaAsignada.id.desc()).all()
    return jsonify([{'id': t.id, 'socio_id': t.socio_id, 'vivienda_id': t.vivienda_id, 'nombre': t.nombre, 'base_consumo_m3': t.base_consumo_m3, 'valor_base': t.valor_base, 'valor_adicional_m3': t.valor_adicional_m3, 'multa_atraso': t.multa_atraso, 'estado': t.estado} for t in q])

@users_bp.post('/tarifas-asignadas')
@jwt_required()
@require_roles('ADMIN')
def create_tarifa_asignada():
    data = request.get_json(silent=True) or {}
    item = TarifaAsignada(socio_id=to_int(data.get('socio_id')), vivienda_id=to_int(data.get('vivienda_id')), tarifa_id=to_int(data.get('tarifa_id')), nombre=data.get('nombre') or 'Tarifa personalizada', base_consumo_m3=to_float(data.get('base_consumo_m3')) or 0, valor_base=to_float(data.get('valor_base')) or 0, valor_adicional_m3=to_float(data.get('valor_adicional_m3')) or 0, multa_atraso=to_float(data.get('multa_atraso')) or 0, estado=data.get('estado') or 'ACTIVA')
    db.session.add(item)
    db.session.commit()
    return jsonify({'mensaje':'Tarifa asignada correctamente.', 'id': item.id}), 201

@users_bp.put('/tarifas-asignadas/<int:item_id>')
@jwt_required()
@require_roles('ADMIN')
def update_tarifa_asignada(item_id):
    item = TarifaAsignada.query.get_or_404(item_id)
    data = request.get_json(silent=True) or {}
    for field in ['nombre','estado']:
        if field in data: setattr(item, field, data.get(field))
    for field in ['base_consumo_m3','valor_base','valor_adicional_m3','multa_atraso']:
        if field in data: setattr(item, field, to_float(data.get(field)) or 0)
    db.session.commit()
    return jsonify({'mensaje':'Tarifa actualizada correctamente.'})


@users_bp.delete('/tarifas-asignadas/<int:item_id>')
@jwt_required()
@require_roles('ADMIN')
def delete_tarifa_asignada(item_id):
    item = TarifaAsignada.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'mensaje':'Tarifa eliminada correctamente.'})
