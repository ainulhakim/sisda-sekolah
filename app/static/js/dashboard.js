// Sidebar Toggle (works for both mobile & desktop)
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        // Mobile: slide-out drawer with backdrop
        const isOpen = sidebar.classList.contains('show');
        if (isOpen) {
            sidebar.classList.remove('show');
            if (backdrop) backdrop.classList.remove('show');
        } else {
            sidebar.classList.add('show');
            if (backdrop) {
                backdrop.classList.add('show');
            } else {
                // Create backdrop
                const bd = document.createElement('div');
                bd.id = 'sidebarBackdrop';
                bd.className = 'sidebar-backdrop show';
                bd.onclick = toggleSidebar;
                document.body.appendChild(bd);
            }
        }
    } else {
        // Desktop: toggle collapsed state
        document.body.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', document.body.classList.contains('sidebar-collapsed'));
    }
}

// Close mobile sidebar
function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (sidebar) sidebar.classList.remove('show');
    if (backdrop) backdrop.classList.remove('show');
}

function toggleDarkMode() {
    const html = document.documentElement;
    const current = html.getAttribute('data-bs-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-bs-theme', next);
    localStorage.setItem('theme', next);
    const icon = document.getElementById('darkModeIcon');
    if (icon) icon.className = next === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

// Init on load
document.addEventListener('DOMContentLoaded', function() {
    // Restore theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
        const icon = document.getElementById('darkModeIcon');
        if (icon) icon.className = savedTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }

    // Restore sidebar state (desktop only)
    if (window.innerWidth > 768) {
        const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (sidebarCollapsed) {
            document.body.classList.add('sidebar-collapsed');
        }
    }

    // Close mobile sidebar when clicking content area
    const mainContent = document.getElementById('main-content');
    if (mainContent) {
        mainContent.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                const sidebar = document.getElementById('sidebar');
                if (sidebar && sidebar.classList.contains('show')) {
                    closeSidebar();
                }
            }
        });
    }

    // Close mobile sidebar on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && window.innerWidth <= 768) {
            closeSidebar();
        }
    });

    // Handle resize - clean up states
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            // Remove mobile states
            const sidebar = document.getElementById('sidebar');
            const backdrop = document.getElementById('sidebarBackdrop');
            if (sidebar) sidebar.classList.remove('show');
            if (backdrop) backdrop.classList.remove('show');
        }
    });
});
