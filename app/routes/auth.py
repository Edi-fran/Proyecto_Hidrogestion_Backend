from __future__ import annotations

import re
from datetime import datetime, timedelta
from hashlib import sha256

from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for, flash
from flask_jwt_extended import (
    create_access_token, create_refresh_token, decode_token,
    get_jwt, get_jwt_identity, jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Auditoria, JuntaAgua, Rol, Sector, Sesion, Socio, Usuario
from app.utils import now_date_str, now_time_str, save_upload


auth_bp = Blueprint('auth', __name__)


def _hash_token(token: str) -> str:
    return sha256(token.encode('utf-8')).hexdigest()


@auth_bp.post('/login')
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'mensaje': 'Usuario y contraseña son obligatorios.'}), 400

    user = Usuario.query.filter(
        (Usuario.username == username) | (Usuario.email == username)
    ).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'mensaje': 'Credenciales inválidas.'}), 401

    if user.estado != 'ACTIVO':
        return jsonify({'mensaje': 'El usuario no está activo.'}), 403

    claims = {'rol': user.rol.nombre, 'nombre': user.nombre_completo, 'username': user.username}
    access_token  = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)

    refresh_decoded = decode_token(refresh_token)

    sesion_db = Sesion(
        usuario_id=user.id,
        jti=refresh_decoded['jti'],
        tipo_token='REFRESH',
        refresh_token_hash=_hash_token(refresh_token),
        access_token_hash=_hash_token(access_token),
        dispositivo=data.get('dispositivo'),
        sistema_operativo=data.get('sistema_operativo'),
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        fecha_emision=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        fecha_expiracion=datetime.utcfromtimestamp(refresh_decoded['exp']).strftime('%Y-%m-%d %H:%M:%S'),
        ultimo_uso=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        revocado=False,
    )
    db.session.add(sesion_db)
    user.ultimo_login = datetime.utcnow()
    db.session.add(Auditoria(
        usuario_id=user.id,
        tabla_afectada='usuarios',
        registro_id=user.id,
        accion='LOGIN',
        detalle='Inicio de sesión API',
        fecha=now_date_str(),
        hora=now_time_str(),
        ip=request.remote_addr,
    ))
    db.session.commit()

    return jsonify({
        'mensaje': 'Inicio de sesión correcto.',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'usuario': {
            'id': user.id,
            'nombre': user.nombre_completo,
            'username': user.username,
            'email': user.email,
            'rol': user.rol.nombre,
            'foto_perfil': user.foto_perfil,
        },
    })


@auth_bp.post('/refresh')
@jwt_required(refresh=True)
def refresh_token():
    user = db.session.get(Usuario, int(get_jwt_identity()))
    if not user:
        return jsonify({'mensaje': 'Usuario no encontrado.'}), 404
    claims = get_jwt()
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            'rol': claims.get('rol', user.rol.nombre),
            'nombre': user.nombre_completo,
            'username': user.username,
        },
    )
    return jsonify({'access_token': access_token, 'mensaje': 'Token renovado.'})


@auth_bp.get('/token-info')
@jwt_required()
def token_info():
    claims = get_jwt()
    return jsonify({
        'sub': get_jwt_identity(),
        'jti': claims.get('jti'),
        'type': claims.get('type'),
        'claims': claims,
    })


@auth_bp.post('/logout')
@jwt_required(refresh=True)
def api_logout():
    body = request.get_json(silent=True) or {}
    token_value = body.get('refresh_token')
    sesion_db = None

    if token_value:
        sesion_db = Sesion.query.filter_by(
            refresh_token_hash=_hash_token(token_value), revocado=False
        ).first()

    if not sesion_db:
        jti = get_jwt().get('jti')
        sesion_db = Sesion.query.filter_by(jti=jti, revocado=False).first()

    if sesion_db:
        sesion_db.revocado = True
        sesion_db.fecha_revocacion = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        db.session.commit()

    return jsonify({'mensaje': 'Sesión cerrada correctamente.'})


@auth_bp.get('/me')
@jwt_required()
def api_me():
    user = db.session.get(Usuario, int(get_jwt_identity()))
    if not user:
        return jsonify({'mensaje': 'Usuario no encontrado.'}), 404
    return jsonify({
        'id': user.id,
        'nombre': user.nombre_completo,
        'username': user.username,
        'email': user.email,
        'telefono': user.telefono,
        'rol': user.rol.nombre,
        'foto_perfil': user.foto_perfil,
        'estado': user.estado,
    })


@auth_bp.post('/web-login')
def web_login():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''

    user = Usuario.query.filter(
        (Usuario.username == username) | (Usuario.email == username)
    ).first()

    if not user or not check_password_hash(user.password_hash, password):
        flash('Credenciales inválidas.', 'danger')
        return redirect(url_for('dashboard.login_page'))

    if user.estado != 'ACTIVO':
        flash('Tu cuenta está desactivada.', 'danger')
        return redirect(url_for('dashboard.login_page'))

    if user.rol.nombre != 'ADMIN':
        flash('Acceso denegado. Solo administradores pueden ingresar al panel.', 'danger')
        return redirect(url_for('dashboard.login_page'))

    session['web_user_id'] = user.id
    session['web_role'] = user.rol.nombre
    session['web_name'] = user.nombre_completo
    return redirect(url_for('dashboard.index'))


@auth_bp.get('/web-logout')
def web_logout():
    session.clear()
    return redirect(url_for('dashboard.login_page'))


# ── REGISTRO PÚBLICO (app móvil) ─────────────────────────────────────────────

@auth_bp.post('/registro')
def api_registro():
    is_multipart = request.content_type and 'multipart' in request.content_type
    data = request.form if is_multipart else (request.get_json(silent=True) or {})
    foto = request.files.get('foto_perfil') if request.files else None

    nombres   = (data.get('nombres')   or '').strip()
    apellidos = (data.get('apellidos') or '').strip()
    username  = (data.get('username')  or '').strip()
    password  = (data.get('password')  or '').strip()
    pregunta  = (data.get('pregunta_seguridad')  or '').strip()
    respuesta = (data.get('respuesta_seguridad') or '').strip().lower()
    consent   = data.get('consentimiento_datos') in ('1', 'true', 'True', True, 1)

    if not all([nombres, apellidos, username, password, pregunta, respuesta]):
        return jsonify({'mensaje': 'Todos los campos obligatorios son requeridos.'}), 400
    if not consent:
        return jsonify({'mensaje': 'Debe aceptar el consentimiento de protección de datos.'}), 400
    if len(password) < 6:
        return jsonify({'mensaje': 'La contraseña debe tener al menos 6 caracteres.'}), 400
    if not foto:
        return jsonify({'mensaje': 'La foto de perfil es obligatoria.'}), 400
    if Usuario.query.filter_by(username=username).first():
        return jsonify({'mensaje': 'El nombre de usuario ya está en uso.'}), 409

    email = (data.get('email') or '').strip() or None
    if email:
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'mensaje': 'El formato del correo electrónico no es válido.'}), 400
        if Usuario.query.filter_by(email=email).first():
            return jsonify({'mensaje': 'El correo electrónico ya está registrado.'}), 409

    ruta_foto, _ = save_upload(foto, 'perfiles')

    rol = Rol.query.filter_by(nombre='SOCIO').first()
    if not rol:
        return jsonify({'mensaje': 'Error de configuración del sistema.'}), 500

    user = Usuario(
        rol_id=rol.id,
        cedula=(data.get('cedula') or '').strip() or None,
        nombres=nombres,
        apellidos=apellidos,
        telefono=(data.get('telefono') or '').strip() or None,
        email=email,
        username=username,
        password_hash=generate_password_hash(password),
        foto_perfil=ruta_foto,
        pregunta_seguridad=pregunta,
        respuesta_seguridad_hash=generate_password_hash(respuesta),
        consentimiento_datos=True,
        fecha_consentimiento=datetime.utcnow(),
        estado='ACTIVO',
    )
    db.session.add(user)
    db.session.commit()

    junta = JuntaAgua.query.first()
    if junta:
        # Código único: si ya existe SOC-00X usar el UUID
        codigo_base = f'SOC-{user.id:04d}'
        if Socio.query.filter_by(codigo_socio=codigo_base).first():
            import uuid as _uuid
            codigo_base = f'SOC-{_uuid.uuid4().hex[:8].upper()}'
        socio = Socio(
            usuario_id=user.id,
            junta_id=junta.id,
            codigo_socio=codigo_base,
            estado_servicio='ACTIVO',
            fecha_ingreso=now_date_str(),
        )
        db.session.add(socio)
        db.session.commit()

    db.session.add(Auditoria(
        usuario_id=user.id,
        tabla_afectada='usuarios',
        registro_id=user.id,
        accion='REGISTRO',
        detalle='Auto-registro desde app móvil',
        fecha=now_date_str(),
        hora=now_time_str(),
        ip=request.remote_addr,
    ))
    db.session.commit()

    return jsonify({
        'mensaje': 'Cuenta creada correctamente. Ya puedes iniciar sesión.',
        'usuario': {'id': user.id, 'nombre': user.nombre_completo, 'username': user.username},
    }), 201


# ── RECUPERACIÓN API (móvil / JSON) ──────────────────────────────────────────

@auth_bp.post('/recuperar/paso1')
def api_recuperar_paso1():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'mensaje': 'El usuario o email es obligatorio.'}), 400
    user = Usuario.query.filter(
        (Usuario.username == username) | (Usuario.email == username)
    ).first()
    if not user or user.estado != 'ACTIVO':
        return jsonify({'mensaje': 'No se encontró un usuario activo con ese nombre o email.'}), 404
    if not user.pregunta_seguridad or not user.respuesta_seguridad_hash:
        return jsonify({'mensaje': 'Este usuario no tiene pregunta de seguridad. Contacta al administrador.'}), 400
    return jsonify({'user_id': user.id, 'pregunta': user.pregunta_seguridad})


@auth_bp.post('/recuperar/paso2')
def api_recuperar_paso2():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    respuesta = (data.get('respuesta') or '').strip().lower()
    if not user_id or not respuesta:
        return jsonify({'mensaje': 'Datos incompletos.'}), 400
    user = db.session.get(Usuario, int(user_id))
    if not user or user.estado != 'ACTIVO':
        return jsonify({'mensaje': 'Usuario no válido.'}), 404
    if not user.respuesta_seguridad_hash or not check_password_hash(user.respuesta_seguridad_hash, respuesta):
        return jsonify({'mensaje': 'Respuesta incorrecta. Intenta nuevamente.'}), 401
    recovery_token = create_access_token(
        identity=str(user.id),
        expires_delta=timedelta(minutes=15),
        additional_claims={'tipo': 'RECOVERY', 'username': user.username},
    )
    return jsonify({'recovery_token': recovery_token, 'mensaje': 'Respuesta verificada.'})


@auth_bp.post('/recuperar/paso3')
def api_recuperar_paso3():
    data = request.get_json(silent=True) or {}
    recovery_token = data.get('recovery_token') or ''
    nueva = (data.get('nueva_password') or '').strip()
    if len(nueva) < 6:
        return jsonify({'mensaje': 'La contraseña debe tener al menos 6 caracteres.'}), 400
    try:
        decoded = decode_token(recovery_token)
    except Exception:
        return jsonify({'mensaje': 'Token de recuperación inválido o expirado.'}), 401
    if decoded.get('tipo') != 'RECOVERY':
        return jsonify({'mensaje': 'Token de recuperación inválido.'}), 401
    user = db.session.get(Usuario, int(decoded['sub']))
    if not user:
        return jsonify({'mensaje': 'Usuario no encontrado.'}), 404
    user.password_hash = generate_password_hash(nueva)
    db.session.commit()
    return jsonify({'mensaje': 'Contraseña restablecida. Ya puedes iniciar sesión.'})


# ── RECUPERACIÓN WEB (formulario HTML) ───────────────────────────────────────

PREGUNTAS_SEGURIDAD = [
    '¿Cuál es tu fecha de nacimiento? (DD/MM/AAAA)',
    '¿Cuál es tu color favorito?',
    '¿Cuál es el nombre de tu primera mascota?',
    '¿En qué ciudad naciste?',
    '¿Cuál es el nombre de tu madre?',
    '¿Cuál es el nombre de tu escuela primaria?',
    '¿Cuál es el nombre de tu mejor amigo de infancia?',
]


@auth_bp.route('/recuperar', methods=['GET', 'POST'])
def recuperar_password():
    paso = request.args.get('paso', '1')

    # ── PASO 1: verificar usuario ──
    if request.method == 'POST' and paso == '1':
        username = (request.form.get('username') or '').strip()
        user = Usuario.query.filter(
            (Usuario.username == username) | (Usuario.email == username)
        ).first()
        if not user or user.estado != 'ACTIVO':
            flash('No se encontró un usuario activo con ese nombre o email.', 'danger')
            return redirect(url_for('auth.recuperar_password', paso=1))
        if not user.pregunta_seguridad or not user.respuesta_seguridad_hash:
            flash('Este usuario no tiene pregunta de seguridad configurada. Contacta al administrador.', 'warning')
            return redirect(url_for('auth.recuperar_password', paso=1))
        session['recover_uid'] = user.id
        session.pop('recover_ok', None)
        return redirect(url_for('auth.recuperar_password', paso=2))

    # ── PASO 2: verificar respuesta ──
    if request.method == 'POST' and paso == '2':
        uid = session.get('recover_uid')
        if not uid:
            return redirect(url_for('auth.recuperar_password', paso=1))
        user = Usuario.query.get(uid)
        if not user:
            return redirect(url_for('auth.recuperar_password', paso=1))
        respuesta = (request.form.get('respuesta') or '').strip().lower()
        if not check_password_hash(user.respuesta_seguridad_hash, respuesta):
            flash('Respuesta incorrecta. Intenta nuevamente.', 'danger')
            return redirect(url_for('auth.recuperar_password', paso=2))
        session['recover_ok'] = True
        return redirect(url_for('auth.recuperar_password', paso=3))

    # ── PASO 3: cambiar contraseña ──
    if request.method == 'POST' and paso == '3':
        if not session.get('recover_ok') or not session.get('recover_uid'):
            return redirect(url_for('auth.recuperar_password', paso=1))
        user = Usuario.query.get(session['recover_uid'])
        if not user:
            return redirect(url_for('auth.recuperar_password', paso=1))
        nueva = (request.form.get('nueva_password') or '').strip()
        confirmar = (request.form.get('confirmar_password') or '').strip()
        if len(nueva) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return redirect(url_for('auth.recuperar_password', paso=3))
        if nueva != confirmar:
            flash('Las contraseñas no coinciden.', 'danger')
            return redirect(url_for('auth.recuperar_password', paso=3))
        user.password_hash = generate_password_hash(nueva)
        db.session.commit()
        session.pop('recover_uid', None)
        session.pop('recover_ok', None)
        flash('Contraseña restablecida correctamente. Ingresa con tu nueva contraseña.', 'success')
        return redirect(url_for('dashboard.login_page'))

    # ── GET: mostrar el paso correspondiente ──
    user = None
    if paso in ('2', '3') and session.get('recover_uid'):
        user = Usuario.query.get(session['recover_uid'])
        if not user:
            return redirect(url_for('auth.recuperar_password', paso=1))
        if paso == '3' and not session.get('recover_ok'):
            return redirect(url_for('auth.recuperar_password', paso=2))

    return render_template(
        'dashboard/recover.html',
        paso=paso,
        user=user,
        preguntas=PREGUNTAS_SEGURIDAD,
    )
