/**
 * Fetch all proxies
 */
export async function fetchProxies() {
    try {
        const response = await fetch(`/proxy`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${JSON.parse(await response.text()).error}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch proxies:", error);
        throw error;
    }
}

/**
 * Create a new proxy
 */
export async function createProxy(data) {
    try {
        const response = await fetch(`/proxy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${JSON.parse(await response.text()).error}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to create proxy:", error);
        throw error;
    }
}

/**
 * Delete a proxy by ID
 */
export async function deleteProxy(id) {
    try {
        const response = await fetch(`/proxy/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${JSON.parse(await response.text()).error}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to delete proxy:", error);
        throw error;
    }
}

/**
 * Stop a running proxy
 */
export async function stopProxy(id) {
    try {
        const response = await fetch(`/proxy/${id}`, {
            method: 'PUT'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${JSON.parse(await response.text()).error}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to stop proxy:", error);
        throw error;
    }
}

/**
 * Start a stopped proxy
 */
export async function startProxy(id) {
    try {
        const response = await fetch(`/proxy/${id}/start`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${JSON.parse(await response.text()).error}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to start proxy:", error);
        throw error;
    }
}

/**
 * Create a backup of all proxies
 */
export async function backupProxies() {
    try {
        const response = await fetch(`/backup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${JSON.parse(await response.text()).error}`);

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'proxies-backup.json';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        // Don't call response.json() since we already consumed the response stream
        return; // or return an empty object if needed
    } catch (error) {
        console.error("Failed to create backup:", error);
        throw error;
    }
}

/**
 * Restore proxies from backup file
 * @param {string} mode - Either 'append' or 'overwrite'
 */
export async function restoreProxies(mode = 'append') {
    try {
        // Create file input element
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.style.display = 'none';

        // Trigger file selection
        document.body.appendChild(input);
        input.click();

        // Return a promise that resolves when the file is processed
        return new Promise((resolve, reject) => {
            input.onchange = async () => {
                try {
                    const file = input.files[0];
                    if (!file) {
                        reject(new Error('No file selected'));
                        return;
                    }

                    // Read the file as JSON
                    const reader = new FileReader();
                    reader.onload = async (e) => {
                        try {
                            const backupData = e.target.result;
                            const response = await fetch(`/restore?mode=${mode}`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: backupData
                            });

                            if (!response.ok) throw new Error(`HTTP ${response.status} ${JSON.parse(await response.text()).error}`);

                            // Clean up
                            document.body.removeChild(input);
                            resolve(await response.json());
                        } catch (error) {
                            console.error("Failed to restore proxies:", error);
                            document.body.removeChild(input);
                            reject(error);
                        }
                    };

                    reader.onerror = () => {
                        document.body.removeChild(input);
                        reject(new Error('Failed to read file'));
                    };

                    reader.readAsText(file);
                } catch (error) {
                    console.error("Failed to process file:", error);
                    document.body.removeChild(input);
                    reject(error);
                }
            };

            input.onerror = () => {
                document.body.removeChild(input);
                reject(new Error('File selection failed'));
            };
        });
    } catch (error) {
        console.error("Failed to restore proxies:", error);
        throw error;
    }
}