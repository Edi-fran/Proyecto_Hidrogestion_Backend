from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, redirect, send_from_directory, url_for
from werkzeug.security import generate_password_hash

from app.config import Config
from app.extensions import cors, db, jwt
from app.models import (
    Auditoria, ConfiguracionSistema, JuntaAgua, Medidor, MovimientoCaja, Mensaje, Notificacion, OrdenTrabajo, OrdenEvidencia,
    Rol, RutaLecturacion, RutaMedidor, Sector, Sesion, Socio, Tarifa, TarifaAsignada,
    Usuario, Vivienda
)
from app.utils import now_date_str, now_time_str


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    for sub in ['usuarios', 'lecturas', 'incidencias', 'seguimientos', 'aportes', 'planillas', 'reportes']:
        Path(app.config['UPLOAD_FOLDER'], sub).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config['CORS_ORIGINS']}}, supports_credentials=False)

    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.admin_extra import admin_extra_bp
    from app.routes.avisos import avisos_bp
    from app.routes.lecturas import lecturas_bp
    from app.routes.incidencias import incidencias_bp
    from app.routes.aportes import aportes_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.planillas import planillas_bp
    from app.routes.ordenes import ordenes_bp
    from app.routes.comunicaciones import comunicaciones_bp
    from app.routes.iot import iot_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api')
    app.register_blueprint(admin_extra_bp, url_prefix='/api')
    app.register_blueprint(avisos_bp, url_prefix='/api/avisos')
    app.register_blueprint(lecturas_bp, url_prefix='/api/lecturas')
    app.register_blueprint(incidencias_bp, url_prefix='/api/incidencias')
    app.register_blueprint(aportes_bp, url_prefix='/api/aportes')
    app.register_blueprint(planillas_bp, url_prefix='/api/planillas')
    app.register_blueprint(ordenes_bp, url_prefix='/api/ordenes')
    app.register_blueprint(comunicaciones_bp, url_prefix='/api')
    app.register_blueprint(iot_bp, url_prefix='/api/iot')
    app.register_blueprint(dashboard_bp)

    @app.route('/api/health')
    def health():
        return jsonify({'ok': True, 'mensaje': 'Servidor HidroGestión operativo', 'timestamp': datetime.now().isoformat()})

    @app.route('/')
    def home():
        return redirect(url_for('dashboard.login_page'))

    @app.route('/uploads/<path:filename>')
    def uploads(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @jwt.token_in_blocklist_loader
    def is_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload['jti']
        sesion = Sesion.query.filter_by(jti=jti).first()
        return bool(sesion and sesion.revocado)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'mensaje': 'La sesión ya no es válida.'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'mensaje': f'Token inválido: {error}'}), 422

    @jwt.unauthorized_loader
    def unauthorized_loader(error):
        return jsonify({'mensaje': f'Autenticación requerida: {error}'}), 401

    @jwt.expired_token_loader
    def expired_token_loader(jwt_header, jwt_payload):
        return jsonify({'mensaje': 'El token ha expirado.'}), 401

    with app.app_context():
        db.create_all()
        seed_base_data()

    return app


def seed_base_data() -> None:
    if Rol.query.count() == 0:
        db.session.add_all([
            Rol(nombre='ADMIN', descripcion='Administrador general del sistema'),
            Rol(nombre='TECNICO', descripcion='Operador o técnico del sistema'),
            Rol(nombre='SOCIO', descripcion='Usuario abonado del sistema')
        ])
        db.session.commit()

    junta = JuntaAgua.query.first()
    if not junta:
        junta = JuntaAgua(nombre='Junta de Agua HidroGestión', descripcion='Junta base para pruebas del sistema', parroquia='Sidras', canton='Catamayo', provincia='Loja', direccion='Oficina principal', telefono='0999999999', email='junta@hidrogestion.local')
        db.session.add(junta)
        db.session.commit()

    if Sector.query.count() == 0:
        db.session.add_all([
            Sector(junta_id=junta.id, nombre='Centro', descripcion='Sector central'),
            Sector(junta_id=junta.id, nombre='Las Sidras', descripcion='Sector Las Sidras')
        ])
        db.session.commit()

    if Tarifa.query.count() == 0:
        db.session.add(Tarifa(nombre='Tarifa base 2026', cargo_fijo=3.5, valor_m3=0.40, mora=1.0, estado='ACTIVA', fecha_inicio=now_date_str()))
        db.session.commit()

    roles = {r.nombre: r for r in Rol.query.all()}
    users_seed = [
        ('admin', 'Admin123*', roles['ADMIN'], '1100000001', 'Administrador', 'General', 'admin@hidrogestion.local'),
        ('tecnico', 'Tecnico123*', roles['TECNICO'], '1100000003', 'Usuario', 'Tecnico', 'tecnico@hidrogestion.local'),
        ('socio', 'Socio123*', roles['SOCIO'], '1100000002', 'Socio', 'Demo', 'socio@hidrogestion.local'),
    ]
    for username, pwd, rol, cedula, nombres, apellidos, email in users_seed:
        if not Usuario.query.filter_by(username=username).first():
            db.session.add(Usuario(rol_id=rol.id, cedula=cedula, nombres=nombres, apellidos=apellidos, telefono='0999999999', email=email, username=username, password_hash=generate_password_hash(pwd), estado='ACTIVO'))
    db.session.commit()

    socio_user = Usuario.query.filter_by(username='socio').first()
    tecnico = Usuario.query.filter_by(username='tecnico').first()
    socio = Socio.query.filter_by(usuario_id=socio_user.id).first()
    if not socio:
        socio = Socio(usuario_id=socio_user.id, junta_id=junta.id, codigo_socio='SOC-001', numero_medidor='MED-001', estado_servicio='ACTIVO', fecha_ingreso=now_date_str())
        db.session.add(socio)
        db.session.commit()

    vivienda = Vivienda.query.filter_by(socio_id=socio.id).first()
    if not vivienda:
        sector = Sector.query.first()
        vivienda = Vivienda(socio_id=socio.id, sector_id=sector.id, codigo_vivienda='VIV-001', direccion='Barrio Central, casa azul', referencia='Frente a la cancha', latitud=-4.0, longitud=-79.2, tipo_vivienda='CASA')
        db.session.add(vivienda)
        db.session.commit()

    medidor = Medidor.query.filter_by(numero_medidor='MED-001').first()
    if not medidor:
        medidor = Medidor(socio_id=socio.id, vivienda_id=vivienda.id, numero_medidor='MED-001', marca='Genérico', modelo='2026', estado='ACTIVO', fecha_instalacion=now_date_str())
        db.session.add(medidor)
        db.session.commit()

    tecnico_socio = Socio.query.filter_by(usuario_id=tecnico.id).first()
    if not tecnico_socio:
        tecnico_socio = Socio(usuario_id=tecnico.id, junta_id=junta.id, codigo_socio='SOC-TEC-001', numero_medidor='MED-TEC-001', estado_servicio='ACTIVO', fecha_ingreso=now_date_str(), observacion='Perfil técnico con datos de socio para consumo propio')
        db.session.add(tecnico_socio)
        db.session.commit()

    tecnico_vivienda = Vivienda.query.filter_by(socio_id=tecnico_socio.id).first()
    if not tecnico_vivienda:
        sector = Sector.query.first()
        tecnico_vivienda = Vivienda(socio_id=tecnico_socio.id, sector_id=sector.id, codigo_vivienda='VIV-TEC-001', direccion='Vivienda del técnico', referencia='Casa del técnico', latitud=-4.001, longitud=-79.201, tipo_vivienda='CASA')
        db.session.add(tecnico_vivienda)
        db.session.commit()

    tecnico_medidor = Medidor.query.filter_by(numero_medidor='MED-TEC-001').first()
    if not tecnico_medidor:
        tecnico_medidor = Medidor(socio_id=tecnico_socio.id, vivienda_id=tecnico_vivienda.id, numero_medidor='MED-TEC-001', marca='Genérico', modelo='2026', estado='ACTIVO', fecha_instalacion=now_date_str())
        db.session.add(tecnico_medidor)
        db.session.commit()

    if TarifaAsignada.query.count() == 0:
        tarifa = Tarifa.query.filter_by(estado='ACTIVA').first()
        db.session.add_all([
            TarifaAsignada(socio_id=socio.id, vivienda_id=vivienda.id, tarifa_id=tarifa.id if tarifa else None, nombre='Tarifa socio demo', base_consumo_m3=10, valor_base=5.0, valor_adicional_m3=0.45, multa_atraso=1.5, estado='ACTIVA'),
            TarifaAsignada(socio_id=tecnico_socio.id, vivienda_id=tecnico_vivienda.id, tarifa_id=tarifa.id if tarifa else None, nombre='Tarifa técnico demo', base_consumo_m3=8, valor_base=4.0, valor_adicional_m3=0.40, multa_atraso=1.0, estado='ACTIVA'),
        ])
        db.session.commit()

    ruta = RutaLecturacion.query.first()
    if not ruta:
        ruta = RutaLecturacion(junta_id=junta.id, sector_id=vivienda.sector_id, nombre='Ruta Centro', descripcion='Ruta principal de lecturación', tecnico_id=tecnico.id, estado='ACTIVA')
        db.session.add(ruta)
        db.session.commit()
        db.session.add(RutaMedidor(ruta_id=ruta.id, medidor_id=medidor.id))
        db.session.commit()

    if not ConfiguracionSistema.query.filter_by(clave='nombre_app').first():
        db.session.add(ConfiguracionSistema(clave='nombre_app', valor='HidroGestión App', descripcion='Nombre del sistema'))
        db.session.commit()

    if Notificacion.query.count() == 0:
        db.session.add_all([
            Notificacion(usuario_id=socio_user.id, titulo='Bienvenido', mensaje='Tu cuenta socio está activa. Revisa tus avisos y planillas.', tipo='SISTEMA', fecha=now_date_str(), hora=now_time_str(), leido=False),
            Notificacion(usuario_id=tecnico.id, titulo='Lecturas pendientes', mensaje='Tienes lecturas e incidencias por revisar.', tipo='LECTURA', fecha=now_date_str(), hora=now_time_str(), leido=False),
        ])
        db.session.commit()

    if Mensaje.query.count() == 0:
        admin = Usuario.query.filter_by(username='admin').first()
        db.session.add(Mensaje(remitente_id=admin.id, destinatario_id=tecnico.id, asunto='Primera orden', contenido='Revisar fugas reportadas y completar lecturas pendientes.', fecha=now_date_str(), hora=now_time_str(), estado='ENVIADO', leido=False))
        db.session.commit()

    if OrdenTrabajo.query.count() == 0:
        admin = Usuario.query.filter_by(username='admin').first()
        db.session.add(OrdenTrabajo(tecnico_id=tecnico.id, creado_por=admin.id, titulo='Inspección de red', descripcion='Revisar posibles fugas en el sector Centro.', estado='ASIGNADA', prioridad='MEDIA', fecha=now_date_str(), hora=now_time_str(), latitud=vivienda.latitud, longitud=vivienda.longitud))
        db.session.commit()