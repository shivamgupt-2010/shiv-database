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
        await fetchProjects();
    }

    async function apiRequest(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...options.headers
        };
        const res = await fetch(endpoint, { ...options, headers });
        if (res.status === 401 || res.status === 403) {
            logoutBtn.click();
            throw new Error('Unauthorized');
        }
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'API Error');
        return data;
    }

    // --- Projects ---
    async function fetchProjects() {
        try {
            const data = await apiRequest('/projects/');
            renderProjects(data.data);
        } catch (err) {
            console.error('Failed to fetch projects', err);
        }
    }

    function renderProjects(projects) {
        projectsList.innerHTML = '';
        if (projects.length === 0) {
            projectsList.innerHTML = '<li><span class="text-muted">No projects found.</span></li>';
            return;
        }

        projects.forEach(p => {
            const li = document.createElement('li');
            li.innerHTML = `
                <div>
                    <strong>${p.name}</strong>
                    <div class="subtitle">ID: ${p.id}</div>
                </div>
            `;
            li.addEventListener('click', () => selectProject(p.id, li));
            projectsList.appendChild(li);
        });
    }

    function selectProject(id, element) {
        currentProjectId = id;
        document.querySelectorAll('#projects-list li').forEach(el => el.classList.remove('active'));
        element.classList.add('active');
        keyActions.classList.remove('hidden');
        generatedKeysContainer.innerHTML = '';
    }

    newProjectBtn.addEventListener('click', () => {
        newProjectModal.classList.remove('hidden');
    });
    closeProjectModal.addEventListener('click', () => {
        newProjectModal.classList.add('hidden');
    });

    createProjectForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('proj-name').value;
        const description = document.getElementById('proj-desc').value;
        
        const btn = createProjectForm.querySelector('button[type="submit"]');
        btn.textContent = 'Creating...';
        
        try {
            await apiRequest('/projects/', {
                method: 'POST',
                body: JSON.stringify({ name, description })
            });
            newProjectModal.classList.add('hidden');
            createProjectForm.reset();
            await fetchProjects();
        } catch (err) {
            alert(err.message);
        } finally {
            btn.textContent = 'Create';
        }
    });

    // --- API Keys ---
    generateKeyBtn.addEventListener('click', () => {
        newKeyModal.classList.remove('hidden');
    });
    closeKeyModal.addEventListener('click', () => {
        newKeyModal.classList.add('hidden');
    });

    createKeyForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('key-name').value;
        
        const btn = createKeyForm.querySelector('button[type="submit"]');
        btn.textContent = 'Generating...';
        
        try {
            const data = await apiRequest(`/api-keys/${currentProjectId}?name=${encodeURIComponent(name)}`, {
                method: 'POST'
            });
            
            newKeyModal.classList.add('hidden');
            createKeyForm.reset();
            
            // Show generated key
            generatedKeysContainer.innerHTML = `
                <div class="result-box">
                    <p><strong>Success!</strong> API Key generated for <em>${name}</em>.</p>
                    <p class="subtitle mt-4">Save this key now. It will not be shown again.</p>
                    <code>${data.data.raw_key}</code>
                </div>
            `;
        } catch (err) {
            alert(err.message);
        } finally {
            btn.textContent = 'Generate';
        }
    });

});
