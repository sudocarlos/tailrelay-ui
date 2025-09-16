import { fetchProxies, createProxy, stopProxy, startProxy, deleteProxy } from './api.js';
import { renderProxyTable, showAlert } from './ui.js';

async function loadProxies() {
    try {
        const data = await fetchProxies();
        renderProxyTable(data);
    } catch (e) {
        showAlert(`Could not load proxies: ${e.message}`, 'danger');
    }
}

// ------------------------------------------------------------------
// Create proxy modal
document.getElementById('add-proxy').addEventListener('click', () => {
    const modal = new bootstrap.Modal(document.getElementById('proxyModal'));
    modal.show();
});

document.getElementById('proxyForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const payload = {
        listening_port: form.listening_port.value,
        target_host: form.target_host.value,
        target_port: form.target_port.value,
    };

    try {
        const res = await createProxy(payload);
        showAlert(`Proxy #${res.id} created`);
        loadProxies(); // refresh table
        form.reset();
        bootstrap.Modal.getInstance(document.getElementById('proxyModal')).hide();
    } catch (err) {
        showAlert(`Error: ${err.message}`, 'danger');
    }
});

// ------------------------------------------------------------------
// Delegated event listeners for table actions
document.querySelector('#proxy-table tbody').addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const id = btn.dataset.id;

    try {
        if (btn.classList.contains('stop-proxy')) {
            await stopProxy(id);
            showAlert(`Proxy #${id} stopped`);
        } else if (btn.classList.contains('start-proxy')) {
            await startProxy(id);
            showAlert(`Proxy #${id} started`);
        } else if (btn.classList.contains('delete-proxy')) {
            await deleteProxy(id);
            showAlert(`Proxy #${id} deleted`);
        }
        loadProxies();
    } catch (err) {
        showAlert(`Action failed for #${id}: ${err.message}`, 'danger');
    }
});

// ------------------------------------------------------------------
// Refresh button
document.getElementById('refresh-proxies').addEventListener('click', loadProxies);

// ------------------------------------------------------------------
// Initial load
window.addEventListener('DOMContentLoaded', () => {
    loadProxies();
    // Optional: setInterval(loadProxies, 15000);
});