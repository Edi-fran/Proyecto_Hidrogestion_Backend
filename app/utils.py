from __future__ import annotations

import csv
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def now_date_str() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def now_time_str() -> str:
    return datetime.now().strftime('%H:%M:%S')


def save_upload(file_storage, category: str) -> tuple[str, str]:
    if not file_storage or file_storage.filename == '':
        raise ValueError('No se recibió ningún archivo.')
    if not allowed_file(file_storage.filename):
        raise ValueError('Tipo de archivo no permitido.')
    original_name = secure_filename(file_storage.filename)
    extension = original_name.rsplit('.', 1)[1].lower()
    unique_name = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{extension}"
    upload_root = Path(current_app.config['UPLOAD_FOLDER'])
    category_dir = upload_root / category
    category_dir.mkdir(parents=True, exist_ok=True)
    abs_path = category_dir / unique_name
    file_storage.save(abs_path)
    return f"{category}/{unique_name}", original_name


def file_size_bytes(relative_path: str) -> int:
    abs_path = Path(current_app.config['UPLOAD_FOLDER']) / relative_path
    return abs_path.stat().st_size if abs_path.exists() else 0


def to_float(value: Optional[str]):
    try:
        return float(value) if value not in (None, '', 'null') else None
    except (TypeError, ValueError):
        return None


def to_int(value: Optional[str]):
    try:
        return int(value) if value not in (None, '', 'null') else None
    except (TypeError, ValueError):
        return None


def export_csv(path: Path, headers: list[str], rows: list[list]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def create_notification(usuario_id: int, titulo: str, mensaje: str, tipo: str, referencia_tabla: str | None = None, referencia_id: int | None = None):
    from app.models import Notificacion
    from app.extensions import db
    db.session.add(Notificacion(usuario_id=usuario_id, titulo=titulo, mensaje=mensaje, tipo=tipo, referencia_tabla=referencia_tabla, referencia_id=referencia_id, fecha=now_date_str(), hora=now_time_str(), leido=False))



def create_audit(usuario_id: int | None, tabla: str, registro_id: int | None, accion: str, detalle: str | None = None, ip: str | None = None):
    from app.models import Auditoria
    from app.extensions import db
    db.session.add(Auditoria(usuario_id=usuario_id, tabla_afectada=tabla, registro_id=registro_id, accion=accion, detalle=detalle, fecha=now_date_str(), hora=now_time_str(), ip=ip))


def sync_system_alerts() -> dict:
    from app.models import Incidencia, Notificacion, OrdenTrabajo, Planilla, Usuario
    from app.extensions import db
    from datetime import datetime, timedelta

    created = 0
    today = datetime.now().date()

    def exists(uid, ref_table, ref_id, title):
        return Notificacion.query.filter_by(usuario_id=uid, referencia_tabla=ref_table, referencia_id=ref_id, titulo=title).first() is not None

    # upcoming and overdue planillas
    for p in Planilla.query.filter(Planilla.estado.in_(['PENDIENTE', 'VENCIDO'])).all():
        if not p.socio or not p.socio.usuario_id or not p.fecha_vencimiento:
            continue
        try:
            due = datetime.strptime(p.fecha_vencimiento, '%Y-%m-%d').date()
        except Exception:
            continue
        days = (due - today).days
        if 0 <= days <= 3 and not exists(p.socio.usuario_id, 'planillas', p.id, 'Planilla por vencer'):
            create_notification(p.socio.usuario_id, 'Planilla por vencer', f'La planilla {p.numero_planilla} vence el {p.fecha_vencimiento}.', 'PAGO', 'planillas', p.id)
            created += 1
        if days < 0:
            if p.estado != 'VENCIDO':
                p.estado = 'VENCIDO'
            if not exists(p.socio.usuario_id, 'planillas', p.id, 'Planilla vencida'):
                create_notification(p.socio.usuario_id, 'Planilla vencida', f'La planilla {p.numero_planilla} se encuentra vencida.', 'PAGO', 'planillas', p.id)
                created += 1

    # technician alerts for pending orders and incidencias
    techs = Usuario.query.join(Usuario.rol).filter_by(nombre='TECNICO').all()
    for tech in techs:
        pending_orders = OrdenTrabajo.query.filter(OrdenTrabajo.tecnico_id == tech.id, OrdenTrabajo.estado.in_(['ASIGNADA', 'EN_PROCESO'])).count()
        if pending_orders and not exists(tech.id, 'ordenes_trabajo', tech.id, 'Órdenes pendientes'):
            create_notification(tech.id, 'Órdenes pendientes', f'Tienes {pending_orders} órdenes técnicas pendientes.', 'ORDEN_TECNICA', 'ordenes_trabajo', tech.id)
            created += 1
        pending_incs = Incidencia.query.filter(Incidencia.estado.in_(['ASIGNADA', 'EN_PROCESO'])).count()
        if pending_incs and not exists(tech.id, 'incidencias', tech.id, 'Incidencias por completar'):
            create_notification(tech.id, 'Incidencias por completar', f'Existen {pending_incs} incidencias por completar o revisar.', 'INCIDENCIA', 'incidencias', tech.id)
            created += 1

    db.session.commit()
    return {'created': created}
