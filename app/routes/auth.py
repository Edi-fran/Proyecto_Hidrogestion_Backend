from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from flask import Blueprint, jsonify, request, session, redirect, url_for, flash
from flask_jwt_extended import (
    create_access_token, create_refresh_token, decode_token,
    get_jwt, get_jwt_identity, jwt_required,
)
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import Auditoria, Sesion, Usuario
from app.utils import now_date_str, now_time_str


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
    access_decoded  = decode_token(access_token)

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
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
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
    user = Usuario.query.get_or_404(int(get_jwt_identity()))
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

    session['web_user_id'] = user.id
    session['web_role'] = user.rol.nombre
    session['web_name'] = user.nombre_completo
    return redirect(url_for('dashboard.index'))


@auth_bp.get('/web-logout')
def web_logout():
    session.clear()
    return redirect(url_for('dashboard.login_page'))
