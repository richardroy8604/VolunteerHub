/**
 * VOLUNTEERHUB - JAVASCRIPT
 * Description: Client-side UI behavior, specifically managing sidebar collapse, 
 * mobile toggling, password visibility, and dynamic form manipulations.
 */

document.addEventListener('DOMContentLoaded', function() {
    // === 1. SIDEBAR TOGGLE & SHORTENING ANIMATION ===
    const toggleBtn = document.getElementById('toggle-sidebar-btn');
    const sidebar = document.getElementById('sidebar');
    const appContent = document.getElementById('app-content');

    if (toggleBtn && sidebar && appContent) {
        toggleBtn.addEventListener('click', function() {
            // Check if screen is mobile size (< 768px)
            const isMobile = window.innerWidth <= 768;

            if (isMobile) {
                // On mobile, completely show/hide sidebar offcanvas
                sidebar.classList.toggle('mobile-open');
            } else {
                // On desktop, toggle collapse state (which shortens it via transition)
                sidebar.classList.toggle('collapsed');
                appContent.classList.toggle('sidebar-collapsed');

                // Store user preference in localStorage
                const isCollapsed = sidebar.classList.contains('collapsed');
                localStorage.setItem('sidebar-collapsed', isCollapsed ? 'true' : 'false');
            }
        });

        // Restore sidebar preference from localStorage
        const storedPreference = localStorage.getItem('sidebar-collapsed');
        if (storedPreference === 'true' && window.innerWidth > 768) {
            sidebar.classList.add('collapsed');
            appContent.classList.add('sidebar-collapsed');
        }
    }

    // Handle window resize behaviors (e.g. removing mobile class if scaled up)
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768 && sidebar) {
            sidebar.classList.remove('mobile-open');
        }
    });

    // === 1.1 MOBILE SIDEBAR CLOSE ON OUTSIDE CLICK ===
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 768 && sidebar && sidebar.classList.contains('mobile-open')) {
            if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
                sidebar.classList.remove('mobile-open');
            }
        }
    });

    // === 2. PASSWORD VISIBILITY TOGGLE ===
    const togglePasswordBtn = document.querySelector('.toggle-password-btn');
    const passwordInput = document.querySelector('.password-input');

    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Toggle eye icon
            const icon = togglePasswordBtn.querySelector('i');
            if (icon) {
                icon.classList.toggle('bi-eye');
                icon.classList.toggle('bi-eye-slash');
            }
        });
    }

    // === 3. AUTO-HIDE DJANGO NOTIFICATION MESSAGES ===
    const messages = document.querySelectorAll('.alert-dismissible');
    messages.forEach(function(message) {
        setTimeout(function() {
            // Fade out animation using Bootstrap classes or raw CSS
            message.classList.remove('show');
            message.classList.add('fade');
            setTimeout(function() {
                message.remove();
            }, 150);
        }, 5000); // 5 seconds
    });

    // === 4. UNIVERSAL PHONE NUMBER COPY TO CLIPBOARD HANDLER ===
    document.addEventListener('click', function(e) {
        const copyBtn = e.target.closest('.copy-phone-btn');
        if (!copyBtn) return;

        e.preventDefault();
        e.stopPropagation();

        const phone = copyBtn.getAttribute('data-phone');
        if (!phone) return;

        function showSuccessFeedback() {
            const icon = copyBtn.querySelector('i');
            if (icon) {
                const originalClass = icon.className;
                icon.className = 'fa-solid fa-check text-success';
                setTimeout(function() {
                    icon.className = originalClass;
                }, 1500);
            }
        }

        // 1. Try modern Async Clipboard API
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(phone).then(showSuccessFeedback).catch(function() {
                fallbackCopyText(phone, showSuccessFeedback);
            });
        } else {
            // 2. Fallback for HTTP / local network IP contexts
            fallbackCopyText(phone, showSuccessFeedback);
        }
    });

    function fallbackCopyText(text, callback) {
        var textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.top = '-9999px';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            if (callback) callback();
        } catch (err) {
            console.error('Fallback copy failed', err);
        }
        document.body.removeChild(textArea);
    }

    // === 5. DYNAMIC SEARCH DROPDOWN ENGINE ===
    function initDynamicSearchDropdowns() {
        const searchableSelects = document.querySelectorAll('select[data-dynamic-search="true"], .dynamic-search-select');
        searchableSelects.forEach(function(select) {
            if (select.dataset.searchInitialized === 'true') return;
            select.dataset.searchInitialized = 'true';

            // Hide native select
            select.style.display = 'none';

            const parent = select.parentElement;
            if (parent) parent.style.position = 'relative';

            const container = document.createElement('div');
            container.className = 'dynamic-search-wrapper position-relative mb-2';

            function getSelectedText() {
                const selectedOpt = select.options[select.selectedIndex];
                return (selectedOpt && selectedOpt.value) ? selectedOpt.text.trim() : '';
            }

            let lastSavedText = getSelectedText();

            container.innerHTML = `
                <div class="input-group">
                    <span class="input-group-text bg-white border-end-0" style="border-color: var(--clr-border);">
                        <i class="fa-solid fa-magnifying-glass text-muted" style="font-size: 0.8rem;"></i>
                    </span>
                    <input type="text" class="form-control border-start-0 dynamic-search-input" placeholder="Type to search..." value="${lastSavedText}" style="border-color: var(--clr-border); font-size: 0.88rem; background-color: #fff; cursor: pointer;">
                </div>
                <div class="dynamic-search-results shadow border bg-white rounded-bottom d-none" style="position: absolute; top: 100%; left: 0; right: 0; max-height: 155px; overflow-y: auto; z-index: 1080; border-color: var(--clr-border) !important;">
                </div>
            `;

            parent.insertBefore(container, select);

            const input = container.querySelector('.dynamic-search-input');
            const resultsBox = container.querySelector('.dynamic-search-results');

            function renderOptions(query) {
                query = (query || '').toLowerCase().trim();
                resultsBox.innerHTML = '';
                let matchCount = 0;

                Array.from(select.options).forEach(function(option) {
                    const text = option.text.trim();
                    const val = option.value;

                    if (!query || text.toLowerCase().includes(query) || !val) {
                        matchCount++;
                        const item = document.createElement('div');
                        item.className = 'dynamic-search-item px-3 py-2 border-bottom text-dark';
                        item.style.cssText = 'cursor: pointer; font-size: 0.84rem; line-height: 1.35; transition: background-color 0.12s;';
                        
                        if (option.selected) {
                            item.style.backgroundColor = '#e6f4ea';
                            item.style.fontWeight = '700';
                            item.style.color = '#1b4d3e';
                        }

                        item.innerText = text;

                        item.addEventListener('mouseenter', function() {
                            if (select.value !== val) this.style.backgroundColor = '#f1f5f9';
                        });
                        item.addEventListener('mouseleave', function() {
                            if (select.value !== val) this.style.backgroundColor = '#fff';
                        });

                        item.addEventListener('mousedown', function(e) {
                            e.preventDefault();
                            select.value = val;
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                            lastSavedText = val ? text : '';
                            input.value = lastSavedText;
                            resultsBox.classList.add('d-none');
                        });

                        resultsBox.appendChild(item);
                    }
                });

                if (matchCount === 0) {
                    const noMatch = document.createElement('div');
                    noMatch.className = 'px-3 py-2 text-muted fst-italic';
                    noMatch.style.fontSize = '0.82rem';
                    noMatch.innerText = 'No matching options found';
                    resultsBox.appendChild(noMatch);
                }
            }

            // On focus/tap: clear text so user can immediately type to filter
            input.addEventListener('focus', function() {
                this.value = '';
                renderOptions('');
                resultsBox.classList.remove('d-none');
            });

            input.addEventListener('input', function() {
                renderOptions(this.value);
                resultsBox.classList.remove('d-none');
            });

            // Reset logic
            function resetToLastSaved() {
                lastSavedText = getSelectedText();
                input.value = lastSavedText;
                resultsBox.classList.add('d-none');
            }

            // If inside a modal, handle reset on modal show & hide (Cancel / X / Backdrop click)
            const parentModal = select.closest('.modal');
            if (parentModal) {
                parentModal.addEventListener('hidden.bs.modal', function() {
                    resetToLastSaved();
                });
                parentModal.addEventListener('show.bs.modal', function() {
                    resetToLastSaved();
                });
            }

            document.addEventListener('click', function(e) {
                if (!container.contains(e.target)) {
                    if (resultsBox.classList.contains('d-none') === false) {
                        resultsBox.classList.add('d-none');
                        // Restore saved text if user clicks outside without choosing
                        input.value = getSelectedText();
                    }
                }
            });
        });
    }

    // Run on DOM load
    initDynamicSearchDropdowns();
    // Expose globally for dynamically opened modals
    window.initDynamicSearchDropdowns = initDynamicSearchDropdowns;
});
