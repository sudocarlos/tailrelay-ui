// src/api.js

const BASE_URL = 'http://localhost:5000';

/**
 * Fetch all proxies
 */
export async function fetchProxies() {
    try {
        const response = await fetch(`${BASE_URL}/proxy`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
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
        const response = await fetch(`${BASE_URL}/proxy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
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
        const response = await fetch(`${BASE_URL}/proxy/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
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
        const response = await fetch(`${BASE_URL}/proxy/${id}`, {
            method: 'PUT'
        });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
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
        const response = await fetch(`${BASE_URL}/proxy/${id}/start`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error("Failed to start proxy:", error);
        throw error;
    }
}