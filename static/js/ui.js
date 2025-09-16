// Build the proxy table
export function renderProxyTable(proxies) {
    const tbody = document.querySelector('#proxy-table tbody');
    tbody.innerHTML = ''; // reset

    proxies.forEach(proxy => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
      <td>${proxy.id}</td>
      <td>${proxy.listening_port}</td>
      <td>${proxy.target_host}</td>
      <td>${proxy.target_port}</td>
      <td>${proxy.process_id ?? '-'}</td>
      <td>${proxy.start_time}</td>
      <td>${proxy.stop_time ?? '-'}</td>
      <td><span class="status badge ${proxy.status === 'running' ? 'bg-success' : 'bg-secondary'
            }">${proxy.status}</span></td>
      <td>
        <button class="btn btn-sm btn-outline-danger stop-proxy" data-id="${proxy.id}">
          Stop
        </button>
        <button class="btn btn-sm btn-outline-success start-proxy" data-id="${proxy.id}">
          Start
        </button>
        <button class="btn btn-sm btn-outline-danger delete-proxy" data-id="${proxy.id}">
          Delete
        </button>
      </td>
    `;
        tbody.appendChild(tr);
    });
}

// Helper for showing alerts
export function showAlert(message, type = 'success') {
    const container = document.querySelector('#alerts');
    const div = document.createElement('div');
    div.className = `alert alert-${type} alert-dismissible fade show`;
    div.role = 'alert';
    div.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;
    container.appendChild(div);

    setTimeout(() => div.remove(), 4000);
}