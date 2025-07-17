from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import asc, desc, case
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Definición del modelo de la tarea
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    is_urgent = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), default='Pendiente') # 'Pendiente', 'En Progreso', 'Completado'

    def __repr__(self):
        return f'<Task {self.id}: {self.content}>'

# Crear la base de datos si no existe
with app.app_context():
    db.create_all()

# Estados de las tareas para usar en los desplegables y filtros
TASK_STATUSES = ['Pendiente', 'En Progreso', 'Completado']

@app.route('/')
def index():
    view_mode = request.args.get('view_mode', 'kanban') # Default to 'kanban'
    filter_urgent = request.args.get('urgent')
    filter_important = request.args.get('important')
    filter_status = request.args.get('status', 'all') # Default to 'all' for status filter

    # Construir la consulta principal con todos los filtros
    query = Task.query

    if filter_urgent == 'true':
        query = query.filter_by(is_urgent=True)
    elif filter_urgent == 'false':
        query = query.filter_by(is_urgent=False)

    if filter_important == 'true':
        query = query.filter_by(is_important=True)
    elif filter_important == 'false':
        query = query.filter_by(is_important=False)

    if filter_status != 'all':
        query = query.filter_by(status=filter_status)

    # Obtener las tareas ya filtradas por todos los parámetros
    # tasks = query.order_by(Task.due_date.asc(), Task.id.asc()).all()

    tasks = query.order_by(
        # Las tareas NO completadas (False) irán antes que las completadas (True)
        case(
            (Task.status == 'Completado', 1), # Si es completado, dale un valor más alto (irá al final)
            else_=0                           # De lo contrario, dale un valor más bajo (irá primero)
        ).asc(),
        Task.due_date.asc(), # Luego, ordena por fecha de vencimiento ascendente
        Task.id.asc()       # Finalmente, por ID ascendente (más recientes primero si fechas iguales)
    ).all()

    # Preparar datos para la vista de Matriz y Lista (agrupada por cuadrantes)
    # Estos cuadrantes se llenarán con las 'tasks' ya filtradas
    quadrants = {
        'do': {'title': 'Cuadrante 1: Hacer (Hoy o Mañana)', 'tasks': [], 'class': 'quadrant-1'},
        'schedule': {'title': 'Cuadrante 2: Agendar (Próximas Semanas)', 'tasks': [], 'class': 'quadrant-2'},
        'delegate': {'title': 'Cuadrante 3: Delegar (Hacer Ahora)', 'tasks': [], 'class': 'quadrant-3'},
        'eliminate': {'title': 'Cuadrante 4: Eliminar (Posponer)', 'tasks': [], 'class': 'quadrant-4'}
    }

    quadrant_counts = {
        'do': 0,
        'schedule': 0,
        'delegate': 0,
        'eliminate': 0
    }

    # Llenar los cuadrantes con las tareas que ya están filtradas por todos los criterios, incluido el estado
    for task in tasks:
        if task.is_urgent and task.is_important:
            quadrants['do']['tasks'].append(task)
            quadrant_counts['do'] += 1
        elif not task.is_urgent and task.is_important:
            quadrants['schedule']['tasks'].append(task)
            quadrant_counts['schedule'] += 1
        elif task.is_urgent and not task.is_important:
            quadrants['delegate']['tasks'].append(task)
            quadrant_counts['delegate'] += 1
        else:
            quadrants['eliminate']['tasks'].append(task)
            quadrant_counts['eliminate'] += 1

    # Determinar si se deben mostrar todos los cuadrantes (esto controla la visualización HTML)
    show_all_quadrants = False
    if view_mode == 'list':
        show_all_quadrants = True
    elif (filter_urgent is None or filter_urgent == '') and \
         (filter_important is None or filter_important == '') and \
         (filter_status is None or filter_status == '' or filter_status == 'all'):
        show_all_quadrants = True
    # Nota: 'show_all_quadrants' ahora solo afecta la estructura de la cuadrícula en HTML,
    # no el filtrado de las tareas que se colocan en los cuadrantes.

    # Preparar tareas para la vista Kanban (agrupadas por estado)
    tasks_by_status = {status: [] for status in TASK_STATUSES}
    if view_mode == 'kanban':
        kanban_query = Task.query.order_by(
            Task.is_important.desc(),
            Task.is_urgent.desc(),
            Task.due_date.asc(),
            Task.id.asc()
        )
        
        # Aplicar filtros de urgente/importante si existen para Kanban
        if filter_urgent == 'true':
            kanban_query = kanban_query.filter_by(is_urgent=True)
        elif filter_urgent == 'false':
            kanban_query = kanban_query.filter_by(is_urgent=False)

        if filter_important == 'true':
            kanban_query = kanban_query.filter_by(is_important=True)
        elif filter_important == 'false':
            kanban_query = kanban_query.filter_by(is_important=False)

        # Aplicar filtro de estado para Kanban si no es 'all'
        if filter_status != 'all':
            kanban_query = kanban_query.filter_by(status=filter_status)

        kanban_tasks = kanban_query.all()

        for task in kanban_tasks:
            tasks_by_status[task.status].append(task)


    return render_template('index.html',
                           tasks=tasks,
                           view_mode=view_mode,
                           task_statuses=TASK_STATUSES,
                           current_urgent_filter=filter_urgent,
                           current_important_filter=filter_important,
                           current_status_filter=filter_status,
                           quadrants=quadrants,
                           quadrant_counts=quadrant_counts,
                           show_all_quadrants=show_all_quadrants,
                           tasks_by_status=tasks_by_status)


@app.route('/add_task', methods=['POST'])
def add_task():
    content = request.form['content']
    is_urgent = 'is_urgent' in request.form
    is_important = 'is_important' in request.form
    due_date_str = request.form.get('due_date')
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

    new_task = Task(content=content, is_urgent=is_urgent, is_important=is_important, due_date=due_date, status='Pendiente')
    db.session.add(new_task)
    db.session.commit()

    # Recuperar los parámetros de la URL para redirigir a la vista actual
    current_view_mode = request.form.get('current_view_mode', 'list')
    current_urgent_filter = request.form.get('current_urgent_filter')
    current_important_filter = request.form.get('current_important_filter')
    current_status_filter = request.form.get('current_status_filter')

    return redirect(url_for('index',
                            view_mode=current_view_mode,
                            urgent=current_urgent_filter if current_urgent_filter else None,
                            important=current_important_filter if current_important_filter else None,
                            status=current_status_filter if current_status_filter else None))

@app.route('/edit_task/<int:task_id>')
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    # Recuperar los parámetros de la URL para pasarlos a la plantilla de edición
    view_mode = request.args.get('view_mode', 'list')
    urgent = request.args.get('urgent')
    important = request.args.get('important')
    status = request.args.get('status')

    return render_template('edit.html',
                           task=task,
                           task_statuses=TASK_STATUSES,
                           view_mode=view_mode,
                           urgent=urgent,
                           important=important,
                           status=status)

@app.route('/update_task/<int:task_id>', methods=['POST'])
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    task.content = request.form['content']
    task.is_urgent = 'is_urgent' in request.form
    task.is_important = 'is_important' in request.form
    task.status = request.form['status']
    due_date_str = request.form.get('due_date')
    task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

    db.session.commit()

    # Recuperar los parámetros de la URL para redirigir a la vista actual
    current_view_mode = request.form.get('current_view_mode', 'list')
    current_urgent_filter = request.form.get('current_urgent_filter')
    current_important_filter = request.form.get('current_important_filter')
    current_status_filter = request.form.get('current_status_filter')

    return redirect(url_for('index',
                            view_mode=current_view_mode,
                            urgent=current_urgent_filter if current_urgent_filter else None,
                            important=current_important_filter if current_important_filter else None,
                            status=current_status_filter if current_status_filter else None))


@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()

    # Recuperar los parámetros de la URL para redirigir a la vista actual
    current_view_mode = request.args.get('view_mode', 'list')
    current_urgent_filter = request.args.get('urgent')
    current_important_filter = request.args.get('important')
    current_status_filter = request.args.get('status')

    return redirect(url_for('index',
                            view_mode=current_view_mode,
                            urgent=current_urgent_filter if current_urgent_filter else None,
                            important=current_important_filter if current_important_filter else None,
                            status=current_status_filter if current_status_filter else None))

@app.route('/api/update_task_status/<int:task_id>', methods=['POST'])
def api_update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    new_status = data.get('new_status')

    if new_status and new_status in TASK_STATUSES:
        task.status = new_status
        db.session.commit()
        return jsonify({'status': task.status, 'message': 'Estado actualizado correctamente'})
    return jsonify({'error': 'Estado inválido o no proporcionado'}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

