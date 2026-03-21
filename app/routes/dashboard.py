from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for, jsonify
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Aviso, Incidencia, Lectura, Medidor, Mensaje, MovimientoCaja, Notificacion, OrdenTrabajo, Pago, Planilla, Recordatorio, Reunion, Rol, Sector, Sesion, Socio, Tarifa, TarifaAsignada, Usuario, Vivienda
from app.utils import now_date_str, now_time_str, sync_system_alerts, to_float, to_int


dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard', template_folder='../templates', static_folder='../static', static_url_path='/dashboard-static')


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
        lectura = Lectura.query.get_or_404(to_int(request.form.get('lectura_id')))
        action = request.form.get('action', 'update')
        if action == 'delete':
            lectura.estado = 'ANULADA'
            db.session.commit()
            flash('Lectura anulada correctamente.', 'success')
            return redirect(url_for('dashboard.lecturas_view'))
        lectura.observacion = request.form.get('observacion') or lectura.observacion
        lectura.estado = request.form.get('estado') or lectura.estado
        if request.form.get('lectura_actual'):
            lectura.lectura_actual = to_float(request.form.get('lectura_actual'))
        db.session.commit()
        flash('Lectura actualizada correctamente.', 'success')
        return redirect(url_for('dashboard.lecturas_view'))
    return render_template('dashboard/lecturas.html', lecturas=Lectura.query.order_by(Lectura.id.desc()).all())


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
    return render_template('dashboard/planillas.html', planillas=Planilla.query.order_by(Planilla.id.desc()).all())


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


@dashboard_bp.get('/notificaciones')
@dashboard_required
def notificaciones_view():
    return render_template('dashboard/notificaciones.html', notificaciones=Notificacion.query.order_by(Notificacion.id.desc()).all())


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
