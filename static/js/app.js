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
});
