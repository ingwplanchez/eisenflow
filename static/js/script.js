// Helper function to get a cookie value
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

document.addEventListener('DOMContentLoaded', function() {
    // --- Dark Mode Toggle Logic ---
    const darkModeToggle = document.getElementById('darkModeToggle');
    const body = document.body;

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        body.classList.add('dark-mode');
        darkModeToggle.innerHTML = '<i class="bi bi-sun-fill"></i>';
    } else {
        darkModeToggle.innerHTML = '<i class="bi bi-moon-fill"></i>';
    }

    darkModeToggle.addEventListener('click', () => {
        body.classList.toggle('dark-mode');
        if (body.classList.contains('dark-mode')) {
            localStorage.setItem('theme', 'dark');
            darkModeToggle.innerHTML = '<i class="bi bi-sun-fill"></i>';
        } else {
            localStorage.setItem('theme', 'light');
            darkModeToggle.innerHTML = '<i class="bi bi-moon-fill"></i>';
        }
    });

    // --- Drag and Drop Logic (Kanban View Only) ---
    // Solo inicializar D&D si estamos en la vista Kanban
    if (document.body.querySelector('.kanban-board')) {
        const draggables = document.querySelectorAll('.kanban-task-card');
        const dropzones = document.querySelectorAll('.kanban-column');

        draggables.forEach(task => {
            task.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', task.dataset.taskId);
                task.classList.add('dragging');
            });

            task.addEventListener('dragend', () => {
                task.classList.remove('dragging');
            });
        });

        dropzones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                const draggingTask = document.querySelector('.dragging');
                if (draggingTask) {
                    const afterElement = getDragAfterElement(zone.querySelector('.kanban-tasks'), e.clientY);
                    const tasksContainer = zone.querySelector('.kanban-tasks');
                    if (afterElement == null) {
                        tasksContainer.appendChild(draggingTask);
                    } else {
                        tasksContainer.insertBefore(draggingTask, afterElement);
                    }
                }
            });

            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                const taskId = e.dataTransfer.getData('text/plain');
                const draggedTask = document.querySelector(`[data-task-id="${taskId}"]`);
                const newStatus = zone.dataset.status;
                const oldStatus = draggedTask.dataset.currentStatus; // Captura el estado anterior

                if (draggedTask && newStatus) {
                    // Actualizar el estado visualmente
                    draggedTask.dataset.currentStatus = newStatus;
                    
                    // Si el nuevo estado es 'Completado', aplicar tachado
                    if (newStatus === 'Completado') {
                        draggedTask.querySelector('.task-content').classList.add('completed-text');
                    } else {
                        draggedTask.querySelector('.task-content').classList.remove('completed-text');
                    }

                    // Enviar la actualización al backend
                    fetch(`/api/update_task_status/${taskId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ new_status: newStatus })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            console.error('Error al actualizar estado:', data.error);
                            // Considerar un revert visual o recargar si falla
                        } else {
                            console.log('Estado actualizado:', data.status);
                            
                            // Nuevo código para actualizar los conteos de las columnas
                            const oldColumnHeader = document.querySelector(`#column-${oldStatus.replace(' ', '-') } .kanban-column-header`);
                            const newColumnHeader = document.querySelector(`#column-${newStatus.replace(' ', '-') } .kanban-column-header`);

                            if (oldColumnHeader) {
                                const oldColumnTasksContainer = document.querySelector(`#column-${oldStatus.replace(' ', '-') } .kanban-tasks`);
                                const oldTaskCount = oldColumnTasksContainer.children.length;
                                oldColumnHeader.textContent = `${oldStatus} (${oldTaskCount})`;
                            }

                            if (newColumnHeader) {
                                const newColumnTasksContainer = document.querySelector(`#column-${newStatus.replace(' ', '-') } .kanban-tasks`);
                                const newTaskCount = newColumnTasksContainer.children.length;
                                newColumnHeader.textContent = `${newStatus} (${newTaskCount})`;
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error de red:', error);
                        // Considerar un revert visual o recargar si falla
                    });
                }
            });
        });

        function getDragAfterElement(container, y) {
            const draggableElements = [...container.querySelectorAll('.kanban-task-card:not(.dragging)')];

            return draggableElements.reduce((closest, child) => {
                const box = child.getBoundingClientRect();
                const offset = y - box.top - box.height / 2;
                if (offset < 0 && offset > closest.offset) {
                    return { offset: offset, element: child };
                } else {
                    return closest;
                }
            }, { offset: Number.NEGATIVE_INFINITY }).element;
        }
    } // End of Kanban D&D logic

    // --- Logic for updating task status via checkbox and applying strikethrough (List/Matrix views) ---
    const checkboxes = document.querySelectorAll('.task-completion-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const taskId = this.dataset.taskId;
            const newStatus = this.checked ? 'Completado' : 'Pendiente';
            
            // Actualizar el tachado en el texto de la tarea
            const taskContentSpan = this.closest('.list-group-item').querySelector('span:not(.badge)'); // Selecciona el span del contenido (no el badge)
            if (taskContentSpan) {
                if (this.checked) {
                    taskContentSpan.classList.add('completed-text');
                } else {
                    taskContentSpan.classList.remove('completed-text');
                }
            }

            // Actualizar el estado visual del badge (Pendiente/En Progreso/Completado)
            const statusBadge = this.closest('.list-group-item').querySelector('.badge');
            if (statusBadge) {
                statusBadge.classList.remove('bg-danger', 'bg-warning', 'bg-success');
                if (newStatus === 'Pendiente') {
                    statusBadge.classList.add('bg-danger');
                } else if (newStatus === 'En Progreso') {
                    statusBadge.classList.add('bg-warning');
                } else if (newStatus === 'Completado') {
                    statusBadge.classList.add('bg-success');
                }
                statusBadge.textContent = newStatus; // Actualizar el texto del badge también
            }


            fetch(`/api/update_task_status/${taskId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ new_status: newStatus })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Error al actualizar estado:', data.error);
                    alert('Error al actualizar el estado de la tarea. Por favor, inténtelo de nuevo.');
                    this.checked = !this.checked; // Revertir el estado del checkbox si hay error
                    // Revertir el tachado si hay error
                    if (taskContentSpan) {
                        taskContentSpan.classList.toggle('completed-text', !this.checked);
                    }
                    // Revertir el badge si hay error (más complejo, quizás recargar sea mejor aquí si el error es grave)
                    if (statusBadge && data.old_status) { 
                        // Simplificado: por ahora no se revierte el badge automáticamente en JS si hay error,
                        // el usuario debería recargar o se podría hacer una lógica más robusta.
                    }
                } else {
                    console.log('Estado actualizado:', data.status);
                    // --- NUEVO CÓDIGO AQUÍ ---
                    // Obtener el modo de vista actual desde el atributo data del body
                    const currentViewMode = document.body.dataset.viewMode; 
                    if (currentViewMode === 'list' || currentViewMode === 'matrix') {
                        location.reload(); // Recargar la página para aplicar el nuevo orden
                    }
                    // --- FIN NUEVO CÓDIGO ---
                }
            })
            .catch(error => {
                console.error('Error de red:', error);
                alert('Error de conexión al actualizar el estado. Por favor, inténtelo de nuevo.');
                this.checked = !this.checked; // Revertir el estado del checkbox si hay error de red
                // Revertir el tachado si hay error de red
                if (taskContentSpan) {
                    taskContentSpan.classList.toggle('completed-text', !this.checked);
                }
            });
        });
    });
}); // End DOMContentLoaded