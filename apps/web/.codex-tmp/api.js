"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getConfigs = getConfigs;
exports.getConfig = getConfig;
exports.createConfig = createConfig;
exports.updateConfig = updateConfig;
exports.deleteConfig = deleteConfig;
exports.getProviderTypes = getProviderTypes;
exports.parseInquiry = parseInquiry;
exports.exportInquiry = exportInquiry;
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
async function ensureOk(response) {
    if (response.ok) {
        return;
    }
    let message = "请求失败";
    try {
        const payload = (await response.json());
        message = payload.detail ?? message;
    }
    catch {
        message = response.statusText || message;
    }
    throw new Error(message);
}
// 配置管理 API
async function getConfigs() {
    const response = await fetch(`${API_BASE_URL}/configs`);
    await ensureOk(response);
    return (await response.json());
}
async function getConfig(providerType) {
    const response = await fetch(`${API_BASE_URL}/configs/${providerType}`);
    await ensureOk(response);
    return (await response.json());
}
async function createConfig(config) {
    const response = await fetch(`${API_BASE_URL}/configs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
    await ensureOk(response);
    return (await response.json());
}
async function updateConfig(providerType, config) {
    const response = await fetch(`${API_BASE_URL}/configs/${providerType}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
    await ensureOk(response);
    return (await response.json());
}
async function deleteConfig(providerType) {
    const response = await fetch(`${API_BASE_URL}/configs/${providerType}`, {
        method: "DELETE",
    });
    await ensureOk(response);
}
async function getProviderTypes() {
    const response = await fetch(`${API_BASE_URL}/configs/providers`);
    await ensureOk(response);
    return (await response.json());
}
async function parseInquiry(files, maxPages) {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const url = maxPages ? `${API_BASE_URL}/inquiry/parse?max_pages=${maxPages}` : `${API_BASE_URL}/inquiry/parse`;
    const response = await fetch(url, {
        method: "POST",
        body: formData,
    });
    await ensureOk(response);
    return (await response.json());
}
async function exportInquiry(result, format) {
    const response = await fetch(`${API_BASE_URL}/inquiry/export?format=${format}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ result }),
    });
    await ensureOk(response);
    return response.blob();
}
