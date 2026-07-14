function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    const isOpen = sidebar.classList.contains('show');

    if (isOpen) {
        sidebar.classList.remove('show');
        if (backdrop) backdrop.remove();
    } else {
        sidebar.classList.add('show');
        // Add backdrop for mobile
        if (window.innerWidth < 768 && !backdrop) {
            const bd = document.createElement('div');
            bd.id = 'sidebarBackdrop';
            bd.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:999;';
            bd.onclick = toggleSidebar;
            document.body.appendChild(bd);
        }
    }
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

// Load saved theme
document.addEventListener('DOMContentLoaded', function() {
    const saved = localStorage.getItem('theme');
    if (saved) {
        document.documentElement.setAttribute('data-bs-theme', saved);
        const icon = document.getElementById('darkModeIcon');
        if (icon) icon.className = saved === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
});

// Close sidebar on mobile when clicking content
document.getElementById('main-content')?.addEventListener('click', function() {
    if (window.innerWidth < 768) {
        const sidebar = document.getElementById('sidebar');
        const backdrop = document.getElementById('sidebarBackdrop');
        if (sidebar) sidebar.classList.remove('show');
        if (backdrop) backdrop.remove();
    }
});
