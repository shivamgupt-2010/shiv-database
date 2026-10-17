document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const authView = document.getElementById('auth-view');
    const dashboardView = document.getElementById('dashboard-view');
    const loginForm = document.getElementById('login-form');
    const loginBtn = document.getElementById('login-btn');
    const loginError = document.getElementById('login-error');
    const logoutBtn = document.getElementById('logout-btn');

    const registerForm = document.getElementById('register-form');
    const registerBtn = document.getElementById('register-btn');
    const registerError = document.getElementById('register-error');

    const showRegisterLink = document.getElementById('show-register-link');
    const showLoginLink = document.getElementById('show-login-link');
    
    const projectsList = document.getElementById('projects-list');
    const newProjectBtn = document.getElementById('new-project-btn');
    const newProjectModal = document.getElementById('new-project-modal');
    const createProjectForm = document.getElementById('create-project-form');
    const closeProjectModal = document.getElementById('close-project-modal');
    
    const keyActions = document.getElementById('key-actions');
    const generateKeyBtn = document.getElementById('generate-key-btn');
    const newKeyModal = document.getElementById('new-key-modal');
    const createKeyForm = document.getElementById('create-key-form');
    const closeKeyModal = document.getElementById('close-key-modal');
    const generatedKeysContainer = document.getElementById('generated-keys-container');

    // State
    let token = localStorage.getItem('shiv_token');
    let currentProjectId = null;

    // Initialize
    if (token) {
        showDashboard();
    }

    // --- Form Toggles ---
    showRegisterLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginForm.classList.add('hidden');
        registerForm.classList.remove('hidden');
    });

    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        registerForm.classList.add('hidden');
        loginForm.classList.remove('hidden');
    });

    // --- Auth ---
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email_or_username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        loginBtn.classList.add('loading');
        loginError.classList.add('hidden');

        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email_or_username, password })
            });
            const data = await res.json();
            
            if (!res.ok) throw new Error(data.detail || 'Authentication failed');
            
            token = data.data.access_token;
            localStorage.setItem('shiv_token', token);
            showDashboard();
        } catch (err) {
            loginError.textContent = err.message;
            loginError.classList.remove('hidden');
        } finally {
            loginBtn.classList.remove('loading');
        }
    });

    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('reg-email').value;
        const username = document.getElementById('reg-username').value;
        const password = document.getElementById('reg-password').value;
        
        registerBtn.classList.add('loading');
        registerError.classList.add('hidden');

        try {
            const res = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, username, password })
            });
            const data = await res.json();
            
            if (!res.ok) throw new Error(data.detail || 'Registration failed');
            
            // On success, show login form and pre-fill username
            registerForm.classList.add('hidden');
            loginForm.classList.remove('hidden');
            document.getElementById('username').value = username;
            
            // Show a temporary success message in login error box for UI feedback
            loginError.textContent = "Registration successful! Please login.";
            loginError.style.color = "var(--success-color, #10b981)";
            loginError.classList.remove('hidden');
        } catch (err) {
            registerError.textContent = err.message;
            registerError.classList.remove('hidden');
        } finally {
            registerBtn.classList.remove('loading');
        }
    });

    logoutBtn.addEventListener('click', () => {
        token = null;
        localStorage.removeItem('shiv_token');
        authView.classList.remove('hidden');
        dashboardView.classList.add('hidden');
    });

    // --- Dashboard UI ---
    async function showDashboard() {
        authView.classList.add('hidden');
        dashboardView.classList.remove('hidden');

        // Fetch current user details to display in navbar
        try {
            const meRes = await apiRequest('/auth/me');
            if (meRes && meRes.data) {
                const badge = document.getElementById('user-info-badge');
                if (badge) {
                    const identifier = meRes.data.email || meRes.data.username;
                    const role = meRes.data.role || 'admin';
                    badge.textContent = `${identifier} (${role})`;
                }
            }
        } catch (err) {
            console.warn('Could not load user profile:', err);
        }

        await fetchProjects();
    }

    async function apiRequest(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...options.headers
        };
        const res = await fetch(endpoint, { ...options, headers });
        if (res.status === 401) {
            token = null;
            localStorage.removeItem('shiv_token');
            authView.classList.remove('hidden');
            dashboardView.classList.add('hidden');
            if (loginError) {
                loginError.textContent = 'Session expired. Please log in again.';
                loginError.classList.remove('hidden');
            }
            throw new Error('Unauthorized');
        }
        if (res.status === 403) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Access forbidden: Insufficient permissions.');
        }
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'API Error');
        return data;
    }

    // --- Projects ---
    async function fetchProjects() {
        try {
            const data = await apiRequest('/projects/');
            renderProjects(data.data || []);
        } catch (err) {
            console.error('Failed to fetch projects', err);
            projectsList.innerHTML = `<li><span class="text-danger" style="color: #ef4444;">${err.message}</span></li>`;
        }
    }

    function renderProjects(projects) {
        projectsList.innerHTML = '';
        if (projects.length === 0) {
            projectsList.innerHTML = '<li><span class="text-muted">No projects found. Click "+ New Project" above to create one.</span></li>';
            keyActions.classList.add('hidden');
            const keysContainer = document.getElementById('keys-list-container');
            if (keysContainer) keysContainer.classList.add('hidden');
            return;
        }

        projects.forEach((p, idx) => {
            const li = document.createElement('li');
            li.setAttribute('data-project-id', p.id);
            li.innerHTML = `
                <div>
                    <strong>${p.name}</strong>
                    <div class="subtitle" style="font-size: 0.8rem; color: #a1a1aa; margin-top: 3px;">Provider: ${p.primary_provider || 'shiv_native'}</div>
                    <div class="subtitle" style="font-family: monospace; font-size: 0.75rem; color: #71717a;">ID: ${p.id}</div>
                </div>
            `;
            li.addEventListener('click', () => selectProject(p.id, li));
            projectsList.appendChild(li);
        });

        // Automatically select active or first project
        if (!currentProjectId && projects.length > 0) {
            const firstLi = projectsList.querySelector('li');
            if (firstLi) firstLi.click();
        } else if (currentProjectId) {
            const activeLi = projectsList.querySelector(`[data-project-id="${currentProjectId}"]`);
            if (activeLi) {
                document.querySelectorAll('#projects-list li').forEach(el => el.classList.remove('active'));
                activeLi.classList.add('active');
            }
        }
    }

    async function selectProject(id, element) {
        currentProjectId = id;
        document.querySelectorAll('#projects-list li').forEach(el => el.classList.remove('active'));
        if (element) element.classList.add('active');
        keyActions.classList.remove('hidden');
        generatedKeysContainer.innerHTML = '';
        await fetchApiKeys(id);
    }

    // --- API Keys Management ---
    async function fetchApiKeys(projectId) {
        const keysContainer = document.getElementById('keys-list-container');
        const keysList = document.getElementById('api-keys-list');
        if (!keysList || !keysContainer) return;

        keysContainer.classList.remove('hidden');
        keysList.innerHTML = '<li><span class="text-muted">Loading API keys...</span></li>';

        try {
            const res = await apiRequest(`/api-keys/${projectId}`);
            renderApiKeys(res.data || []);
        } catch (err) {
            keysList.innerHTML = `<li><span class="text-danger" style="color: #ef4444;">${err.message}</span></li>`;
        }
    }

    function renderApiKeys(keys) {
        const keysList = document.getElementById('api-keys-list');
        if (!keysList) return;
        keysList.innerHTML = '';

        if (keys.length === 0) {
            keysList.innerHTML = '<li><span class="text-muted" style="font-size: 0.85rem;">No API keys yet. Click "Generate New API Key" above.</span></li>';
            return;
        }

        keys.forEach(k => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.justifyContent = 'space-between';
            li.style.alignItems = 'center';
            li.style.padding = '10px 14px';

            const statusBadge = k.revoked 
                ? '<span style="background: rgba(239, 68, 68, 0.2); color: #ef4444; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Revoked</span>'
                : '<span style="background: rgba(16, 185, 129, 0.2); color: #10b981; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Active</span>';
            
            li.innerHTML = `
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem;">${k.name} ${statusBadge}</div>
                    <div class="subtitle" style="font-family: monospace; font-size: 0.8rem; margin-top: 4px; color: #a1a1aa;">Prefix: ${k.key_prefix}...</div>
                </div>
                <div>
                    ${!k.revoked ? `<button type="button" class="btn ghost-btn revoke-btn" data-key-id="${k.id}" style="color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4); padding: 4px 10px; font-size: 0.8rem; border-radius: 4px; cursor: pointer;">Revoke</button>` : ''}
                </div>
            `;

            const revokeBtn = li.querySelector('.revoke-btn');
            if (revokeBtn) {
                revokeBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm(`Revoke API key "${k.name}"? Applications using this key will immediately lose access.`)) {
                        revokeBtn.textContent = 'Revoking...';
                        try {
                            await apiRequest(`/api-keys/${k.id}`, { method: 'DELETE' });
                            await fetchApiKeys(currentProjectId);
                        } catch (err) {
                            alert(err.message);
                        }
                    }
                });
            }
            keysList.appendChild(li);
        });
    }

    newProjectBtn.addEventListener('click', () => {
        newProjectModal.classList.remove('hidden');
    });
    closeProjectModal.addEventListener('click', () => {
        newProjectModal.classList.add('hidden');
    });

    createProjectForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('proj-name').value.trim();
        const description = document.getElementById('proj-desc').value.trim();
        
        const btn = createProjectForm.querySelector('button[type="submit"]');
        btn.textContent = 'Creating...';
        btn.disabled = true;
        
        try {
            const createRes = await apiRequest('/projects/', {
                method: 'POST',
                body: JSON.stringify({ name, description })
            });
            newProjectModal.classList.add('hidden');
            createProjectForm.reset();
            
            // Set currentProjectId to the newly created project
            if (createRes && createRes.data && createRes.data.id) {
                currentProjectId = createRes.data.id;
            }
            await fetchProjects();
        } catch (err) {
            alert('Failed to create project: ' + err.message);
        } finally {
            btn.textContent = 'Create';
            btn.disabled = false;
        }
    });

    // --- API Key Generation Form ---
    generateKeyBtn.addEventListener('click', () => {
        newKeyModal.classList.remove('hidden');
    });
    closeKeyModal.addEventListener('click', () => {
        newKeyModal.classList.add('hidden');
    });

    createKeyForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('key-name').value.trim();
        if (!currentProjectId) {
            alert('Please select a project first.');
            return;
        }
        
        const btn = createKeyForm.querySelector('button[type="submit"]');
        btn.textContent = 'Generating...';
        btn.disabled = true;
        
        try {
            const data = await apiRequest(`/api-keys/${currentProjectId}?name=${encodeURIComponent(name)}`, {
                method: 'POST',
                body: JSON.stringify({ name })
            });
            
            newKeyModal.classList.add('hidden');
            createKeyForm.reset();
            
            // Show generated key with copy button
            const rawKey = data.data.raw_key;
            generatedKeysContainer.innerHTML = `
                <div class="result-box" style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <p style="color: #10b981; font-weight: 600; margin-bottom: 5px;">Success! API Key generated for <em>${name}</em>.</p>
                    <p class="subtitle" style="font-size: 0.85rem; color: #a1a1aa; margin-bottom: 10px;">Save this secret key now. It will not be shown again.</p>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <input type="text" readonly value="${rawKey}" id="new-key-value" style="font-family: monospace; font-size: 0.85rem; width: 100%; padding: 8px 12px; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; color: #fff;">
                        <button type="button" class="btn secondary-btn" id="copy-key-btn" style="white-space: nowrap; padding: 8px 14px; font-weight: 600; cursor: pointer;">Copy</button>
                    </div>
                </div>
            `;
            
            const copyBtn = document.getElementById('copy-key-btn');
            if (copyBtn) {
                copyBtn.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText(rawKey);
                        copyBtn.textContent = 'Copied!';
                        setTimeout(() => copyBtn.textContent = 'Copy', 2000);
                    } catch (err) {
                        const input = document.getElementById('new-key-value');
                        if (input) {
                            input.select();
                            document.execCommand('copy');
                            copyBtn.textContent = 'Copied!';
                            setTimeout(() => copyBtn.textContent = 'Copy', 2000);
                        }
                    }
                });
            }

            await fetchApiKeys(currentProjectId);
        } catch (err) {
            alert('Failed to generate API Key: ' + err.message);
        } finally {
            btn.textContent = 'Generate';
            btn.disabled = false;
        }
    });

});
