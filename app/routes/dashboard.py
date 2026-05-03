from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for, jsonify, send_from_directory
from werkzeug.security import generate_password_hash
import os

from app.extensions import db
from app.models import Aviso, Incidencia, Lectura, Medidor, Mensaje, MovimientoCaja, Notificacion, OrdenTrabajo, Pago, Planilla, Recordatorio, Reunion, Rol, Sector, Sesion, Socio, Tarifa, TarifaAsignada, Usuario, Vivienda
from app.utils import now_date_str, now_time_str, sync_system_alerts, to_float, to_int
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from datetime import datetime
from app.models import LecturaEvidencia

from datetime import datetime
from werkzeug.utils import secure_filename
from app.models import Usuario, Socio, Medidor, Lectura, LecturaEvidencia, Planilla

from datetime import datetime
from werkzeug.utils import secure_filename
from app.models import Usuario, Socio, Medidor, Lectura, LecturaEvidencia, Planilla
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard', template_folder='../templates', static_folder='../static', static_url_path='/dashboard-static')


import os
from datetime import datetime
from flask import request, render_template, redirect, url_for, flash, abort
from werkzeug.utils import secure_filename

# Busca tu import actual, probablemente se ve así:
from flask import Blueprint, request, jsonify

# Agrégale current_app:
from flask import Blueprint, request, jsonify, current_app




def dashboard_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('web_user_id'):
            return redirect(url_for('dashboard.login_page'))
        return view_func(*args, **kwargs)
    return wrapper


def admin_required():
    return session.get('web_role') == 'ADMIN'


@dashboard_bp.get('/login')
def login_page():
    if session.get('web_user_id'):
        return redirect(url_for('dashboard.index'))
    return render_template('dashboard/login.html')


@dashboard_bp.get('/refresh')
@dashboard_required
def refresh_page():
    flash('Panel actualizado correctamente.', 'info')
    return redirect(request.referrer or url_for('dashboard.index'))


@dashboard_bp.get('/api/status')
@dashboard_required
def api_status():
    return jsonify({'ok': True, 'message': 'Dashboard operativo'})


@dashboard_bp.get('/')
@dashboard_required
def index():
    nombre = session.get('web_name')
    lecturas_recientes = Lectura.query.order_by(Lectura.id.desc()).limit(6).all()
    incidencias_recientes = Incidencia.query.order_by(Incidencia.id.desc()).limit(6).all()
    total_recaudado = sum(m.monto for m in MovimientoCaja.query.filter_by(tipo_movimiento='INGRESO').all())
    total_pendiente = sum(p.total_pagar for p in Planilla.query.filter(Planilla.estado != 'PAGADO').all())
    return render_template('dashboard/index.html', nombre=nombre, total_usuarios=Usuario.query.count(), total_lecturas=Lectura.query.count(), total_incidencias=Incidencia.query.count(), total_avisos=Aviso.query.count(), total_planillas=Planilla.query.count(), total_recaudado=total_recaudado, total_pendiente=total_pendiente, lecturas_recientes=lecturas_recientes, incidencias_recientes=incidencias_recientes, incidencias_abiertas=Incidencia.query.filter(Incidencia.estado != 'CERRADA').count())


@dashboard_bp.route('/usuarios', methods=['GET', 'POST'])
@dashboard_required
def usuarios_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        action = request.form.get('action', 'create')
        if action == 'delete':
            user = Usuario.query.get_or_404(to_int(request.form.get('user_id')))
            user.estado = 'INACTIVO'
            db.session.commit()
            flash('Usuario desactivado correctamente.', 'success')
            return redirect(url_for('dashboard.usuarios_view'))
        if action == 'reset_password':
            user = Usuario.query.get_or_404(to_int(request.form.get('user_id')))
            nueva = request.form.get('nueva_password', '').strip()
            confirmar = request.form.get('confirmar_password', '').strip()
            if not nueva or len(nueva) < 6:
                flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
                return redirect(url_for('dashboard.usuarios_view'))
            if nueva != confirmar:
                flash('Las contraseñas no coinciden.', 'danger')
                return redirect(url_for('dashboard.usuarios_view'))
            user.password_hash = generate_password_hash(nueva)
            db.session.commit()
            flash(f'Contraseña de {user.nombre_completo} restablecida correctamente.', 'success')
            return redirect(url_for('dashboard.usuarios_view'))
        if action == 'update':
            user = Usuario.query.get_or_404(to_int(request.form.get('user_id')))
            rol = Rol.query.filter_by(nombre=(request.form.get('rol') or user.rol.nombre).upper()).first()
            user.rol_id = rol.id if rol else user.rol_id
            user.cedula = request.form.get('cedula') or user.cedula
            user.nombres = request.form.get('nombres') or user.nombres
            user.apellidos = request.form.get('apellidos') or user.apellidos
            user.telefono = request.form.get('telefono') or user.telefono
            user.email = request.form.get('email') or user.email
            user.username = request.form.get('username') or user.username
            user.direccion_referencia = request.form.get('direccion') or user.direccion_referencia
            user.estado = request.form.get('estado') or user.estado
            if request.form.get('password'):
                user.password_hash = generate_password_hash(request.form.get('password'))
            if user.socio:
                user.socio.codigo_socio = request.form.get('codigo_socio') or user.socio.codigo_socio
                user.socio.numero_medidor = request.form.get('numero_medidor') or user.socio.numero_medidor
                if user.socio.viviendas:
                    vivienda = user.socio.viviendas[0]
                    vivienda.direccion = request.form.get('direccion') or vivienda.direccion
                    vivienda.referencia = request.form.get('referencia') or vivienda.referencia
                    vivienda.latitud = to_float(request.form.get('latitud')) if request.form.get('latitud') else vivienda.latitud
                    vivienda.longitud = to_float(request.form.get('longitud')) if request.form.get('longitud') else vivienda.longitud
                if user.socio.medidores:
                    medidor = user.socio.medidores[0]
                    medidor.numero_medidor = request.form.get('numero_medidor') or medidor.numero_medidor
                    medidor.marca = request.form.get('marca_medidor') or medidor.marca
                    medidor.modelo = request.form.get('modelo_medidor') or medidor.modelo
            db.session.commit()
            flash('Usuario actualizado correctamente.', 'success')
            return redirect(url_for('dashboard.usuarios_view'))
        rol = Rol.query.filter_by(nombre=(request.form.get('rol') or 'SOCIO').upper()).first()
        user = Usuario(rol_id=rol.id, cedula=request.form.get('cedula'), nombres=request.form.get('nombres'), apellidos=request.form.get('apellidos'), telefono=request.form.get('telefono'), email=request.form.get('email'), username=request.form.get('username'), password_hash=generate_password_hash(request.form.get('password') or 'Temporal123*'), direccion_referencia=request.form.get('direccion'), estado='ACTIVO')
        db.session.add(user)
        db.session.commit()
        if rol.nombre == 'SOCIO':
            socio = Socio(usuario_id=user.id, junta_id=1, codigo_socio=request.form.get('codigo_socio') or f'SOC-{user.id:03d}', numero_medidor=request.form.get('numero_medidor') or f'MED-{user.id:03d}', estado_servicio='ACTIVO', fecha_ingreso=now_date_str())
            db.session.add(socio)
            db.session.commit()
            vivienda = Vivienda(socio_id=socio.id, sector_id=to_int(request.form.get('sector_id')) or 1, codigo_vivienda=request.form.get('codigo_vivienda') or f'VIV-{user.id:03d}', direccion=request.form.get('direccion') or 'Sin dirección', referencia=request.form.get('referencia'), latitud=to_float(request.form.get('latitud')), longitud=to_float(request.form.get('longitud')), tipo_vivienda=request.form.get('tipo_vivienda') or 'CASA')
            db.session.add(vivienda)
            db.session.commit()
            db.session.add(Medidor(socio_id=socio.id, vivienda_id=vivienda.id, numero_medidor=request.form.get('numero_medidor') or f'MED-{user.id:03d}', marca=request.form.get('marca_medidor'), modelo=request.form.get('modelo_medidor'), estado='ACTIVO', fecha_instalacion=now_date_str()))
            db.session.commit()
        flash('Usuario creado correctamente.', 'success')
        return redirect(url_for('dashboard.usuarios_view'))
    usuarios = Usuario.query.order_by(Usuario.id.desc()).all()
    return render_template('dashboard/users.html', usuarios=usuarios, roles=Rol.query.all(), sectores=Sector.query.order_by(Sector.nombre).all())


@dashboard_bp.route('/lecturas', methods=['GET', 'POST'])
@dashboard_required
def lecturas_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)

        lectura_id = to_int(request.form.get('lectura_id'))
        lectura = Lectura.query.get_or_404(lectura_id)
        action = (request.form.get('action') or 'update').strip()

        if action == 'delete':
            lectura.estado = 'ANULADA'
            lectura.actualizado_en = datetime.now()
            db.session.commit()
            flash('Lectura anulada correctamente.', 'success')
            return redirect(url_for('dashboard.lecturas_view'))

        if action == 'hard_delete':
            upload_folder = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'Lecturas')
            )

            if getattr(lectura, 'evidencias', None):
                for evidencia in lectura.evidencias:
                    try:
                        if evidencia.ruta_imagen:
                            nombre_archivo = os.path.basename(evidencia.ruta_imagen)
                            ruta_archivo = os.path.join(upload_folder, nombre_archivo)
                            if os.path.exists(ruta_archivo):
                                os.remove(ruta_archivo)
                    except Exception:
                        pass

            planillas = Planilla.query.filter_by(lectura_id=lectura.id).all()
            for planilla in planillas:
                db.session.delete(planilla)

            if getattr(lectura, 'consumo', None):
                db.session.delete(lectura.consumo)

            if getattr(lectura, 'evidencias', None):
                for evidencia in lectura.evidencias:
                    db.session.delete(evidencia)

            db.session.delete(lectura)
            db.session.commit()
            flash('Lectura eliminada definitivamente.', 'success')
            return redirect(url_for('dashboard.lecturas_view'))

        nueva_observacion = request.form.get('observacion')
        nuevo_estado = request.form.get('estado')
        nueva_lectura_actual = request.form.get('lectura_actual')

        if nueva_observacion is not None:
            lectura.observacion = nueva_observacion.strip()

        if nuevo_estado:
            lectura.estado = nuevo_estado.strip()

        if nueva_lectura_actual:
            lectura.lectura_actual = to_float(nueva_lectura_actual)
            lectura_anterior = lectura.lectura_anterior or 0
            lectura_actual = lectura.lectura_actual or 0
            lectura.consumo_calculado = max(0, lectura_actual - lectura_anterior)

        foto = request.files.get('foto_evidencia')
        if foto and foto.filename:
            nombre_seguro = secure_filename(foto.filename)
            extension = os.path.splitext(nombre_seguro)[1].lower()

            if not extension:
                extension = '.jpg'

            carpeta_lecturas = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'Lecturas')
            )
            os.makedirs(carpeta_lecturas, exist_ok=True)

            nombre_final = f"lectura_{lectura.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{extension}"
            ruta_fisica = os.path.join(carpeta_lecturas, nombre_final)
            foto.save(ruta_fisica)

            ruta_relativa = f"Lecturas/{nombre_final}"

            evidencia = LecturaEvidencia(
                lectura_id=lectura.id,
                ruta_imagen=ruta_relativa
            )
            db.session.add(evidencia)

        lectura.actualizado_en = datetime.now()
        db.session.commit()
        flash('Lectura actualizada correctamente.', 'success')
        return redirect(url_for('dashboard.lecturas_view'))

    buscar = (request.args.get('buscar') or '').strip()
    fecha = (request.args.get('fecha') or '').strip()
    hora = (request.args.get('hora') or '').strip()
    dia = (request.args.get('dia') or '').strip()

    consulta = Lectura.query

    if buscar:
        consulta = consulta.outerjoin(Socio, Lectura.socio_id == Socio.id) \
                           .outerjoin(Usuario, Socio.usuario_id == Usuario.id) \
                           .outerjoin(Medidor, Lectura.medidor_id == Medidor.id) \
                           .filter(
                               db.or_(
                                   Usuario.cedula.ilike(f"%{buscar}%"),
                                   Usuario.nombres.ilike(f"%{buscar}%"),
                                   Usuario.apellidos.ilike(f"%{buscar}%"),
                                   Medidor.numero_medidor.ilike(f"%{buscar}%")
                               )
                           )

    if fecha:
        consulta = consulta.filter(Lectura.fecha_lectura == fecha)

    if hora:
        consulta = consulta.filter(db.func.substr(Lectura.hora_lectura, 1, 5) == hora)

    if dia:
        mapa_dias = {
            'Sunday': '0',
            'Monday': '1',
            'Tuesday': '2',
            'Wednesday': '3',
            'Thursday': '4',
            'Friday': '5',
            'Saturday': '6',
            'Domingo': '0',
            'Lunes': '1',
            'Martes': '2',
            'Miércoles': '3',
            'Miercoles': '3',
            'Jueves': '4',
            'Viernes': '5',
            'Sábado': '6',
            'Sabado': '6'
        }
        numero_dia = mapa_dias.get(dia)
        if numero_dia is not None:
            consulta = consulta.filter(
                db.func.strftime('%w', Lectura.fecha_lectura) == numero_dia
            )

    lecturas = consulta.order_by(Lectura.id.desc()).all()

    print("======================================")
    print("DB URI:", current_app.config.get("SQLALCHEMY_DATABASE_URI"))
    print("TOTAL LECTURAS EN VISTA:", len(lecturas))
    for item in lecturas:
        print("LECTURA:", item.id, item.fecha_lectura, item.hora_lectura, item.estado)
    print("======================================")

    return render_template(
        'dashboard/lecturas.html',
        lecturas=lecturas,
        buscar=buscar,
        fecha=fecha,
        hora=hora,
        dia=dia
    )
@dashboard_bp.route('/incidencias', methods=['GET', 'POST'])
@dashboard_required
def incidencias_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        incidencia = Incidencia.query.get_or_404(to_int(request.form.get('incidencia_id')))
        action = request.form.get('action', 'update')
        if action == 'delete':
            incidencia.estado = 'CERRADA'
            db.session.commit()
            flash('Incidencia cerrada correctamente.', 'success')
            return redirect(url_for('dashboard.incidencias_view'))
        incidencia.titulo = request.form.get('titulo') or incidencia.titulo
        incidencia.descripcion = request.form.get('descripcion') or incidencia.descripcion
        incidencia.prioridad = request.form.get('prioridad') or incidencia.prioridad
        incidencia.estado = request.form.get('estado') or incidencia.estado
        db.session.commit()
        flash('Incidencia actualizada correctamente.', 'success')
        return redirect(url_for('dashboard.incidencias_view'))
    return render_template('dashboard/incidencias.html', incidencias=Incidencia.query.order_by(Incidencia.id.desc()).all())


@dashboard_bp.route('/avisos', methods=['GET', 'POST'])
@dashboard_required
def avisos_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        action = request.form.get('action', 'create')
        if action == 'delete':
            aviso = Aviso.query.get_or_404(to_int(request.form.get('aviso_id')))
            db.session.delete(aviso)
            db.session.commit()
            flash('Aviso eliminado correctamente.', 'success')
            return redirect(url_for('dashboard.avisos_view'))
        if action == 'update':
            aviso = Aviso.query.get_or_404(to_int(request.form.get('aviso_id')))
            aviso.titulo = request.form.get('titulo') or aviso.titulo
            aviso.contenido = request.form.get('contenido') or aviso.contenido
            aviso.tipo_aviso = request.form.get('tipo_aviso') or aviso.tipo_aviso
            aviso.prioridad = request.form.get('prioridad') or aviso.prioridad
            aviso.estado = request.form.get('estado') or aviso.estado
            db.session.commit()
            flash('Aviso actualizado correctamente.', 'success')
            return redirect(url_for('dashboard.avisos_view'))
        aviso = Aviso(junta_id=1, creado_por=session['web_user_id'], titulo=request.form.get('titulo') or 'Aviso sin título', contenido=request.form.get('contenido') or '', tipo_aviso=request.form.get('tipo_aviso') or 'COMUNICADO', prioridad=request.form.get('prioridad') or 'MEDIA', fecha_publicacion=request.form.get('fecha_publicacion') or now_date_str(), hora_publicacion=request.form.get('hora_publicacion') or now_time_str(), estado=request.form.get('estado') or 'PUBLICADO', aplica_a_todos=True)
        db.session.add(aviso)
        db.session.commit()
        flash('Aviso creado correctamente.', 'success')
        return redirect(url_for('dashboard.avisos_view'))
    return render_template('dashboard/avisos.html', avisos=Aviso.query.order_by(Aviso.id.desc()).all())


@dashboard_bp.route('/planillas', methods=['GET', 'POST'])
@dashboard_required
def planillas_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        planilla = Planilla.query.get_or_404(to_int(request.form.get('planilla_id')))
        nuevo_estado = request.form.get('estado') or 'PAGADO'
        planilla.estado = nuevo_estado
        planilla.fecha_pago = request.form.get('fecha_pago') or now_date_str()
        planilla.hora_pago = request.form.get('hora_pago') or now_time_str()
        planilla.metodo_pago = request.form.get('metodo_pago') or 'EFECTIVO'
        planilla.referencia_pago = request.form.get('referencia_pago')
        pago = Pago(planilla_id=planilla.id, socio_id=planilla.socio_id, vivienda_id=planilla.vivienda_id, valor_pagado=float(request.form.get('valor_pagado') or planilla.total_pagar), fecha_pago=planilla.fecha_pago, hora_pago=planilla.hora_pago, metodo_pago=planilla.metodo_pago, referencia_pago=planilla.referencia_pago, registrado_por=session['web_user_id'], observacion=request.form.get('observacion'))
        db.session.add(pago)
        db.session.flush()
        db.session.add(MovimientoCaja(tipo_movimiento='INGRESO', categoria='AGUA', referencia_tabla='pagos', referencia_id=pago.id, descripcion=f'Cobro planilla {planilla.numero_planilla}', monto=pago.valor_pagado, fecha=planilla.fecha_pago, hora=planilla.hora_pago, registrado_por=session['web_user_id']))
        db.session.commit()
        flash('Planilla marcada como pagada.', 'success')
        return redirect(url_for('dashboard.planillas_view'))

    # ── FILTROS ──────────────────────────────────────────────
    filtro_medidor = (request.args.get('medidor') or '').strip()
    filtro_socio   = (request.args.get('socio') or '').strip()
    filtro_fecha   = (request.args.get('fecha') or '').strip()

    consulta = Planilla.query \
        .join(Socio, Planilla.socio_id == Socio.id) \
        .join(Usuario, Socio.usuario_id == Usuario.id) \
        .outerjoin(Lectura, Planilla.lectura_id == Lectura.id) \
        .outerjoin(Medidor, Lectura.medidor_id == Medidor.id)

    if filtro_socio:
        consulta = consulta.filter(
            db.or_(
                Usuario.nombres.ilike(f'%{filtro_socio}%'),
                Usuario.apellidos.ilike(f'%{filtro_socio}%'),
                Usuario.cedula.ilike(f'%{filtro_socio}%'),
            )
        )

    if filtro_medidor:
        consulta = consulta.filter(
            Medidor.numero_medidor.ilike(f'%{filtro_medidor}%')
        )

    if filtro_fecha:
        consulta = consulta.filter(Planilla.fecha_emision == filtro_fecha)

    planillas = consulta.order_by(Planilla.id.desc()).all()

    return render_template(
        'dashboard/planillas.html',
        planillas=planillas,
        filtro_medidor=filtro_medidor,
        filtro_socio=filtro_socio,
        filtro_fecha=filtro_fecha,
    )
@dashboard_bp.get('/sesiones')
@dashboard_required
def sesiones_view():
    return render_template('dashboard/sesiones.html', sesiones=Sesion.query.order_by(Sesion.id.desc()).all())


@dashboard_bp.post('/sesiones/<int:sesion_id>/revocar')
@dashboard_required
def revocar_sesion(sesion_id):
    if not admin_required():
        abort(403)
    item = Sesion.query.get_or_404(sesion_id)
    item.revocado = True
    item.fecha_revocacion = f"{now_date_str()} {now_time_str()}"
    db.session.commit()
    flash('Sesión revocada correctamente.', 'success')
    return redirect(url_for('dashboard.sesiones_view'))


@dashboard_bp.route('/medidores', methods=['GET', 'POST'])
@dashboard_required
def medidores_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        action = request.form.get('action', 'update')
        medidor = Medidor.query.get_or_404(to_int(request.form.get('medidor_id')))
        if action == 'delete':
            medidor.estado = 'INACTIVO'
            db.session.commit()
            flash('Medidor desactivado correctamente.', 'success')
            return redirect(url_for('dashboard.medidores_view'))
        medidor.numero_medidor = request.form.get('numero_medidor') or medidor.numero_medidor
        medidor.marca = request.form.get('marca') or medidor.marca
        medidor.modelo = request.form.get('modelo') or medidor.modelo
        medidor.estado = request.form.get('estado') or medidor.estado
        db.session.commit()
        flash('Medidor actualizado correctamente.', 'success')
        return redirect(url_for('dashboard.medidores_view'))
    return render_template('dashboard/medidores.html', medidores=Medidor.query.order_by(Medidor.id.desc()).all())


@dashboard_bp.get('/recaudacion')
@dashboard_required
def recaudacion_view():
    ingresos = MovimientoCaja.query.filter_by(tipo_movimiento='INGRESO').order_by(MovimientoCaja.id.desc()).all()
    total = sum(i.monto for i in ingresos)
    return render_template('dashboard/recaudacion.html', ingresos=ingresos, total=total)


@dashboard_bp.get('/planillas/<int:planilla_id>/imprimir')
@dashboard_required
def imprimir_planilla(planilla_id):
    planilla = Planilla.query.get_or_404(planilla_id)
    return render_template('dashboard/planilla_print.html', planilla=planilla)


@dashboard_bp.get('/lecturas/imprimir')
@dashboard_required
def imprimir_lecturas():
    return render_template('dashboard/lecturas_print.html', lecturas=Lectura.query.order_by(Lectura.id.desc()).all())


@dashboard_bp.get('/mapa-incidencias')
@dashboard_required
def mapa_incidencias_view():
    items = Incidencia.query.filter(Incidencia.latitud.isnot(None), Incidencia.longitud.isnot(None)).order_by(Incidencia.id.desc()).all()
    return render_template('dashboard/mapa_incidencias.html', items=items)


@dashboard_bp.route('/ordenes', methods=['GET', 'POST'])
@dashboard_required
def ordenes_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        tecnico_id = to_int(request.form.get('tecnico_id'))
        item = OrdenTrabajo(tecnico_id=tecnico_id, creado_por=session['web_user_id'], incidencia_id=to_int(request.form.get('incidencia_id')), titulo=request.form.get('titulo') or 'Actividad', descripcion=request.form.get('descripcion') or '', prioridad=request.form.get('prioridad') or 'MEDIA', estado='ASIGNADA', fecha=request.form.get('fecha') or now_date_str(), hora=request.form.get('hora') or now_time_str(), latitud=to_float(request.form.get('latitud')), longitud=to_float(request.form.get('longitud')))
        db.session.add(item)
        db.session.commit()
        flash('Orden creada correctamente.', 'success')
        return redirect(url_for('dashboard.ordenes_view'))
    return render_template('dashboard/ordenes.html', ordenes=OrdenTrabajo.query.order_by(OrdenTrabajo.id.desc()).all(), tecnicos=Usuario.query.join(Usuario.rol).filter_by(nombre='TECNICO').all(), incidencias=Incidencia.query.order_by(Incidencia.id.desc()).limit(50).all())


@dashboard_bp.route('/mensajes', methods=['GET', 'POST'])
@dashboard_required
def mensajes_view():
    if request.method == 'POST':
        remitente_id = session['web_user_id']
        destinatario_id = to_int(request.form.get('destinatario_id'))
        item = Mensaje(remitente_id=remitente_id, destinatario_id=destinatario_id, asunto=request.form.get('asunto') or 'Mensaje', contenido=request.form.get('contenido') or '', estado='ENVIADO', leido=False, fecha=now_date_str(), hora=now_time_str())
        db.session.add(item)
        db.session.commit()
        flash('Mensaje enviado correctamente.', 'success')
        return redirect(url_for('dashboard.mensajes_view'))
    msgs = Mensaje.query.order_by(Mensaje.id.desc()).limit(100).all()
    users = Usuario.query.order_by(Usuario.nombres).all()
    return render_template('dashboard/mensajes.html', mensajes=msgs, usuarios=users)


@dashboard_bp.route('/tarifas', methods=['GET','POST'])
@dashboard_required
def tarifas_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        item_id = to_int(request.form.get('tarifa_asignada_id'))
        if item_id:
            item = TarifaAsignada.query.get_or_404(item_id)
            item.nombre = request.form.get('nombre') or item.nombre
            item.base_consumo_m3 = to_float(request.form.get('base_consumo_m3')) or item.base_consumo_m3
            item.valor_base = to_float(request.form.get('valor_base')) or item.valor_base
            item.valor_adicional_m3 = to_float(request.form.get('valor_adicional_m3')) or item.valor_adicional_m3
            item.multa_atraso = to_float(request.form.get('multa_atraso')) or item.multa_atraso
            item.estado = request.form.get('estado') or item.estado
        else:
            item = TarifaAsignada(socio_id=to_int(request.form.get('socio_id')), vivienda_id=to_int(request.form.get('vivienda_id')), nombre=request.form.get('nombre') or 'Tarifa personalizada', base_consumo_m3=to_float(request.form.get('base_consumo_m3')) or 0, valor_base=to_float(request.form.get('valor_base')) or 0, valor_adicional_m3=to_float(request.form.get('valor_adicional_m3')) or 0, multa_atraso=to_float(request.form.get('multa_atraso')) or 0, estado=request.form.get('estado') or 'ACTIVA')
            db.session.add(item)
        db.session.commit()
        flash('Tarifa guardada correctamente.', 'success')
        return redirect(url_for('dashboard.tarifas_view'))
    return render_template('dashboard/tarifas.html', tarifas=TarifaAsignada.query.order_by(TarifaAsignada.id.desc()).all(), usuarios=Usuario.query.order_by(Usuario.nombres).all())


@dashboard_bp.get('/ordenes/<int:orden_id>/imprimir')
@dashboard_required
def imprimir_orden_dashboard(orden_id):
    orden = OrdenTrabajo.query.get_or_404(orden_id)
    return render_template('dashboard/orden_print.html', orden=orden)


@dashboard_bp.post('/sincronizar-alertas')
@dashboard_required
def sync_alertas_view():
    if not admin_required():
        abort(403)
    result = sync_system_alerts()
    flash(f"Alertas sincronizadas. Nuevas: {result['created']}", 'success')
    return redirect(request.referrer or url_for('dashboard.index'))


@dashboard_bp.post('/notificaciones/enviar')
@dashboard_required
def enviar_notificacion():
    if not admin_required():
        abort(403)

    titulo = request.form.get('titulo', '').strip()
    mensaje = request.form.get('mensaje', '').strip()
    tipo = request.form.get('tipo', 'SISTEMA')
    destinatario = request.form.get('destinatario', 'todos')
    usuario_id = to_int(request.form.get('usuario_id'))

    if not titulo or not mensaje:
        flash('El título y mensaje son obligatorios.', 'danger')
        return redirect(url_for('dashboard.notificaciones_view'))

    if destinatario == 'todos':
        usuarios = Usuario.query.filter_by(estado='ACTIVO').all()
        for u in usuarios:
            db.session.add(Notificacion(
                usuario_id=u.id,
                titulo=titulo,
                mensaje=mensaje,
                tipo=tipo,
                leido=False,
                fecha=now_date_str(),
                hora=now_time_str()
            ))
        flash(f'Notificación enviada a {len(usuarios)} usuarios.', 'success')
    else:
        if not usuario_id:
            flash('Selecciona un usuario.', 'danger')
            return redirect(url_for('dashboard.notificaciones_view'))
        db.session.add(Notificacion(
            usuario_id=usuario_id,
            titulo=titulo,
            mensaje=mensaje,
            tipo=tipo,
            leido=False,
            fecha=now_date_str(),
            hora=now_time_str()
        ))
        flash('Notificación enviada correctamente.', 'success')

    db.session.commit()
    return redirect(url_for('dashboard.notificaciones_view'))


@dashboard_bp.get('/notificaciones')
@dashboard_required
def notificaciones_view():
    return render_template(
        'dashboard/notificaciones.html',
        notificaciones=Notificacion.query.order_by(Notificacion.id.desc()).all(),
        usuarios=Usuario.query.filter_by(estado='ACTIVO').order_by(Usuario.nombres).all()
    )

@dashboard_bp.get('/pagos')
@dashboard_required
def pagos_view():
    return render_template('dashboard/pagos.html', pagos=Pago.query.order_by(Pago.id.desc()).all())


@dashboard_bp.get('/movimientos-caja')
@dashboard_required
def movimientos_view():
    return render_template('dashboard/movimientos.html', movimientos=MovimientoCaja.query.order_by(MovimientoCaja.id.desc()).all())


@dashboard_bp.route('/reuniones', methods=['GET', 'POST'])
@dashboard_required
def reuniones_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        rid = to_int(request.form.get('reunion_id'))
        action = request.form.get('action', 'create')
        if rid:
            item = Reunion.query.get_or_404(rid)
            if action == 'delete':
                db.session.delete(item)
                db.session.commit()
                flash('Reunión eliminada correctamente.', 'success')
                return redirect(url_for('dashboard.reuniones_view'))
            item.titulo = request.form.get('titulo') or item.titulo
            item.descripcion = request.form.get('descripcion') or item.descripcion
            item.lugar = request.form.get('lugar') or item.lugar
            item.fecha = request.form.get('fecha') or item.fecha
            item.hora = request.form.get('hora') or item.hora
            item.estado = request.form.get('estado') or item.estado
        else:
            item = Reunion(junta_id=1, creado_por=session['web_user_id'], titulo=request.form.get('titulo') or 'Reunión', descripcion=request.form.get('descripcion'), lugar=request.form.get('lugar'), fecha=request.form.get('fecha') or now_date_str(), hora=request.form.get('hora') or now_time_str(), estado=request.form.get('estado') or 'PROGRAMADA')
            db.session.add(item)
        db.session.commit()
        flash('Reunión guardada correctamente.', 'success')
        return redirect(url_for('dashboard.reuniones_view'))
    return render_template('dashboard/reuniones.html', reuniones=Reunion.query.order_by(Reunion.fecha.desc(), Reunion.hora.desc()).all())

@dashboard_bp.route('/recordatorios', methods=['GET', 'POST'])
@dashboard_required
def recordatorios_view():
    if request.method == 'POST':
        if not admin_required():
            abort(403)
        rid = to_int(request.form.get('recordatorio_id'))
        action = request.form.get('action', 'create')
        if rid:
            item = Recordatorio.query.get_or_404(rid)
            if action == 'delete':
                db.session.delete(item)
                db.session.commit()
                flash('Recordatorio eliminado correctamente.', 'success')
                return redirect(url_for('dashboard.recordatorios_view'))
            item.titulo = request.form.get('titulo') or item.titulo
            item.descripcion = request.form.get('descripcion') or item.descripcion
            item.tipo = request.form.get('tipo') or item.tipo
            item.fecha = request.form.get('fecha') or item.fecha
            item.hora = request.form.get('hora') or item.hora
            item.enviado = request.form.get('enviado') == 'on'
        else:
            item = Recordatorio(usuario_id=to_int(request.form.get('usuario_id')) or session['web_user_id'], titulo=request.form.get('titulo') or 'Recordatorio', descripcion=request.form.get('descripcion'), tipo=request.form.get('tipo') or 'SISTEMA', fecha=request.form.get('fecha') or now_date_str(), hora=request.form.get('hora') or now_time_str(), enviado=False)
            db.session.add(item)
        db.session.commit()
        flash('Recordatorio guardado correctamente.', 'success')
        return redirect(url_for('dashboard.recordatorios_view'))
    return render_template('dashboard/recordatorios.html', recordatorios=Recordatorio.query.order_by(Recordatorio.fecha.desc(), Recordatorio.hora.desc()).all(), usuarios=Usuario.query.order_by(Usuario.nombres).all())



@dashboard_bp.get('/debug-lecturas')
@dashboard_required
def debug_lecturas():
    total = Lectura.query.count()
    lecturas = Lectura.query.limit(5).all()
    resultado = {
        "total_lecturas": total,
        "db_uri": current_app.config.get("SQLALCHEMY_DATABASE_URI"),
        "muestra": [
            {
                "id": l.id,
                "fecha": str(l.fecha_lectura),
                "estado": l.estado,
                "socio_id": l.socio_id
            } for l in lecturas
        ]
    }
    return jsonify(resultado)

@dashboard_bp.post('/planillas/generar')
@dashboard_required
def generar_planillas():
    if not admin_required():
        abort(403)
    lecturas = Lectura.query.filter(Lectura.estado != 'ANULADA').all()
    generadas = 0
    errores = 0
    for lectura in lecturas:
        existe = Planilla.query.filter_by(lectura_id=lectura.id).first()
        if existe:
            continue
        try:
            consumo = max(0, (lectura.lectura_actual or 0) - (lectura.lectura_anterior or 0))
            tarifa = TarifaAsignada.query.filter_by(socio_id=lectura.socio_id, estado='ACTIVA').first()
            cargo_fijo = tarifa.valor_base if tarifa else 2.0
            valor_m3 = tarifa.valor_adicional_m3 if tarifa else 0.5
            base_m3 = tarifa.base_consumo_m3 if tarifa else 10.0
            subtotal = cargo_fijo + (max(0, consumo - base_m3) * valor_m3)
            total = round(subtotal, 2)
            fecha_dt = datetime.now()
            numero = f"PLA-{lectura.socio_id:04d}-{fecha_dt.year}{fecha_dt.month:02d}-{lectura.id:04d}"
            planilla = Planilla(
                socio_id=lectura.socio_id,
                vivienda_id=lectura.vivienda_id,
                lectura_id=lectura.id,
                periodo_anio=fecha_dt.year,
                periodo_mes=fecha_dt.month,
                numero_planilla=numero,
                fecha_emision=now_date_str(),
                lectura_anterior=lectura.lectura_anterior,
                lectura_actual=lectura.lectura_actual,
                consumo_m3=consumo,
                cargo_fijo=cargo_fijo,
                valor_m3=valor_m3,
                subtotal_consumo=subtotal,
                recargo=0, multa=0, otros=0,
                total_pagar=total,
                estado='PENDIENTE',
            )
            db.session.add(planilla)
            generadas += 1
        except Exception as e:
            errores += 1
            print(f"Error lectura {lectura.id}: {e}")
    db.session.commit()
    flash(f'Planillas generadas: {generadas}. Errores: {errores}.', 'success')
    return redirect(url_for('dashboard.planillas_view'))


@dashboard_bp.get('/iot')
@dashboard_required
def iot_view():
    import requests as req
    
    # Datos en tiempo real del ESP32
    esp32_data = {}
    esp32_online = False
    try:
        r = req.get('http://192.168.18.51/datos', timeout=3)
        if r.status_code == 200:
            esp32_data = r.json()
            esp32_online = True
    except:
        esp32_online = False

    # Historial de lecturas IoT del medidor 3
    from app.models import Lectura
    lecturas = Lectura.query.filter(
        Lectura.medidor_id == 3,
        Lectura.observacion.like('IoT%')
    ).order_by(Lectura.id.desc()).limit(30).all()

    # Consumo por día
    consumo_dia = {}
    for l in lecturas:
        fecha = l.fecha_lectura or 'Sin fecha'
        consumo_dia[fecha] = consumo_dia.get(fecha, 0) + (l.consumo_calculado or 0)

    datos_grafica = [
        {'fecha': k, 'm3': round(v, 5), 'litros': round(v * 1000, 2)}
        for k, v in sorted(consumo_dia.items())
    ]

    total_m3     = sum(l.consumo_calculado or 0 for l in lecturas)
    total_litros = total_m3 * 1000

    return render_template(
        'dashboard/iot.html',
        esp32_data   = esp32_data,
        esp32_online = esp32_online,
        lecturas     = lecturas,
        datos_grafica= datos_grafica,
        total_m3     = round(total_m3, 5),
        total_litros = round(total_litros, 2),
    )


# ── RUTA PARA SERVIR IMÁGENES SUBIDAS ────────────────────────────────────────
@dashboard_bp.get('/uploads/<path:filename>')
def uploaded_file(filename):
    upload_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'uploads'))
    return send_from_directory(upload_folder, filename)