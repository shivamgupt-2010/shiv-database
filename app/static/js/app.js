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

    const uploadMediaBtn = document.getElementById('upload-media-btn');
    const mediaFileInput = document.getElementById('media-file-input');
    const uploadProgressBox = document.getElementById('upload-progress-box');
    const mediaGrid = document.getElementById('media-grid');

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
        if (uploadMediaBtn) uploadMediaBtn.disabled = false;
        await Promise.all([
            fetchApiKeys(id),
            fetchMediaFiles(id)
        ]);
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

    // --- Media & Storage Management (100% Free / Zero Cloud Cost) ---
    if (uploadMediaBtn && mediaFileInput) {
        uploadMediaBtn.addEventListener('click', () => {
            if (!currentProjectId) {
                alert('Please select a project first.');
                return;
            }
            mediaFileInput.click();
        });

        mediaFileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (file.size > 10 * 1024 * 1024) {
                alert('File size exceeds the 10 MB limit.');
                mediaFileInput.value = '';
                return;
            }

            if (uploadProgressBox) {
                uploadProgressBox.textContent = `Uploading "${file.name}" to SHIV Native Storage...`;
                uploadProgressBox.classList.remove('hidden');
            }
            uploadMediaBtn.disabled = true;

            try {
                const formData = new FormData();
                formData.append('file', file);

                const res = await fetch(`/storage/upload?project_id=${encodeURIComponent(currentProjectId)}`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    },
                    body: formData
                });

                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.detail || data.message || 'Upload failed');
                }

                if (uploadProgressBox) {
                    uploadProgressBox.textContent = `Success! "${file.name}" uploaded. URL: ${data.data.url}`;
                    setTimeout(() => uploadProgressBox.classList.add('hidden'), 4000);
                }

                mediaFileInput.value = '';
                await fetchMediaFiles(currentProjectId);
            } catch (err) {
                alert('Upload failed: ' + err.message);
                if (uploadProgressBox) uploadProgressBox.classList.add('hidden');
            } finally {
                uploadMediaBtn.disabled = false;
                mediaFileInput.value = '';
            }
        });
    }

    async function fetchMediaFiles(projectId) {
        if (!mediaGrid) return;
        mediaGrid.innerHTML = '<div style="color: #a1a1aa; font-size: 0.85rem; grid-column: 1 / -1; padding: 20px 0;">Loading media files...</div>';

        try {
            const res = await apiRequest(`/storage/list?project_id=${encodeURIComponent(projectId)}`);
            renderMediaFiles(res.data || []);
        } catch (err) {
            mediaGrid.innerHTML = `<div style="color: #ef4444; font-size: 0.85rem; grid-column: 1 / -1;">Failed to load files: ${err.message}</div>`;
        }
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function renderMediaFiles(files) {
        if (!mediaGrid) return;
        mediaGrid.innerHTML = '';

        if (files.length === 0) {
            mediaGrid.innerHTML = `
                <div style="color: #71717a; font-size: 0.85rem; grid-column: 1 / -1; padding: 30px 10px; text-align: center; border: 1px dashed rgba(255,255,255,0.15); border-radius: 8px;">
                    No media files stored yet.<br>Click <strong>"+ Upload Media"</strong> above to store images, logos, or documents with instant permanent public URLs.
                </div>
            `;
            return;
        }

        files.forEach(f => {
            const card = document.createElement('div');
            card.style.background = 'rgba(15, 23, 42, 0.7)';
            card.style.border = '1px solid rgba(255, 255, 255, 0.1)';
            card.style.borderRadius = '8px';
            card.style.overflow = 'hidden';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';

            const isImg = f.content_type && f.content_type.startsWith('image/');
            const previewHtml = isImg
                ? `<div style="height: 120px; width: 100%; background: #000; overflow: hidden; display: flex; align-items: center; justify-content: center;">
                     <img src="${f.url}" alt="${f.file_name}" style="max-height: 120px; max-width: 100%; object-fit: cover;" loading="lazy">
                   </div>`
                : `<div style="height: 120px; width: 100%; background: rgba(30, 41, 59, 0.8); display: flex; align-items: center; justify-content: center; font-size: 2rem;">
                     📄
                   </div>`;

            card.innerHTML = `
                ${previewHtml}
                <div style="padding: 10px 12px; flex: 1; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 600; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #f1f5f9;" title="${f.file_name}">
                            ${f.file_name}
                        </div>
                        <div style="font-size: 0.75rem; color: #a1a1aa; margin-top: 4px;">
                            ${formatBytes(f.size)} • ${f.content_type || 'file'}
                        </div>
                    </div>
                    <div style="display: flex; gap: 6px; margin-top: 10px;">
                        <button type="button" class="btn secondary-btn copy-media-url-btn" data-url="${f.url}" style="flex: 1; padding: 4px 8px; font-size: 0.75rem;">Copy URL</button>
                        <a href="${f.url}" target="_blank" rel="noopener noreferrer" class="btn ghost-btn" style="padding: 4px 8px; font-size: 0.75rem; text-decoration: none; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px;">View</a>
                        <button type="button" class="btn ghost-btn delete-media-btn" data-file-id="${f.id}" data-file-name="${f.file_name}" style="padding: 4px 8px; font-size: 0.75rem; color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 4px;">Delete</button>
                    </div>
                </div>
            `;

            const copyBtn = card.querySelector('.copy-media-url-btn');
            if (copyBtn) {
                copyBtn.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText(f.url);
                        copyBtn.textContent = 'Copied!';
                        setTimeout(() => copyBtn.textContent = 'Copy URL', 2000);
                    } catch (err) {
                        prompt('Copy file URL:', f.url);
                    }
                });
            }

            const deleteBtn = card.querySelector('.delete-media-btn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', async () => {
                    if (confirm(`Delete file "${f.file_name}" permanently?`)) {
                        deleteBtn.textContent = '...';
                        deleteBtn.disabled = true;
                        try {
                            await apiRequest(`/storage/file/${f.id}?project_id=${encodeURIComponent(currentProjectId)}`, {
                                method: 'DELETE'
                            });
                            await fetchMediaFiles(currentProjectId);
                        } catch (err) {
                            alert('Delete failed: ' + err.message);
                            deleteBtn.textContent = 'Delete';
                            deleteBtn.disabled = false;
                        }
                    }
                });
            }

            mediaGrid.appendChild(card);
        });
    }

    // ==========================================
    // --- SHIV IDENTITY & TABS MANAGEMENT ---
    // ==========================================

    // Tab Switching
    const navTabBtns = document.querySelectorAll('.nav-tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    navTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            navTabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.add('hidden'));

            btn.classList.add('active');
            const targetPane = document.getElementById(targetTab);
            if (targetPane) targetPane.classList.remove('hidden');

            if (targetTab === 'tab-identity') fetchUserProfile();
            if (targetTab === 'tab-apps') fetchDeveloperApps();
            if (targetTab === 'tab-sessions') {
                fetchConnectedApps();
                fetchActiveSessions();
            }
        });
    });

    // --- Profile Management ---
    const profileForm = document.getElementById('edit-profile-form');
    const profileFeedback = document.getElementById('profile-feedback');

    async function fetchUserProfile() {
        try {
            const res = await apiRequest('/auth/me');
            if (res && res.data) {
                const u = res.data;
                const shivId = u.shiv_id || 'SHV-USER';
                const dName = u.display_name || u.username;
                const uname = u.username;

                document.getElementById('profile-shiv-id-badge').textContent = shivId;
                document.getElementById('profile-avatar-circle').textContent = dName.charAt(0).toUpperCase();
                document.getElementById('profile-display-name-text').textContent = dName;
                document.getElementById('profile-username-text').textContent = `@${uname}`;
                document.getElementById('profile-email-text').textContent = u.email;

                const vBadge = document.getElementById('profile-email-verified-badge');
                if (u.email_verified) {
                    vBadge.textContent = 'Verified';
                    vBadge.className = 'badge badge-success';
                } else {
                    vBadge.textContent = 'Unverified';
                    vBadge.className = 'badge badge-warning';
                }

                document.getElementById('profile-role-badge').textContent = u.role || 'user';
                document.getElementById('profile-status-badge').textContent = u.status || 'active';

                // Pre-fill inputs
                document.getElementById('edit-display-name').value = u.display_name || '';
                document.getElementById('edit-bio').value = u.bio || '';
                document.getElementById('edit-website').value = u.website || '';
                document.getElementById('edit-phone').value = u.phone || '';
            }
        } catch (err) {
            console.error('Failed to fetch profile:', err);
        }
    }

    if (profileForm) {
        profileForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const saveBtn = document.getElementById('save-profile-btn');
            saveBtn.classList.add('loading');
            profileFeedback.classList.add('hidden');

            const payload = {
                display_name: document.getElementById('edit-display-name').value.trim() || null,
                bio: document.getElementById('edit-bio').value.trim() || null,
                website: document.getElementById('edit-website').value.trim() || null,
                phone: document.getElementById('edit-phone').value.trim() || null,
            };

            try {
                const res = await apiRequest('/auth/me', {
                    method: 'PATCH',
                    body: JSON.stringify(payload)
                });
                profileFeedback.textContent = 'Profile successfully updated!';
                profileFeedback.style.background = 'rgba(16, 185, 129, 0.15)';
                profileFeedback.style.border = '1px solid rgba(16, 185, 129, 0.3)';
                profileFeedback.style.color = '#34d399';
                profileFeedback.classList.remove('hidden');
                await fetchUserProfile();
            } catch (err) {
                profileFeedback.textContent = 'Update failed: ' + err.message;
                profileFeedback.style.background = 'rgba(239, 68, 68, 0.15)';
                profileFeedback.style.border = '1px solid rgba(239, 68, 68, 0.3)';
                profileFeedback.style.color = '#f87171';
                profileFeedback.classList.remove('hidden');
            } finally {
                saveBtn.classList.remove('loading');
            }
        });
    }

    // --- Developer Applications (OAuth / OIDC) ---
    const registerAppModal = document.getElementById('register-app-modal');
    const openRegisterAppBtn = document.getElementById('open-register-app-btn');
    const closeAppModal = document.getElementById('close-app-modal');
    const createAppForm = document.getElementById('create-app-form');
    const developerAppsList = document.getElementById('developer-apps-list');
    const clientSecretBanner = document.getElementById('client-secret-banner');
    const bannerSecretValue = document.getElementById('banner-secret-value');
    const copyBannerSecretBtn = document.getElementById('copy-banner-secret-btn');

    if (openRegisterAppBtn) {
        openRegisterAppBtn.addEventListener('click', () => registerAppModal.classList.remove('hidden'));
    }
    if (closeAppModal) {
        closeAppModal.addEventListener('click', () => registerAppModal.classList.add('hidden'));
    }

    if (copyBannerSecretBtn) {
        copyBannerSecretBtn.addEventListener('click', async () => {
            const secret = bannerSecretValue.value;
            try {
                await navigator.clipboard.writeText(secret);
                copyBannerSecretBtn.textContent = 'Copied!';
                setTimeout(() => copyBannerSecretBtn.textContent = 'Copy Secret', 2000);
            } catch {
                prompt('Copy secret:', secret);
            }
        });
    }

    if (createAppForm) {
        createAppForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const client_name = document.getElementById('app-name').value.trim();
            const client_type = document.getElementById('app-type').value;
            const client_uri = document.getElementById('app-website').value.trim();
            const rawUris = document.getElementById('app-redirect-uris').value.trim();
            const redirect_uris = rawUris.split(/[\n,]+/).map(u => u.trim()).filter(Boolean);

            const scopes = ['openid'];
            if (document.getElementById('scope-profile').checked) scopes.push('profile');
            if (document.getElementById('scope-email').checked) scopes.push('email');
            if (document.getElementById('scope-offline').checked) scopes.push('offline_access');

            try {
                const res = await apiRequest('/oauth/clients', {
                    method: 'POST',
                    body: JSON.stringify({
                        client_name,
                        client_type,
                        client_uri,
                        redirect_uris,
                        allowed_scopes: scopes.join(' ')
                    })
                });

                registerAppModal.classList.add('hidden');
                createAppForm.reset();

                if (res.data && res.data.client_secret) {
                    bannerSecretValue.value = res.data.client_secret;
                    clientSecretBanner.classList.remove('hidden');
                    clientSecretBanner.scrollIntoView({ behavior: 'smooth' });
                }

                await fetchDeveloperApps();
            } catch (err) {
                alert('App Registration Failed: ' + err.message);
            }
        });
    }

    async function fetchDeveloperApps() {
        if (!developerAppsList) return;
        developerAppsList.innerHTML = '<li style="color: #71717a;">Loading applications...</li>';

        try {
            const res = await apiRequest('/oauth/clients');
            const apps = res.data || [];

            if (apps.length === 0) {
                developerAppsList.innerHTML = `
                    <li style="padding: 24px; text-align: center; color: #a1a1aa;">
                        No OAuth applications registered yet. Click <strong>+ Register Application</strong> to integrate your first service.
                    </li>
                `;
                return;
            }

            developerAppsList.innerHTML = '';
            apps.forEach(app => {
                const li = document.createElement('li');
                li.style.flexDirection = 'column';
                li.style.alignItems = 'flex-start';
                li.style.gap = '12px';
                li.style.padding = '16px';
                li.style.cursor = 'default';

                const urisHtml = (app.redirect_uris || []).map(u => `<code style="font-size: 0.75rem; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; color: #93c5fd;">${u}</code>`).join(' ');

                li.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                        <div>
                            <strong style="font-size: 1.05rem; color: #fff;">${app.client_name}</strong>
                            <span class="badge ${app.client_type === 'confidential' ? 'badge-primary' : 'badge-purple'}" style="margin-left: 8px;">${app.client_type}</span>
                            <span class="badge badge-success" style="margin-left: 4px;">${app.status || 'active'}</span>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            ${app.client_type === 'confidential' ? `<button type="button" class="btn ghost-btn rotate-secret-btn" data-id="${app.id}" data-name="${app.client_name}" style="padding: 4px 10px; font-size: 0.75rem; border: 1px solid rgba(245,158,11,0.4); color: #fbbf24;">Rotate Secret</button>` : ''}
                            <button type="button" class="btn ghost-btn delete-app-btn" data-id="${app.id}" data-name="${app.client_name}" style="padding: 4px 10px; font-size: 0.75rem; border: 1px solid rgba(239,68,68,0.4); color: #ef4444;">Delete</button>
                        </div>
                    </div>
                    <div style="font-size: 0.85rem; color: #a1a1aa; width: 100%; display: flex; flex-direction: column; gap: 6px;">
                        <div>
                            <strong>Client ID:</strong> 
                            <code style="color: #60a5fa; user-select: all; font-size: 0.8rem; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">${app.client_id}</code>
                            <button type="button" class="btn ghost-btn copy-client-id-btn" data-id="${app.client_id}" style="padding: 2px 6px; font-size: 0.7rem; margin-left: 6px;">Copy</button>
                        </div>
                        <div>
                            <strong>Allowed Scopes:</strong> 
                            <span style="color: #e2e8f0; font-family: monospace; font-size: 0.8rem;">${app.allowed_scopes}</span>
                        </div>
                        <div>
                            <strong>Redirect URIs:</strong>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">${urisHtml}</div>
                        </div>
                    </div>
                `;

                // Copy Client ID
                const copyIdBtn = li.querySelector('.copy-client-id-btn');
                if (copyIdBtn) {
                    copyIdBtn.addEventListener('click', async () => {
                        await navigator.clipboard.writeText(app.client_id);
                        copyIdBtn.textContent = 'Copied!';
                        setTimeout(() => copyIdBtn.textContent = 'Copy', 1500);
                    });
                }

                // Rotate Secret
                const rotateBtn = li.querySelector('.rotate-secret-btn');
                if (rotateBtn) {
                    rotateBtn.addEventListener('click', async () => {
                        if (confirm(`Rotate client secret for "${app.client_name}"? Existing client applications using the old secret will fail immediately until updated.`)) {
                            try {
                                const rotRes = await apiRequest(`/oauth/clients/${app.id}/rotate-secret`, { method: 'POST' });
                                if (rotRes.data && rotRes.data.client_secret) {
                                    bannerSecretValue.value = rotRes.data.client_secret;
                                    clientSecretBanner.classList.remove('hidden');
                                    clientSecretBanner.scrollIntoView({ behavior: 'smooth' });
                                }
                            } catch (err) {
                                alert('Secret rotation failed: ' + err.message);
                            }
                        }
                    });
                }

                // Delete App
                const delBtn = li.querySelector('.delete-app-btn');
                if (delBtn) {
                    delBtn.addEventListener('click', async () => {
                        if (confirm(`Permanently delete OAuth application "${app.client_name}"? All issued authorization codes and tokens will be invalidated.`)) {
                            try {
                                await apiRequest(`/oauth/clients/${app.id}`, { method: 'DELETE' });
                                await fetchDeveloperApps();
                            } catch (err) {
                                alert('Delete failed: ' + err.message);
                            }
                        }
                    });
                }

                developerAppsList.appendChild(li);
            });
        } catch (err) {
            developerAppsList.innerHTML = `<li style="color: #ef4444;">Error loading applications: ${err.message}</li>`;
        }
    }

    // --- Connected Applications (User Consents) ---
    const connectedAppsList = document.getElementById('connected-apps-list');

    async function fetchConnectedApps() {
        if (!connectedAppsList) return;
        connectedAppsList.innerHTML = '<li style="color: #71717a;">Loading connected applications...</li>';

        try {
            const res = await apiRequest('/oauth/grants');
            const grants = res.data || [];

            if (grants.length === 0) {
                connectedAppsList.innerHTML = '<li style="padding: 20px; text-align: center; color: #a1a1aa;">No external applications have been granted access to your account.</li>';
                return;
            }

            connectedAppsList.innerHTML = '';
            grants.forEach(g => {
                const li = document.createElement('li');
                li.style.display = 'flex';
                li.style.justifyContent = 'space-between';
                li.style.alignItems = 'center';
                li.style.padding = '12px 16px';
                li.style.cursor = 'default';

                li.innerHTML = `
                    <div>
                        <strong style="color: #fff;">${g.client_name || g.client_id}</strong>
                        <div style="font-size: 0.75rem; color: #a1a1aa; margin-top: 2px;">
                            Scopes: <span style="color: #60a5fa;">${g.granted_scopes}</span>
                        </div>
                    </div>
                    <button type="button" class="btn ghost-btn revoke-grant-btn" data-client-id="${g.client_id}" style="color: #ef4444; border: 1px solid rgba(239,68,68,0.3); font-size: 0.75rem; padding: 4px 10px;">Revoke Access</button>
                `;

                const revBtn = li.querySelector('.revoke-grant-btn');
                revBtn.addEventListener('click', async () => {
                    if (confirm(`Revoke access for "${g.client_name || g.client_id}"?`)) {
                        try {
                            await apiRequest(`/oauth/grants/${g.client_id}`, { method: 'DELETE' });
                            await fetchConnectedApps();
                        } catch (err) {
                            alert('Failed to revoke access: ' + err.message);
                        }
                    }
                });

                connectedAppsList.appendChild(li);
            });
        } catch (err) {
            connectedAppsList.innerHTML = `<li style="color: #ef4444;">Error: ${err.message}</li>`;
        }
    }

    // --- Active Sessions ---
    const activeSessionsList = document.getElementById('active-sessions-list');
    const revokeAllSessionsBtn = document.getElementById('revoke-all-sessions-btn');

    async function fetchActiveSessions() {
        if (!activeSessionsList) return;
        activeSessionsList.innerHTML = '<li style="color: #71717a;">Loading active sessions...</li>';

        try {
            const res = await apiRequest('/auth/sessions');
            const sessions = res.data || [];

            if (sessions.length === 0) {
                activeSessionsList.innerHTML = '<li style="padding: 20px; text-align: center; color: #a1a1aa;">No active sessions found.</li>';
                return;
            }

            activeSessionsList.innerHTML = '';
            sessions.forEach(s => {
                const li = document.createElement('li');
                li.style.display = 'flex';
                li.style.justifyContent = 'space-between';
                li.style.alignItems = 'center';
                li.style.padding = '12px 16px';
                li.style.cursor = 'default';

                const ip = s.ip_address || 'Unknown IP';
                const ua = s.user_agent ? (s.user_agent.length > 40 ? s.user_agent.substring(0, 40) + '...' : s.user_agent) : 'Browser / Client';
                const created = s.created_at ? new Date(s.created_at).toLocaleString() : 'Recent';

                li.innerHTML = `
                    <div>
                        <strong style="color: #fff; font-size: 0.85rem;">${ua}</strong>
                        <div style="font-size: 0.75rem; color: #a1a1aa; margin-top: 2px;">
                            IP: ${ip} • Signed in: ${created}
                        </div>
                    </div>
                    <button type="button" class="btn ghost-btn revoke-session-btn" data-session-id="${s.id}" style="color: #ef4444; border: 1px solid rgba(239,68,68,0.3); font-size: 0.75rem; padding: 4px 10px;">Terminate</button>
                `;

                const termBtn = li.querySelector('.revoke-session-btn');
                termBtn.addEventListener('click', async () => {
                    if (confirm('Terminate this active session?')) {
                        try {
                            await apiRequest(`/auth/sessions/${s.id}`, { method: 'DELETE' });
                            await fetchActiveSessions();
                        } catch (err) {
                            alert('Failed to terminate session: ' + err.message);
                        }
                    }
                });

                activeSessionsList.appendChild(li);
            });
        } catch (err) {
            activeSessionsList.innerHTML = `<li style="color: #ef4444;">Error: ${err.message}</li>`;
        }
    }

    if (revokeAllSessionsBtn) {
        revokeAllSessionsBtn.addEventListener('click', async () => {
            if (confirm('Terminate all other device sessions? You will remain logged in on this current browser.')) {
                try {
                    await apiRequest('/auth/sessions/revoke-all', { method: 'POST' });
                    await fetchActiveSessions();
                } catch (err) {
                    alert('Failed to revoke sessions: ' + err.message);
                }
            }
        });
    }

});

